#!/usr/bin/env python3
"""Parse and validate a raw Devin GLM batch response without repairing moves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chess

import chess_benchmark as benchmark

SCHEMA_VERSION = "chess/devin-batch-result/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--raw-log", type=Path, required=True)
    parser.add_argument("--policy-id", default="devin-glm-5.2-candidate-v1")
    parser.add_argument("--model", default="glm-5.2")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def extract_moves_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    candidates = []
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("moves"), list):
            candidates.append(value)
    if not candidates:
        raise ValueError("Devin output contains no moves JSON object")
    return max(candidates, key=lambda value: len(value["moves"]))


def main() -> int:
    args = parse_args()
    suite = benchmark.load_puzzle_suite(args.suite)
    if args.offset < 0 or not 1 <= args.limit or args.offset + args.limit > len(suite["puzzles"]):
        raise ValueError("batch bounds are outside suite")
    puzzles = suite["puzzles"][args.offset : args.offset + args.limit]
    raw_log = args.raw_log.read_text(encoding="utf-8")
    failure = None
    try:
        response = extract_moves_object(raw_log)
        raw_moves = response["moves"]
    except ValueError as exc:
        response = None
        raw_moves = []
        failure = str(exc)
    by_id: dict[str, Any] = {}
    duplicate_ids = []
    malformed_rows = 0
    for row in raw_moves:
        if not isinstance(row, dict) or set(row) != {"puzzle_id", "move"}:
            malformed_rows += 1
            continue
        puzzle_id = row["puzzle_id"]
        if not isinstance(puzzle_id, str) or not isinstance(row["move"], str):
            malformed_rows += 1
            continue
        if puzzle_id in by_id:
            duplicate_ids.append(puzzle_id)
        by_id[puzzle_id] = row["move"]
    decisions = []
    for index, puzzle in enumerate(puzzles):
        board = chess.Board(puzzle["fen"])
        raw = by_id.get(puzzle["id"])
        parsed = None
        row_failure = None
        try:
            parsed = benchmark.parse_strict_uci(raw, board).uci()
        except Exception as exc:
            row_failure = f"{type(exc).__name__}: {exc}"
        decisions.append(
            {
                "index": index,
                "puzzle_id": puzzle["id"],
                "fen": puzzle["fen"],
                "legal_moves": list(benchmark.legal_uci(board)),
                "best_moves": puzzle["best_moves"],
                "raw_output": raw,
                "parsed_move": parsed,
                "raw_legal": parsed is not None,
                "exact": parsed in puzzle["best_moves"] if parsed is not None else False,
                "failure": row_failure,
                "execution": "validated-legal" if parsed is not None else "abstain-or-redirect-required",
            }
        )
    legal = sum(row["raw_legal"] for row in decisions)
    exact = sum(row["exact"] for row in decisions)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "candidate-verification-only-not-frozen-evidence",
        "suite_id": suite["suite_id"],
        "track": "strict-batch-with-legal-membership-validator",
        "batch": {"offset": args.offset, "limit": args.limit},
        "model": {
            "policy_id": args.policy_id,
            "requested_model": args.model,
            "resolved_model": args.model,
            "backend": "devin-cli",
            "cost_usd": 0.0,
            "constraint_state": "prompted-legal-set-not-logit-constrained",
        },
        "response_validation": {
            "batch_failure": failure,
            "returned_rows": len(raw_moves),
            "malformed_rows": malformed_rows,
            "duplicate_ids": sorted(set(duplicate_ids)),
            "unexpected_ids": sorted(set(by_id) - {puzzle["id"] for puzzle in puzzles}),
        },
        "aggregate": {
            "puzzles": len(decisions),
            "exact": exact,
            "exact_move_accuracy": exact / len(decisions),
            "raw_legal": legal,
            "raw_legal_rate": legal / len(decisions),
            "executed_legal_rate": 1.0,
            "abstention_or_redirect_required": len(decisions) - legal,
            "abstention_or_redirect_rate": (len(decisions) - legal) / len(decisions),
        },
        "decisions": decisions,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
