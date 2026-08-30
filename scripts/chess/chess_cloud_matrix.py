#!/usr/bin/env python3
"""Bounded no-tools Claude/Codex Chess verification matrix."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

import chess

import chess_benchmark as benchmark
import chess_llm_policy as llm_policy

SCHEMA_VERSION = "chess/cloud-matrix-result/v1"
CONFIG_SCHEMA = "chess/model-verification-matrix/v1"
BACKENDS = {"codex-cli", "claude-cli", "devin-cli-batch"}


class ProviderFailure(ValueError):
    def __init__(self, message: str, metadata: dict[str, Any], raw_output: str | None = None):
        super().__init__(message)
        self.metadata = metadata
        self.raw_output = raw_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--track", choices=llm_policy.TRACKS, required=True)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported chess model matrix config")
    models = config.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("model matrix must contain models")
    optional_top_level = {"supersedes", "supersession_reason"}
    required_top_level = {
        "schema_version",
        "suite_id",
        "track",
        "strict_raw_diagnostic_positions",
        "frozen_before_scoring",
        "models",
    }
    if not required_top_level.issubset(config) or set(config) - required_top_level - optional_top_level:
        raise ValueError("model matrix top-level fields are incomplete")
    ids = []
    required = {
        "policy_id",
        "backend",
        "requested_model",
        "role",
        "reasoning_effort",
        "maximum_positions",
        "command_timeout_seconds",
        "max_budget_usd_per_decision",
    }
    for entry in models:
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("model matrix entry fields are incomplete")
        if entry["backend"] not in BACKENDS:
            raise ValueError("unsupported model matrix backend")
        if entry["reasoning_effort"] not in {"low", "medium", "high"}:
            raise ValueError("unsupported reasoning effort")
        if not isinstance(entry["maximum_positions"], int) or entry["maximum_positions"] < 1:
            raise ValueError("maximum positions must be positive")
        if not isinstance(entry["command_timeout_seconds"], int) or entry["command_timeout_seconds"] < 1:
            raise ValueError("command timeout must be positive")
        budget = entry["max_budget_usd_per_decision"]
        if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget < 0:
            raise ValueError("decision budget must be non-negative")
        ids.append(entry["policy_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("model matrix policy ids must be unique")
    return config


def select_model(config: dict[str, Any], policy_id: str) -> dict[str, Any]:
    matches = [entry for entry in config["models"] if entry["policy_id"] == policy_id]
    if len(matches) != 1:
        raise ValueError(f"policy id is not declared exactly once: {policy_id}")
    return matches[0]


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
        raise ValueError("Codex CLI attempted tool use")
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
    return {"event_count": len(events), "resolved_models": resolved, "cost_usd": None}


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
    usage = envelope.get("modelUsage") if isinstance(envelope.get("modelUsage"), dict) else {}
    return raw, {
        "resolved_models": sorted(usage),
        "cost_usd": envelope.get("total_cost_usd"),
        "turns": envelope.get("num_turns"),
        "usage": usage,
    }


class CloudChessPolicy:
    revision = "cloud-cli-chess-policy/v2"

    def __init__(self, entry: dict[str, Any], track: str):
        llm_policy.validate_track(track)
        self.entry = dict(entry)
        self.track = track
        self.policy_id = entry["policy_id"]
        self.call_metadata: list[dict[str, Any]] = []

    def _run_codex(self, state: dict[str, Any], legal_moves: Sequence[str]) -> tuple[str, dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="chess-codex-matrix-") as directory:
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
            if self.track == llm_policy.LEGAL_CONSTRAINED_TRACK:
                schema_path = root / "move-schema.json"
                schema_path.write_text(
                    json.dumps(llm_policy.constrained_action_schema(legal_moves), sort_keys=True),
                    encoding="utf-8",
                )
                command.extend(["--output-schema", str(schema_path)])
            command.append(llm_policy.flat_prompt(state))
            completed = subprocess.run(
                command,
                cwd=directory,
                text=True,
                capture_output=True,
                timeout=self.entry["command_timeout_seconds"],
                check=False,
            )
            raw = output_path.read_text(encoding="utf-8") if output_path.exists() else None
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise ProviderFailure(
                    f"Codex CLI failed with exit {completed.returncode}: {detail[:300]}",
                    {"resolved_models": [], "cost_usd": None, "provider_error": f"codex-cli-exit-{completed.returncode}"},
                    raw,
                )
            return raw or "", parse_codex_events(completed.stdout)

    def _run_claude(self, state: dict[str, Any], legal_moves: Sequence[str]) -> tuple[str, dict[str, Any]]:
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
            command.extend(["--json-schema", json.dumps(llm_policy.constrained_action_schema(legal_moves))])
        command.append(benchmark.serialize_observation(state))
        with tempfile.TemporaryDirectory(prefix="chess-claude-matrix-") as directory:
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
                    usage = envelope.get("modelUsage") if isinstance(envelope.get("modelUsage"), dict) else {}
                    metadata.update(
                        {
                            "resolved_models": sorted(usage),
                            "cost_usd": envelope.get("total_cost_usd"),
                            "turns": envelope.get("num_turns"),
                            "provider_error": envelope.get("subtype") or metadata["provider_error"],
                        }
                    )
            except json.JSONDecodeError:
                pass
            raise ProviderFailure(f"Claude CLI failed with exit {completed.returncode}: {detail[:300]}", metadata)
        return parse_claude_envelope(completed.stdout, constrained)

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        if self.entry["backend"] == "devin-cli-batch":
            raise ProviderFailure(
                "Devin GLM uses the sealed batch adapter, not the per-position cloud adapter",
                {"resolved_models": [], "cost_usd": 0.0, "provider_error": "wrong-adapter"},
            )
        executable = self.entry["backend"].removesuffix("-cli")
        if shutil.which(executable) is None:
            raise ProviderFailure(
                f"cloud backend executable is unavailable: {executable}",
                {"resolved_models": [], "cost_usd": None, "provider_error": "backend-unavailable"},
            )
        started = time.perf_counter_ns()
        try:
            if self.entry["backend"] == "codex-cli":
                raw, metadata = self._run_codex(state, legal_moves)
            else:
                raw, metadata = self._run_claude(state, legal_moves)
        except ProviderFailure as exc:
            exc.metadata["adapter_wall_time_ms"] = (time.perf_counter_ns() - started) / 1_000_000
            self.call_metadata.append(exc.metadata)
            raise
        metadata["adapter_wall_time_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        self.call_metadata.append(metadata)
        if self.track == llm_policy.LEGAL_CONSTRAINED_TRACK:
            board = chess.Board(state["fen"])
            return llm_policy.parse_constrained_output(raw, board).uci()
        return raw


def main() -> int:
    args = parse_args()
    if not 1 <= args.parallel <= 8:
        raise ValueError("parallelism must be from one through eight")
    config = load_config(args.config)
    entry = select_model(config, args.policy_id)
    suite = benchmark.load_puzzle_suite(args.suite)
    configured_limit = entry["maximum_positions"]
    if args.track == llm_policy.STRICT_TRACK:
        configured_limit = min(configured_limit, config["strict_raw_diagnostic_positions"])
    limit = min(len(suite["puzzles"]), configured_limit, args.limit or configured_limit)
    selected_suite = {**suite, "puzzles": suite["puzzles"][:limit]}

    def run_one(puzzle: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        one = {**selected_suite, "puzzles": [puzzle]}
        policy = CloudChessPolicy(entry, args.track)
        decision = benchmark.evaluate_puzzles(policy, one)["decisions"][0]
        return decision, policy.call_metadata

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
        completed = list(executor.map(run_one, selected_suite["puzzles"]))
    decisions = [decision for decision, _ in completed]
    provider_calls = [call for _, calls in completed for call in calls]
    exact = sum(row["exact"] for row in decisions)
    legal = sum(row["legal"] for row in decisions)
    failures = sum(row["failure"] is not None for row in decisions)
    total_cost_values = [call.get("cost_usd") for call in provider_calls if isinstance(call.get("cost_usd"), (int, float))]
    resolved_models = sorted({model for call in provider_calls for model in call.get("resolved_models", [])})
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "candidate-verification-only-not-frozen-evidence",
        "suite_id": suite["suite_id"],
        "track": args.track,
        "model": {**entry, "resolved_models": resolved_models},
        "runtime": {
            "python": platform.python_version(),
            "codex_cli": subprocess.run(["codex", "--version"], text=True, capture_output=True, timeout=10).stdout.strip(),
            "claude_cli": subprocess.run(["claude", "--version"], text=True, capture_output=True, timeout=10).stdout.strip(),
        },
        "aggregate": {
            "puzzles": len(decisions),
            "exact": exact,
            "exact_move_accuracy": exact / len(decisions),
            "legal": legal,
            "legal_rate": legal / len(decisions),
            "provider_failures": failures,
            "provider_failure_rate": failures / len(decisions),
            "mean_latency_ms": sum(row["latency_ms"] for row in decisions) / len(decisions),
            "total_cost_usd": sum(total_cost_values) if total_cost_values else None,
            "constraint_applied_rate": 1.0 if args.track == llm_policy.LEGAL_CONSTRAINED_TRACK else 0.0,
            "execution_rate": legal / len(decisions),
            "executed_legal": legal,
            "executed_legal_rate": 1.0 if legal else None,
            "abstention_or_redirect_required": len(decisions) - legal,
            "abstention_or_redirect_rate": (len(decisions) - legal) / len(decisions),
        },
        "provider_calls": provider_calls,
        "decisions": decisions,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
