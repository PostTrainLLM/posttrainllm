#!/usr/bin/env python3
"""Record the deterministic random-legal chess puzzle baseline."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import chess

import chess_benchmark as benchmark


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--calibration-seeds", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite = benchmark.load_puzzle_suite(args.suite)
    result = benchmark.evaluate_puzzles(benchmark.RandomLegalPolicy(args.seed), suite)
    result["status"] = "development-random-baseline"
    result["random_seed"] = args.seed
    if not 100 <= args.calibration_seeds <= 100_000:
        raise ValueError("calibration seed count must be from 100 through 100000")
    accuracies = [
        benchmark.evaluate_puzzles(benchmark.RandomLegalPolicy(seed), suite)["aggregate"]["exact_move_accuracy"]
        for seed in range(args.calibration_seeds)
    ]
    ordered = sorted(accuracies)
    result["calibration"] = {
        "seeds": args.calibration_seeds,
        "mean_exact_move_accuracy": statistics.fmean(accuracies),
        "median_exact_move_accuracy": statistics.median(accuracies),
        "p95_exact_move_accuracy": ordered[int(0.95 * (len(ordered) - 1))],
        "analytic_expected_accuracy": statistics.fmean(
            len(puzzle["best_moves"]) / len(benchmark.legal_uci(chess.Board(puzzle["fen"])))
            for puzzle in suite["puzzles"]
        ),
    }
    result["trace_hash"] = benchmark.sha256_json({key: value for key, value in result.items() if key != "trace_hash"})
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
