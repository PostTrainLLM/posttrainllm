#!/usr/bin/env python3
"""Aggregate candidate-only chess model runs without changing the frozen labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def decision_legal(decision: dict[str, Any]) -> bool:
    return bool(decision.get("legal", decision.get("raw_legal", False)))


def aggregate_run(paths: list[Path]) -> dict[str, Any]:
    documents = [load(path) for path in paths]
    first = documents[0]
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        for decision in document["decisions"]:
            puzzle_id = decision["puzzle_id"]
            if puzzle_id in seen:
                raise ValueError(f"duplicate puzzle id for one policy: {puzzle_id}")
            seen.add(puzzle_id)
            decisions.append(decision)

    puzzles = len(decisions)
    legal = sum(decision_legal(d) for d in decisions)
    exact = sum(bool(d["exact"]) for d in decisions)
    provider_failures = sum(bool(d.get("failure")) for d in decisions)
    costs = [doc.get("aggregate", {}).get("total_cost_usd") for doc in documents]
    numeric_costs = [cost for cost in costs if isinstance(cost, (int, float))]
    if not numeric_costs:
        numeric_costs = [
            doc.get("model", {}).get("cost_usd")
            for doc in documents
            if isinstance(doc.get("model", {}).get("cost_usd"), (int, float))
        ]
    latencies = [d.get("latency_ms") for d in decisions if isinstance(d.get("latency_ms"), (int, float))]
    model = first.get("model", {})
    if not model and first.get("policy"):
        model = {
            "policy_id": first["policy"]["policy_id"],
            "requested_model": first["policy"]["policy_id"],
            "backend": "local-baseline",
        }
    result = {
        "policy_id": model.get("policy_id", model.get("requested_model", "unknown")),
        "requested_model": model.get("requested_model", "unknown"),
        "backend": model.get("backend", "unknown"),
        "track": first.get("track", "candidate-baseline"),
        "source_artifacts": [str(path) for path in paths],
        "puzzles": puzzles,
        "exact": exact,
        "exact_move_accuracy": exact / puzzles if puzzles else 0.0,
        "exact_given_execution": exact / legal if legal else None,
        "raw_legal": legal,
        "raw_legal_rate": legal / puzzles if puzzles else 0.0,
        "executed": legal,
        "execution_rate": legal / puzzles if puzzles else 0.0,
        "executed_legal_rate": 1.0 if legal else None,
        "redirect_required": puzzles - legal,
        "redirect_rate": (puzzles - legal) / puzzles if puzzles else 0.0,
        "provider_failures": provider_failures,
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "total_cost_usd": sum(numeric_costs) if numeric_costs else None,
        "decisions": decisions,
    }
    calibration = first.get("calibration")
    if isinstance(calibration, dict):
        result["calibration"] = calibration
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--deep-verification", type=Path, required=True)
    parser.add_argument("--run", action="append", nargs="+", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    suite = load(args.suite)
    verification = load(args.deep_verification)
    gold = {puzzle["id"]: puzzle["best_moves"] for puzzle in suite["puzzles"]}
    runs = [aggregate_run(paths) for paths in args.run]

    choices: dict[str, dict[str, str | None]] = {}
    for run in runs:
        for decision in run.pop("decisions"):
            choices.setdefault(decision["puzzle_id"], {})[run["policy_id"]] = decision.get("parsed_move")

    disagreements = []
    for puzzle_id, by_policy in choices.items():
        non_null = [move for move in by_policy.values() if move is not None]
        if len(set(non_null)) > 1:
            disagreements.append(
                {"puzzle_id": puzzle_id, "stockfish_best_moves": gold[puzzle_id], "model_moves": by_policy}
            )

    output = {
        "schema_version": "chess/candidate-model-matrix/v1",
        "status": "candidate-only-not-a-frozen-benchmark",
        "suite_id": suite["suite_id"],
        "label_authority": {
            "source": "Stockfish",
            "models_are_secondary_reviewers_not_label_authorities": True,
            "deep_verification": verification["aggregate"],
        },
        "legality_contract": {
            "raw_legal_rate_measures_model_or_provider_output": True,
            "execution_membership_check_required": True,
            "illegal_missing_or_failed_outputs": "abstain-or-redirect",
            "executed_moves_must_be_legal": True,
        },
        "runs": runs,
        "cross_model_disagreements": disagreements,
    }
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"))
    output["trace_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "runs": len(runs), "disagreements": len(disagreements)}))


if __name__ == "__main__":
    main()
