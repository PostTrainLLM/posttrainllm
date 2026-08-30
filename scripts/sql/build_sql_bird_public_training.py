#!/usr/bin/env python3
"""Build a BIRD-augmented public SQL SFT corpus.

The b-mc2 public adapter beat the tiny T5 baseline, but its misses are mostly
hard join/subquery/generalization rows. BIRD train rows carry richer schemas,
evidence, and multi-table SQL, so this builder adds a bounded SELECT-only BIRD
slice to the existing b-mc2 join-weighted curriculum.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from datasets import load_dataset


SYSTEM = (
    "You are a text-to-SQL model. Return only one SQLite SELECT query, no markdown."
)


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_sql(sql: str) -> str:
    clean = re.sub(r"\s+", " ", sql.strip())
    return clean if clean.endswith(";") else clean + ";"


def normalize_schema(schema: str, max_chars: int) -> str:
    schema = re.sub(r"\s+", " ", schema.strip())
    return (
        schema[:max_chars].rsplit(";", 1)[0] + ";"
        if len(schema) > max_chars
        else schema
    )


def prompt(schema: str, question: str, evidence: str = "") -> str:
    parts = [SYSTEM, f"Schema: {schema.strip()}"]
    if evidence.strip():
        parts.append(f"Evidence: {evidence.strip()}")
    parts.append(f"Question: {question.strip()}")
    return " ".join(parts)


def curriculum(sql: str, schema: str) -> str:
    s = f" {sql.lower()} "
    tables = len(re.findall(r"\bcreate\s+table\b", schema, flags=re.I))
    if " join " in s:
        return "join"
    if any(k in s for k in [" not in ", " exists ", " in (select "]):
        return "subquery"
    if any(k in s for k in [" group by ", " having "]):
        return "group_having"
    if any(k in s for k in [" order by ", " limit "]):
        return "order_limit"
    if re.search(r"\b(count|avg|sum|min|max|round)\s*\(", s):
        return "aggregate"
    if " where " in s:
        return "filter"
    if tables > 1:
        return "multi_table_no_join"
    return "projection"


def usable(sql: str, schema: str, question: str, max_prompt_chars: int) -> bool:
    if not sql or not schema or not question:
        return False
    s = sql.strip().lower()
    if not s.startswith("select "):
        return False
    blocked = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "create ",
        "alter ",
        "pragma ",
    ]
    if any(tok in s for tok in blocked):
        return False
    return len(prompt(schema, question)) <= max_prompt_chars


def weighted_copy(row: dict, repeat: int, suffix: str) -> list[dict]:
    out = []
    for idx in range(repeat):
        r = dict(row)
        r["id"] = f"{row.get('id', suffix)}-{suffix}-w{idx}"
        out.append(r)
    return out


def load_bird_rows(
    limit: int, max_prompt_chars: int, max_schema_chars: int
) -> list[dict]:
    ds = load_dataset("xu3kev/BIRD-SQL-data-train", split="train")
    rows: list[dict] = []
    for idx, row in enumerate(ds):
        sql = str(row["SQL"]).strip()
        schema = normalize_schema(str(row["schema"]), max_schema_chars)
        question = str(row["question"]).strip()
        evidence = str(row.get("evidence") or "").strip()
        if not usable(sql, schema, question, max_prompt_chars):
            continue
        cur = curriculum(sql, schema)
        # Bias the bounded slice toward rows that match the observed public
        # failure surface: joins, subqueries, grouping, and distinct/count.
        repeat = {
            "join": 3,
            "subquery": 3,
            "group_having": 2,
            "aggregate": 2,
        }.get(cur, 1)
        base = {
            "id": f"bird-train-{idx:05d}",
            "source": "xu3kev/BIRD-SQL-data-train",
            "source_index": idx,
            "db_id": row.get("db_id"),
            "curriculum": cur,
            "instruction": prompt(schema, question, evidence),
            "response": normalize_sql(sql),
        }
        rows.extend(weighted_copy(base, repeat, "bird"))
        if len(rows) >= limit:
            return rows[:limit]
    return rows


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--bmc2-train",
        default="evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl",
    )
    p.add_argument("--out", default="evals/sql-public-bird-bmc2-v5")
    p.add_argument("--bird-limit", type=int, default=4096)
    p.add_argument("--bmc2-limit", type=int, default=4096)
    p.add_argument("--max-prompt-chars", type=int, default=2600)
    p.add_argument("--max-schema-chars", type=int, default=1800)
    args = p.parse_args()

    bmc2_rows = read_jsonl(Path(args.bmc2_train))[: args.bmc2_limit]
    bird_rows = load_bird_rows(
        args.bird_limit, args.max_prompt_chars, args.max_schema_chars
    )
    rows = bmc2_rows + bird_rows

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "train.jsonl").write_text("\n".join(jdump(r) for r in rows) + "\n")
    counts = collections.Counter(r.get("source", "unknown") for r in rows)
    cur = collections.Counter(r.get("curriculum", "unknown") for r in rows)
    manifest = {
        "bmc2_train": args.bmc2_train,
        "bmc2_limit": args.bmc2_limit,
        "bird_source": "xu3kev/BIRD-SQL-data-train",
        "bird_limit": args.bird_limit,
        "max_prompt_chars": args.max_prompt_chars,
        "max_schema_chars": args.max_schema_chars,
        "rows": len(rows),
        "source_counts": dict(sorted(counts.items())),
        "curriculum_counts": dict(sorted(cur.items())),
        "gate": {
            "public_exact_min": 0.531,
            "synthetic_execution_target": 0.860,
            "routing_required": True,
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(rows)} rows to {out / 'train.jsonl'}")
    print(json.dumps(manifest["source_counts"], sort_keys=True))
    print(json.dumps(manifest["curriculum_counts"], sort_keys=True))


if __name__ == "__main__":
    main()
