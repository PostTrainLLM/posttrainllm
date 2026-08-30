#!/usr/bin/env python3
"""Score public text-to-SQL predictions by normalized exact SQL match."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def normalize_sql(sql: str) -> str:
    s = sql.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", s, flags=re.I | re.S)
    if fence:
        s = fence.group(1).strip()
    select = re.search(r"\bselect\b", s, flags=re.I)
    if select:
        s = s[select.start() :]
    semi = s.find(";")
    if semi >= 0:
        s = s[: semi + 1]
    s = s.rstrip(";").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s*([()=<>])\s*", r"\1", s)
    return s


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("preds")
    p.add_argument("--out")
    args = p.parse_args()

    rows = []
    for idx, line in enumerate(Path(args.preds).read_text().splitlines()):
        if not line.strip():
            continue
        row = json.loads(line)
        pred = row.get("predicted_sql") or row.get("output") or ""
        gold = row.get("gold_sql") or ""
        pred_norm = normalize_sql(str(pred))
        gold_norm = normalize_sql(str(gold))
        rows.append(
            {
                "index": idx,
                "id": row.get("id", idx),
                "question": row.get("question", ""),
                "predicted_sql": pred,
                "gold_sql": gold,
                "normalized_predicted_sql": pred_norm,
                "normalized_gold_sql": gold_norm,
                "exact_match": pred_norm == gold_norm,
            }
        )

    if not rows:
        raise SystemExit("no rows")
    exact = sum(1 for r in rows if r["exact_match"]) / len(rows)
    print(f"sql-public-exact: exact_match={exact:.3f} (n={len(rows)})")
    if args.out:
        Path(args.out).write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")


if __name__ == "__main__":
    main()
