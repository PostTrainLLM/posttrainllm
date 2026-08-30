#!/usr/bin/env python3
"""Build a tiny public text-to-SQL benchmark slice from Hugging Face.

The factory's synthetic SQL fixture is useful for the closed loop, but we need a
public sanity check before claiming the specialist generalizes. This script
samples b-mc2/sql-create-context, a public Spider/WikiSQL-derived dataset with
question, CREATE TABLE context, and gold SQL.

It intentionally produces an exact-match benchmark, not an execution benchmark:
the HF dataset ships schema text, not populated SQLite DBs.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from datasets import load_dataset


SYSTEM = "You are a text-to-SQL model. Return only one SQLite SELECT query, no markdown."


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def simple_enough(sql: str, context: str) -> bool:
    """Keep examples close to the current POC's capability envelope."""
    s = sql.strip().lower()
    if not s.startswith("select "):
        return False
    if any(tok in s for tok in [" join ", " union ", " intersect ", " except ", " over "]):
        return False
    if s.count("select ") > 1:
        return False
    table_count = len(re.findall(r"\bcreate\s+table\b", context, flags=re.I))
    return table_count == 1


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="evals/sql-public-bmc2")
    p.add_argument("--limit", type=int, default=24)
    p.add_argument("--scan", type=int, default=2000)
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    ds = load_dataset("b-mc2/sql-create-context", split=f"train[:{args.scan}]")
    rows = []
    for idx, row in enumerate(ds):
        gold = str(row["answer"]).strip()
        context = str(row["context"]).strip()
        if not simple_enough(gold, context):
            continue
        question = str(row["question"]).strip()
        rows.append(
            {
                "id": f"bmc2-{idx:05d}",
                "source": "b-mc2/sql-create-context",
                "question": question,
                "schema": context,
                "prompt": f"{SYSTEM} Schema: {context}. Question: {question}",
                "gold_sql": gold,
            }
        )
        if len(rows) >= args.limit:
            break

    if len(rows) < args.limit:
        raise SystemExit(f"only found {len(rows)} usable rows; requested {args.limit}")

    (out / "dev.jsonl").write_text("\n".join(jdump(r) for r in rows) + "\n")
    (out / "manifest.json").write_text(
        jdump(
            {
                "dataset": "b-mc2/sql-create-context",
                "split": f"train[:{args.scan}]",
                "limit": args.limit,
                "metric": "normalized_exact_sql",
                "notes": [
                    "public HF dataset derived from Spider/WikiSQL",
                    "schema-grounded exact-match only; no SQLite DB contents shipped",
                    "filtered to single-table SELECT examples for first public sanity check",
                ],
            }
        )
        + "\n"
    )
    print(f"wrote {len(rows)} rows to {out / 'dev.jsonl'}")


if __name__ == "__main__":
    main()
