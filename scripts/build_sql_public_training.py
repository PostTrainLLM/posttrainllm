#!/usr/bin/env python3
"""Build public-style SQL SFT/preference data from Hugging Face datasets.

This is the next step after the tiny synthetic SQL POC: train on
schema-grounded public data while holding out a non-overlapping public slice.

Default source is b-mc2/sql-create-context because it is lightweight and ships
question + CREATE TABLE context + SQL. The output shape matches tinygpt's SFT
reader and the existing exact-match public scorer.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from datasets import load_dataset


SYSTEM = "You are a text-to-SQL model. Return only one SQLite SELECT query, no markdown."


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def normalize_completion(sql: str) -> str:
    sql = re.sub(r"\s+", " ", sql.strip())
    return sql if sql.endswith(";") else sql + ";"


def prompt(context: str, question: str) -> str:
    return f"{SYSTEM} Schema: {context.strip()}. Question: {question.strip()}"


def curriculum(sql: str, context: str) -> str:
    s = sql.lower()
    tables = len(re.findall(r"\bcreate\s+table\b", context, flags=re.I))
    if " join " in s:
        return "join"
    if any(k in s for k in [" group by ", " having "]):
        return "group_having"
    if any(k in s for k in [" order by ", " limit "]):
        return "order_limit"
    if re.search(r"\b(count|avg|sum|min|max)\s*\(", s):
        return "aggregate"
    if " where " in s:
        return "filter"
    if tables > 1:
        return "multi_table_no_join"
    return "projection"


def usable(sql: str, context: str, question: str, max_chars: int) -> bool:
    if not sql or not context or not question:
        return False
    s = sql.strip().lower()
    if not s.startswith("select "):
        return False
    if any(tok in s for tok in [" union ", " intersect ", " except "]):
        return False
    return len(prompt(context, question)) <= max_chars


def bad_completion(sql: str, idx: int) -> tuple[str, str]:
    clean = normalize_completion(sql)
    variants = [
        ("sql_prose_wrapped", f"Answer: {clean}"),
        ("sql_markdown_fence", f"```sql\n{clean}\n```"),
        ("sql_explanation_suffix", f"{clean} This query answers the question."),
        ("sql_missing_semicolon", clean.rstrip(";")),
    ]
    return variants[idx % len(variants)]


def read_bmc2(scan: int) -> list[dict[str, str]]:
    ds = load_dataset("b-mc2/sql-create-context", split=f"train[:{scan}]")
    rows: list[dict[str, str]] = []
    for idx, row in enumerate(ds):
        rows.append(
            {
                "source": "b-mc2/sql-create-context",
                "source_index": str(idx),
                "question": str(row["question"]).strip(),
                "context": str(row["context"]).strip(),
                "sql": str(row["answer"]).strip(),
            }
        )
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="evals/sql-public-bmc2-train")
    p.add_argument("--scan", type=int, default=8000)
    p.add_argument("--dev-limit", type=int, default=64)
    p.add_argument("--train-limit", type=int, default=512)
    p.add_argument("--dev-start", type=int, default=0)
    p.add_argument("--train-start", type=int, default=2000)
    p.add_argument("--max-prompt-chars", type=int, default=1800)
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw_rows = read_bmc2(args.scan)

    usable_rows = []
    for row in raw_rows:
        if usable(row["sql"], row["context"], row["question"], args.max_prompt_chars):
            row = dict(row)
            row["curriculum"] = curriculum(row["sql"], row["context"])
            row["completion"] = normalize_completion(row["sql"])
            usable_rows.append(row)

    def take_rows(start: int, limit: int) -> list[dict[str, str]]:
        rows = [r for r in usable_rows if int(r["source_index"]) >= start]
        return rows[:limit]

    dev_src = take_rows(args.dev_start, args.dev_limit)
    dev_ids = {r["source_index"] for r in dev_src}
    train_src = [r for r in take_rows(args.train_start, args.train_limit * 2) if r["source_index"] not in dev_ids]
    train_src = train_src[: args.train_limit]

    if len(dev_src) < args.dev_limit:
        raise SystemExit(f"only found {len(dev_src)} dev rows; requested {args.dev_limit}")
    if len(train_src) < args.train_limit:
        raise SystemExit(f"only found {len(train_src)} train rows; requested {args.train_limit}")

    train_rows = []
    pref_rows = []
    for i, row in enumerate(train_src):
        row_id = f"bmc2-train-{int(row['source_index']):05d}"
        instr = prompt(row["context"], row["question"])
        train_rows.append(
            {
                "id": row_id,
                "source": row["source"],
                "source_index": int(row["source_index"]),
                "curriculum": row["curriculum"],
                "instruction": instr,
                "response": row["completion"],
            }
        )
        failure_type, rejected = bad_completion(row["completion"], i)
        pref_rows.append(
            {
                "id": row_id,
                "source": row["source"],
                "curriculum": row["curriculum"],
                "prompt": instr,
                "chosen": row["completion"],
                "rejected": rejected,
                "failure_type": failure_type,
            }
        )

    dev_rows = [
        {
            "id": f"bmc2-dev-{int(row['source_index']):05d}",
            "source": row["source"],
            "source_index": int(row["source_index"]),
            "curriculum": row["curriculum"],
            "question": row["question"],
            "schema": row["context"],
            "prompt": prompt(row["context"], row["question"]),
            "gold_sql": row["completion"],
        }
        for row in dev_src
    ]

    counts = collections.Counter(r["curriculum"] for r in train_rows)
    dev_counts = collections.Counter(r["curriculum"] for r in dev_rows)
    (out / "train.jsonl").write_text("\n".join(jdump(r) for r in train_rows) + "\n")
    (out / "dev.jsonl").write_text("\n".join(jdump(r) for r in dev_rows) + "\n")
    (out / "preferences.jsonl").write_text("\n".join(jdump(r) for r in pref_rows) + "\n")
    (out / "manifest.json").write_text(
        jdump(
            {
                "source": "b-mc2/sql-create-context",
                "scan": args.scan,
                "train_start": args.train_start,
                "dev_start": args.dev_start,
                "train_rows": len(train_rows),
                "dev_rows": len(dev_rows),
                "preference_rows": len(pref_rows),
                "metric": "normalized_exact_sql",
                "train_curriculum": dict(sorted(counts.items())),
                "dev_curriculum": dict(sorted(dev_counts.items())),
                "non_overlap_key": "source_index",
            }
        )
        + "\n"
    )
    print(
        f"wrote train={len(train_rows)} dev={len(dev_rows)} prefs={len(pref_rows)} "
        f"to {out}"
    )


if __name__ == "__main__":
    main()
