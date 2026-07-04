#!/usr/bin/env python3
"""Report SQL eval metrics by semantic slice."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def infer_slices(row: dict) -> list[str]:
    sql = str(row.get("gold_sql") or row.get("answer_sql") or "").lower()
    slices = [f"domain:{row.get('domain', 'unknown')}"]
    slices.append("join" if " join " in sql else "single_table")
    if any(fn in sql for fn in ("count(", "sum(", "avg(", "min(", "max(")):
        slices.append("aggregate")
    if " where " in sql:
        slices.append("filter")
    if " group by " in sql:
        slices.append("group_by")
    if " order by " in sql:
        slices.append("order_by")
    if row.get("clean") is not None:
        slices.append("clean_output" if row.get("clean") else "unclean_output")
    return slices


def as_bool(row: dict, keys: tuple[str, ...]) -> bool:
    return any(bool(row.get(k)) for k in keys)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("rows", help="eval row trace JSONL")
    p.add_argument("--out", default="", help="optional JSON summary path")
    args = p.parse_args()

    rows = read_jsonl(Path(args.rows))
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    overall = Counter()
    for row in rows:
        exec_ok = as_bool(row, ("exec_match", "execution_match", "correct"))
        exact_ok = as_bool(row, ("exact_match",))
        overall["n"] += 1
        overall["exec"] += int(exec_ok)
        overall["exact"] += int(exact_ok)
        for sl in infer_slices(row):
            by_slice[sl]["n"] += 1
            by_slice[sl]["exec"] += int(exec_ok)
            by_slice[sl]["exact"] += int(exact_ok)

    def summarize(c: Counter[str]) -> dict:
        n = c["n"]
        return {
            "rows": n,
            "execution_accuracy": round(c["exec"] / n, 4) if n else 0.0,
            "exact_match": round(c["exact"] / n, 4) if n else 0.0,
        }

    summary = {
        "overall": summarize(overall),
        "slices": {name: summarize(c) for name, c in sorted(by_slice.items())},
    }
    text = json.dumps(summary, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
