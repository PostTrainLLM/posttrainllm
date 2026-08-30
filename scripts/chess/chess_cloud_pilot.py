#!/usr/bin/env python3
"""Run a bounded no-tools Codex CLI chess-tactics development screen."""

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

import chess_benchmark as benchmark
import chess_llm_policy as llm_policy

SCHEMA_VERSION = "chess/cloud-puzzle-pilot/v1"


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
    return {"event_count": len(events)}


class CodexChessPolicy:
    revision = "codex-cli-chess-policy/v1"

    def __init__(
        self, requested_model: str, reasoning_effort: str, timeout_seconds: int
    ):
        if shutil.which("codex") is None:
            raise ValueError("codex executable is unavailable")
        self.policy_id = f"codex-{requested_model}-development"
        self.requested_model = requested_model
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.call_metadata: list[dict[str, Any]] = []

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        del legal_moves
        with tempfile.TemporaryDirectory(prefix="chess-codex-") as directory:
            output_path = Path(directory) / "last-message.txt"
            command = [
                "codex",
                "exec",
                "--model",
                self.requested_model,
                "--config",
                f'model_reasoning_effort="{self.reasoning_effort}"',
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
                llm_policy.flat_prompt(state),
            ]
            started = time.perf_counter_ns()
            completed = subprocess.run(
                command,
                cwd=directory,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            wall_ms = (time.perf_counter_ns() - started) / 1_000_000
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                self.call_metadata.append(
                    {"wall_time_ms": wall_ms, "provider_error": detail[:300]}
                )
                raise ValueError(
                    f"Codex CLI failed with exit {completed.returncode}: {detail[:300]}"
                )
            metadata = parse_codex_events(completed.stdout)
            metadata["wall_time_ms"] = wall_ms
            self.call_metadata.append(metadata)
            return output_path.read_text(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument(
        "--reasoning-effort", choices=("low", "medium", "high"), default="medium"
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.parallel <= 8:
        raise ValueError("parallelism must be from 1 through 8")
    suite = benchmark.load_puzzle_suite(args.suite)

    def run_one(puzzle: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        one = {**suite, "puzzles": [puzzle]}
        policy = CodexChessPolicy(
            args.model, args.reasoning_effort, args.timeout_seconds
        )
        return benchmark.evaluate_puzzles(policy, one)["decisions"][
            0
        ], policy.call_metadata

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
        completed = list(executor.map(run_one, suite["puzzles"]))
    decisions = [row for row, _ in completed]
    for index, row in enumerate(decisions):
        row["index"] = index
    provider_calls = [call for _, calls in completed for call in calls]
    exact = sum(row["exact"] for row in decisions)
    legal = sum(row["legal"] for row in decisions)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "development-only-mutable-model-alias",
        "environment_revision": benchmark.ENVIRONMENT_REVISION,
        "observation_revision": benchmark.OBSERVATION_REVISION,
        "suite_id": suite["suite_id"],
        "model": {
            "policy_id": f"codex-{args.model}-development",
            "requested_model": args.model,
            "identity_state": "mutable-alias-development-only",
            "reasoning_effort": args.reasoning_effort,
        },
        "runtime": {
            "python": platform.python_version(),
            "codex_cli": subprocess.run(
                ["codex", "--version"], text=True, capture_output=True, timeout=10
            ).stdout.strip(),
        },
        "aggregate": {
            "puzzles": len(decisions),
            "exact": exact,
            "exact_move_accuracy": exact / len(decisions),
            "legal": legal,
            "legal_rate": legal / len(decisions),
            "mean_latency_ms": sum(row["latency_ms"] for row in decisions)
            / len(decisions),
            "total_wall_time_ms": sum(row["latency_ms"] for row in decisions),
        },
        "provider_calls": provider_calls,
        "decisions": decisions,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(
        json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
