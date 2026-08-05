#!/usr/bin/env python3
"""Evaluate an owned Python-reference chess checkpoint on compiled held-out rows."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import chess_benchmark as benchmark
import chess_sft_corpus as corpus
from chess_python_checkpoint import PythonCheckpointChessPolicy, sha256_file

SCHEMA_VERSION = "chess/python-checkpoint-eval/v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--model-ref", required=True)
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation", "test"), required=True)
    parser.add_argument("--maximum-rows", type=int)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--candidate-batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_rows(path: Path, split: str, maximum_rows: int | None) -> list[dict]:
    if maximum_rows is not None and maximum_rows < 1:
        raise ValueError("maximum_rows must be positive")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if row.get("schema_version") != corpus.ROW_SCHEMA:
                raise ValueError("unsupported compiled chess row")
            unhashed = {key: value for key, value in row.items() if key != "row_hash"}
            if row.get("row_hash") != benchmark.sha256_json(unhashed):
                raise ValueError("compiled chess row hash mismatch")
            if row.get("split") != split:
                continue
            if row.get("target") not in row.get("legal_moves", []):
                raise ValueError("compiled chess target is not legal")
            rows.append(row)
            if maximum_rows is not None and len(rows) >= maximum_rows:
                break
    if not rows:
        raise ValueError(f"no {split} rows selected")
    return rows


def main() -> int:
    args = parse_args()
    rows = load_rows(args.data, args.split, args.maximum_rows)
    policy = PythonCheckpointChessPolicy(
        args.checkpoint,
        args.model_ref,
        args.policy_id,
        device=args.device,
        candidate_batch_size=args.candidate_batch_size,
    )
    decisions = []
    for row in rows:
        chosen = policy.choose({"fen": row["fen"]}, row["legal_moves"])
        ranked = sorted(policy.last_scores, key=lambda move: (policy.last_scores[move], move), reverse=True)
        target = row["target"]
        strongest_alternative = max(
            (score for move, score in policy.last_scores.items() if move != target),
            default=None,
        )
        decisions.append(
            {
                "row_id": row["id"],
                "target": target,
                "chosen": chosen,
                "exact": chosen == target,
                "legal": chosen in row["legal_moves"],
                "target_rank": ranked.index(target) + 1,
                "target_log_score": policy.last_scores[target],
                "target_margin_over_strongest_alternative": (
                    policy.last_scores[target] - strongest_alternative
                    if strongest_alternative is not None
                    else None
                ),
            }
        )
    exact = sum(row["exact"] for row in decisions)
    legal = sum(row["legal"] for row in decisions)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "candidate-evidence",
        "policy": {
            "policy_id": args.policy_id,
            "model_ref": args.model_ref,
            "revision": policy.revision,
            "checkpoint_sha256": policy.checkpoint_sha256,
        },
        "data": {
            "path": str(args.data),
            "sha256": sha256_file(args.data),
            "split": args.split,
        },
        "runtime": {
            "python": platform.python_version(),
            "device": policy.device,
            "model_load_time_ms": policy.model_load_time_ms,
        },
        "aggregate": {
            "rows": len(decisions),
            "exact_target_rate": exact / len(decisions),
            "executed_legal_rate": legal / len(decisions),
        },
        "decisions": decisions,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
