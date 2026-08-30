#!/usr/bin/env python3
"""Score SQL candidate-selection predictions."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pred_to_id(row: dict, choice_row: dict) -> str | None:
    if "selected_id" in row:
        return str(row["selected_id"])
    if "predicted_choice_id" in row:
        return str(row["predicted_choice_id"])
    if "selected_index" in row:
        idx = int(row["selected_index"])
        choices = choice_row["choices"]
        return str(choices[idx]["id"]) if 0 <= idx < len(choices) else None
    if "predicted_choice" in row:
        idx = int(row["predicted_choice"])
        choices = choice_row["choices"]
        return str(choices[idx]["id"]) if 0 <= idx < len(choices) else None
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--choices", required=True)
    p.add_argument("--preds", required=True, help="JSONL with id plus selected_id or selected_index")
    p.add_argument("--out", default="", help="optional per-row scored JSONL")
    args = p.parse_args()

    choice_rows = read_jsonl(Path(args.choices))
    pred_rows = {str(r.get("id")): r for r in read_jsonl(Path(args.preds))}
    scored = []
    total = 0
    correct = 0
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    missing = 0

    for row in choice_rows:
        total += 1
        pred = pred_rows.get(str(row["id"]))
        selected_id = pred_to_id(pred, row) if pred else None
        ok = selected_id == row["answer_id"]
        correct += int(ok)
        missing += int(selected_id is None)
        for sl in row.get("slices", []):
            by_slice[sl]["n"] += 1
            by_slice[sl]["correct"] += int(ok)
        scored.append({
            "id": row["id"],
            "selected_id": selected_id,
            "answer_id": row["answer_id"],
            "correct": ok,
            "slices": row.get("slices", []),
        })

    if args.out:
        Path(args.out).write_text(
            "\n".join(json.dumps(r, separators=(",", ":"), sort_keys=True) for r in scored) + "\n"
        )

    summary = {
        "task": "sql_candidate_selection",
        "rows": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "missing_predictions": missing,
        "slices": {
            sl: {
                "rows": c["n"],
                "correct": c["correct"],
                "accuracy": round(c["correct"] / c["n"], 4) if c["n"] else 0.0,
            }
            for sl, c in sorted(by_slice.items())
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
