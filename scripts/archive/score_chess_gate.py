
# These modules moved to sibling group folders when scripts/ was grouped;
# add those folders to the import path so this archived script still runs.
import sys as _sys
from pathlib import Path as _Path
for _g in ["chess"]:
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / _g))

#!/usr/bin/env python3
"""Score the frozen chess Gate-0 capability-gradient decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess_benchmark as benchmark

SCHEMA_VERSION = "chess/gate-0-decision/v1"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--random", type=Path, required=True)
    parser.add_argument("--local", type=Path, action="append", required=True)
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--matches", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gate = load(args.gate)
    random_result = load(args.random)
    locals_ = [load(path) for path in args.local]
    frontier = load(args.frontier)
    expected_count = gate["required_puzzles"]
    all_results = [random_result, *locals_, frontier]
    if any(result["aggregate"]["puzzles"] != expected_count for result in all_results):
        raise ValueError("all Gate-0 results must use the frozen puzzle count")
    random_accuracy = random_result["calibration"]["mean_exact_move_accuracy"]
    local_rows = [
        {
            "policy_id": result["model"]["policy_id"],
            "model_ref": result["model"]["model_ref"],
            **result["aggregate"],
            "trace_hash": result["trace_hash"],
        }
        for result in locals_
    ]
    strongest_local = max(local_rows, key=lambda row: row["exact_move_accuracy"])
    frontier_accuracy = frontier["aggregate"]["exact_move_accuracy"]
    thresholds = gate["frontier"]
    checks = {
        "complete_puzzle_count": frontier["aggregate"]["puzzles"] == expected_count,
        "strict_legal_rate": frontier["aggregate"]["legal_rate"] >= thresholds["strict_legal_rate_minimum"],
        "frontier_exact_accuracy": frontier_accuracy >= thresholds["exact_move_accuracy_minimum"],
        "frontier_margin_over_calibrated_random": frontier_accuracy - random_accuracy >= thresholds["accuracy_margin_over_random_minimum"],
        "frontier_margin_over_strongest_local": frontier_accuracy - strongest_local["exact_move_accuracy"] >= thresholds["accuracy_margin_over_strongest_local_general_minimum"],
    }
    passed = all(checks.values())
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "valid-development-gate-pass" if passed else "valid-development-gate-fail",
        "decision": "admit-for-frozen-suite-design" if passed else "retain-failed-benchmark-artifact",
        "specialist_training_status": "still-requires-frozen-suite-and-recipe" if passed else "blocked-benchmark-failed",
        "gate_id": gate["gate_id"],
        "suite_id": frontier["suite_id"],
        "thresholds": thresholds,
        "checks": checks,
        "passed": passed,
        "random": {
            "representative_accuracy": random_result["aggregate"]["exact_move_accuracy"],
            "calibrated_mean_accuracy": random_accuracy,
            "calibration_seeds": random_result["calibration"]["seeds"],
            "analytic_expected_accuracy": random_result["calibration"]["analytic_expected_accuracy"],
            "trace_hash": random_result["trace_hash"],
        },
        "locals": local_rows,
        "strongest_local_policy_id": strongest_local["policy_id"],
        "frontier": {
            "policy_id": frontier["model"]["policy_id"],
            "requested_model": frontier["model"]["requested_model"],
            "identity_state": frontier["model"]["identity_state"],
            **frontier["aggregate"],
            "margin_over_calibrated_random": frontier_accuracy - random_accuracy,
            "margin_over_strongest_local": frontier_accuracy - strongest_local["exact_move_accuracy"],
            "trace_hash": frontier["trace_hash"],
        },
        "match_demonstration": load(args.matches)["aggregate"] if args.matches else None,
        "limitations": [
            "This is a 20-position development gate, not the future frozen benchmark.",
            "The frontier identity is a mutable Codex model alias and cannot support a frozen public ceiling claim yet.",
            "Engine-generated tactical-gap positions test move selection but do not yet provide broad human-authored theme coverage.",
            "The paired local games are demonstrative only: notation forfeits and short repetitions make them unsuitable for Elo or capability ranking.",
            "No 30–50M specialist has been trained or evaluated.",
        ],
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), "passed": passed, "decision": result["decision"], "frontier_accuracy": frontier_accuracy, "strongest_local_accuracy": strongest_local["exact_move_accuracy"], "random_accuracy": random_accuracy}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
