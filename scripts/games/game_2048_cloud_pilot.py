#!/usr/bin/env python3
"""Run a bounded no-tools cloud-CLI 2048 policy pilot; never frozen evidence."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import game_2048 as game
import game_2048_llm_policy as llm_policy

SCHEMA_VERSION = "game-2048/cloud-cli-pilot/v1"
ADAPTER_REVISION = "cloud-cli-character-policy/v1"
BACKENDS = {"codex-cli", "claude-cli"}


class CloudProviderError(ValueError):
    def __init__(self, message: str, metadata: dict[str, Any]):
        super().__init__(message)
        self.metadata = metadata


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "game-2048/cloud-opponents/v1":
        raise ValueError("unsupported cloud opponent config")
    opponents = config.get("opponents")
    if not isinstance(opponents, list) or not opponents:
        raise ValueError("cloud opponent config must contain opponents")
    policy_ids = []
    for entry in opponents:
        required = {
            "policy_id",
            "backend",
            "requested_model",
            "identity_state",
            "reasoning_effort",
            "max_budget_usd_per_decision",
            "command_timeout_seconds",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("cloud opponent entry fields are incomplete")
        if entry["backend"] not in BACKENDS:
            raise ValueError(f"unsupported cloud backend: {entry['backend']}")
        if entry["identity_state"] not in {"mutable-alias", "immutable"}:
            raise ValueError("cloud identity state must be mutable-alias or immutable")
        if entry["reasoning_effort"] not in {"low", "medium", "high"}:
            raise ValueError("cloud reasoning effort must be low, medium, or high")
        if (
            not isinstance(entry["command_timeout_seconds"], int)
            or entry["command_timeout_seconds"] <= 0
        ):
            raise ValueError("cloud command timeout must be a positive integer")
        budget = entry["max_budget_usd_per_decision"]
        if (
            not isinstance(budget, (int, float))
            or isinstance(budget, bool)
            or budget < 0
        ):
            raise ValueError("cloud decision budget must be non-negative")
        policy_ids.append(entry["policy_id"])
    if len(policy_ids) != len(set(policy_ids)):
        raise ValueError("cloud policy ids must be unique")
    return config


def select_opponent(config: dict[str, Any], policy_id: str) -> dict[str, Any]:
    matches = [
        entry for entry in config["opponents"] if entry["policy_id"] == policy_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"cloud opponent policy is not declared exactly once: {policy_id}"
        )
    return matches[0]


def parse_claude_envelope(stdout: str, constrained: bool) -> tuple[str, dict[str, Any]]:
    envelope = json.loads(stdout)
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        raise ValueError("Claude CLI returned an error envelope")
    if constrained:
        structured = envelope.get("structured_output")
        if not isinstance(structured, dict):
            raise ValueError("Claude constrained output is missing structured_output")
        raw = json.dumps(structured, sort_keys=True)
    else:
        raw = envelope.get("result")
        if not isinstance(raw, str):
            raise ValueError("Claude strict output is missing result text")
    usage = (
        envelope.get("modelUsage")
        if isinstance(envelope.get("modelUsage"), dict)
        else {}
    )
    return raw, {
        "resolved_models": sorted(usage),
        "cost_usd": envelope.get("total_cost_usd"),
        "turns": envelope.get("num_turns"),
    }


def codex_event_uses_tools(event: dict[str, Any]) -> bool:
    event_type = str(event.get("type", ""))
    item = event.get("item") if isinstance(event.get("item"), dict) else {}
    item_type = str(item.get("type", ""))
    markers = ("command", "tool", "mcp", "web_search", "file_change")
    return any(marker in event_type or marker in item_type for marker in markers)


def parse_codex_events(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if not events:
        raise ValueError("Codex CLI emitted no JSONL events")
    if any(not isinstance(event, dict) for event in events):
        raise ValueError("Codex CLI emitted a non-object event")
    if any(codex_event_uses_tools(event) for event in events):
        raise ValueError("Codex CLI attempted tool use in a no-tools benchmark")
    if any(event.get("type") == "error" for event in events):
        raise ValueError("Codex CLI emitted an error event")
    resolved = sorted(
        {
            value
            for event in events
            for key, value in event.items()
            if key in {"model", "model_id"} and isinstance(value, str)
        }
    )
    return {"resolved_models": resolved, "event_count": len(events), "cost_usd": None}


class CloudCliPolicy:
    revision = ADAPTER_REVISION

    def __init__(self, entry: dict[str, Any], track: str):
        llm_policy.validate_track(track)
        self.entry = dict(entry)
        self.track = track
        self.policy_id = entry["policy_id"]
        self.raw_outputs: list[str] = []
        self.call_metadata: list[dict[str, Any]] = []

    def _run_claude(
        self, observation: dict[str, Any], legal_actions: Sequence[str]
    ) -> tuple[str, dict[str, Any]]:
        constrained = self.track == llm_policy.LEGAL_CONSTRAINED_TRACK
        command = [
            "claude",
            "--print",
            "--safe-mode",
            "--tools",
            "",
            "--no-session-persistence",
            "--model",
            self.entry["requested_model"],
            "--fallback-model",
            self.entry["requested_model"],
            "--effort",
            self.entry["reasoning_effort"],
            "--output-format",
            "json",
            "--max-budget-usd",
            str(self.entry["max_budget_usd_per_decision"]),
            "--system-prompt",
            llm_policy.SYSTEM_PROMPT,
        ]
        if constrained:
            command.extend(
                [
                    "--json-schema",
                    json.dumps(llm_policy.constrained_action_schema(legal_actions)),
                ]
            )
        command.append(game.serialize_character_observation(observation))
        with tempfile.TemporaryDirectory(prefix="game-2048-claude-") as directory:
            completed = subprocess.run(
                command,
                cwd=directory,
                text=True,
                capture_output=True,
                timeout=self.entry["command_timeout_seconds"],
                check=False,
            )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            metadata: dict[str, Any] = {
                "resolved_models": [],
                "cost_usd": None,
                "provider_error": f"claude-cli-exit-{completed.returncode}",
            }
            try:
                envelope = json.loads(completed.stdout)
                if isinstance(envelope, dict):
                    usage = (
                        envelope.get("modelUsage")
                        if isinstance(envelope.get("modelUsage"), dict)
                        else {}
                    )
                    metadata.update(
                        {
                            "resolved_models": sorted(usage),
                            "cost_usd": envelope.get("total_cost_usd"),
                            "turns": envelope.get("num_turns"),
                            "provider_error": envelope.get("subtype")
                            or metadata["provider_error"],
                        }
                    )
            except json.JSONDecodeError:
                pass
            raise CloudProviderError(
                f"Claude CLI failed with exit {completed.returncode}: {detail[:300]}",
                metadata,
            )
        return parse_claude_envelope(completed.stdout, constrained)

    def _run_codex(
        self, observation: dict[str, Any], legal_actions: Sequence[str]
    ) -> tuple[str, dict[str, Any]]:
        constrained = self.track == llm_policy.LEGAL_CONSTRAINED_TRACK
        with tempfile.TemporaryDirectory(prefix="game-2048-codex-") as directory:
            root = Path(directory)
            output_path = root / "last-message.txt"
            command = [
                "codex",
                "exec",
                "--model",
                self.entry["requested_model"],
                "--config",
                f'model_reasoning_effort="{self.entry["reasoning_effort"]}"',
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--cd",
                directory,
                "--json",
                "--output-last-message",
                str(output_path),
            ]
            if constrained:
                schema_path = root / "action-schema.json"
                schema_path.write_text(
                    json.dumps(
                        llm_policy.constrained_action_schema(legal_actions),
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                command.extend(["--output-schema", str(schema_path)])
            command.append(llm_policy.flat_prompt(observation))
            completed = subprocess.run(
                command,
                cwd=directory,
                text=True,
                capture_output=True,
                timeout=self.entry["command_timeout_seconds"],
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise CloudProviderError(
                    f"Codex CLI failed with exit {completed.returncode}: {detail[:300]}",
                    {
                        "resolved_models": [],
                        "cost_usd": None,
                        "provider_error": f"codex-cli-exit-{completed.returncode}",
                    },
                )
            metadata = parse_codex_events(completed.stdout)
            raw = output_path.read_text(encoding="utf-8")
        return raw, metadata

    def choose(self, observation: dict[str, Any], legal_actions: Sequence[str]) -> str:
        executable = self.entry["backend"].removesuffix("-cli")
        if shutil.which(executable) is None:
            raise ValueError(f"cloud backend executable is unavailable: {executable}")
        started = time.perf_counter_ns()
        try:
            if self.entry["backend"] == "claude-cli":
                raw, metadata = self._run_claude(observation, legal_actions)
            else:
                raw, metadata = self._run_codex(observation, legal_actions)
        except CloudProviderError as exc:
            exc.metadata["adapter_wall_time_ms"] = (
                time.perf_counter_ns() - started
            ) / 1_000_000
            self.call_metadata.append(exc.metadata)
            raise ValueError(str(exc)) from exc
        metadata["adapter_wall_time_ms"] = (
            time.perf_counter_ns() - started
        ) / 1_000_000
        self.raw_outputs.append(raw)
        self.call_metadata.append(metadata)
        if self.track == llm_policy.LEGAL_CONSTRAINED_TRACK:
            return llm_policy.parse_constrained_output(raw)
        return game.parse_character_action(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument(
        "--track", choices=llm_policy.TRACKS, default=llm_policy.STRICT_TRACK
    )
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--max-moves", type=int, default=1)
    parser.add_argument("--parallel-games", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_moves <= 128:
        raise ValueError("cloud pilot max-moves must be from 1 through 128")
    if not 1 <= args.parallel_games <= 8:
        raise ValueError("cloud pilot parallel games must be from 1 through 8")
    config = load_config(args.config)
    entry = select_opponent(config, args.policy_id)
    executable = entry["backend"].removesuffix("-cli")
    if shutil.which(executable) is None:
        raise ValueError(f"cloud backend executable is unavailable: {executable}")
    version = subprocess.run(
        [executable, "--version"],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    def run_seed(
        seed: int,
    ) -> tuple[int, dict[str, Any], list[str], list[dict[str, Any]]]:
        seed_policy = CloudCliPolicy(entry, args.track)
        episode = game.run_episode(
            seed_policy,
            seed,
            max_moves=args.max_moves,
            per_move_milliseconds=entry["command_timeout_seconds"] * 1_000,
        )
        return seed, episode, seed_policy.raw_outputs, seed_policy.call_metadata

    if args.parallel_games == 1:
        completed_seeds = [run_seed(seed) for seed in args.seed]
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.parallel_games
        ) as executor:
            completed_seeds = list(executor.map(run_seed, args.seed))
    by_seed = {
        seed: (episode, raw, calls) for seed, episode, raw, calls in completed_seeds
    }
    episodes = [by_seed[seed][0] for seed in args.seed]
    raw_outputs_by_seed = [
        {"seed": seed, "outputs": by_seed[seed][1]} for seed in args.seed
    ]
    provider_calls = [
        {"seed": seed, **call} for seed in args.seed for call in by_seed[seed][2]
    ]
    resolved_models = sorted(
        {model for call in provider_calls for model in call.get("resolved_models", [])}
    )
    provider_failed = any(call.get("provider_error") for call in provider_calls)
    identity_failed = entry["identity_state"] == "immutable" and resolved_models != [
        entry["requested_model"]
    ]
    run_failed = provider_failed or identity_failed
    total_cost = sum(
        value
        for call in provider_calls
        if isinstance((value := call.get("cost_usd")), (int, float))
    )
    random_episodes = [
        game.run_episode(
            game.RandomLegalPolicy(seed),
            seed,
            max_moves=args.max_moves,
            per_move_milliseconds=1_000,
        )
        for seed in args.seed
    ]
    score_deltas = [
        episode["metrics"]["score"] - baseline["metrics"]["score"]
        for episode, baseline in zip(episodes, random_episodes)
    ]
    model_mean = sum(episode["metrics"]["score"] for episode in episodes) / len(
        episodes
    )
    random_mean = sum(episode["metrics"]["score"] for episode in random_episodes) / len(
        random_episodes
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "development-run-failed-provider"
            if provider_failed
            else "development-run-failed-identity"
            if identity_failed
            else "development-smoke-not-frozen-evidence"
        ),
        "adapter_revision": ADAPTER_REVISION,
        "evaluation_track": args.track,
        "opponent": entry,
        "cli_version": (version.stdout.strip() or version.stderr.strip())[:200],
        "resolved_models": resolved_models,
        "episodes": episodes,
        "raw_outputs_by_seed": raw_outputs_by_seed,
        "provider_calls": provider_calls,
        "total_cost_usd": total_cost,
        "identity_error": (
            {"requested": entry["requested_model"], "resolved": resolved_models}
            if identity_failed
            else None
        ),
        "aggregate": None
        if run_failed
        else {
            "games": len(episodes),
            "mean_score": model_mean,
            "mean_moves": sum(episode["metrics"]["move_count"] for episode in episodes)
            / len(episodes),
            "invalid_decisions": sum(
                episode["metrics"]["decisions"] - episode["metrics"]["legal_decisions"]
                for episode in episodes
            ),
        },
        "random_legal_comparison": None
        if run_failed
        else {
            "random_mean_score": random_mean,
            "model_to_random_mean_score_ratio": model_mean / random_mean
            if random_mean
            else None,
            "paired_mean_score_delta": sum(score_deltas) / len(score_deltas),
            "paired_win_rate": sum(delta > 0 for delta in score_deltas)
            / len(score_deltas),
            "paired_bootstrap_95_ci": game.paired_bootstrap(
                score_deltas, 256, 2048999001
            ),
            "score_deltas_by_seed": [
                {"seed": seed, "delta": delta}
                for seed, delta in zip(args.seed, score_deltas)
            ],
        },
    }
    game.write_json_exclusive(args.output, result)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "resolved_models": result["resolved_models"],
                "total_cost_usd": total_cost,
            }
        )
    )
    return 1 if run_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
