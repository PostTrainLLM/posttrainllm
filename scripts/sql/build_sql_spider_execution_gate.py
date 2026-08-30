#!/usr/bin/env python3
"""Build a Spider-style public SQL execution gate.

Input is a local Spider checkout/download with:

  dev.json
  database/<db_id>/<db_id>.sqlite

The output JSONL is compatible with `posttrainllm eval-sql`: generation should add a
`predicted_sql` field, and scoring uses `--db-dir <spider-root>`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


SYSTEM = (
    "You are a text-to-SQL model. Return only one SQLite SELECT query, no markdown."
)


def jdump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def load_examples(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a JSON list")
    return data


def db_path(root: Path, db_id: str) -> Path:
    return root / "database" / db_id / f"{db_id}.sqlite"


def schema_text(sqlite_path: Path) -> str:
    with sqlite3.connect(sqlite_path) as db:
        rows = db.execute(
            """
            select sql
            from sqlite_master
            where type = 'table'
              and name not like 'sqlite_%'
              and sql is not null
            order by name
            """
        ).fetchall()
    return " ".join(str(row[0]).strip().rstrip(";") + ";" for row in rows)


def clean_sql(sql: str) -> str:
    sql = " ".join(sql.strip().split())
    if sql and not sql.endswith(";"):
        sql += ";"
    return sql


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--spider-root",
        required=True,
        help="Directory containing dev.json and database/.",
    )
    ap.add_argument(
        "--split", default="dev.json", help="Split JSON path relative to --spider-root."
    )
    ap.add_argument("--out", required=True, help="Output directory.")
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum rows to emit; 0 means all usable rows.",
    )
    ap.add_argument(
        "--select-only",
        action="store_true",
        default=True,
        help="Keep only SELECT gold queries.",
    )
    ap.add_argument("--include-non-select", dest="select_only", action="store_false")
    args = ap.parse_args()

    root = Path(args.spider_root)
    split_path = root / args.split
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    examples = load_examples(split_path)
    schemas: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    skipped: dict[str, int] = {"missing_db": 0, "missing_fields": 0, "non_select": 0}

    for idx, ex in enumerate(examples):
        db_id = str(ex.get("db_id", "")).strip()
        question = str(ex.get("question", "")).strip()
        gold = clean_sql(str(ex.get("query", ex.get("gold_sql", ""))))
        if not db_id or not question or not gold:
            skipped["missing_fields"] += 1
            continue
        if args.select_only and not gold.lower().startswith("select "):
            skipped["non_select"] += 1
            continue
        sqlite_path = db_path(root, db_id)
        if not sqlite_path.exists():
            skipped["missing_db"] += 1
            continue
        if db_id not in schemas:
            schemas[db_id] = schema_text(sqlite_path)
        schema = schemas[db_id]
        rows.append(
            {
                "id": f"spider-{Path(args.split).stem}-{idx:05d}",
                "source": "spider",
                "db_id": db_id,
                "question": question,
                "schema": schema,
                "prompt": f"{SYSTEM} Schema: {schema} Question: {question}",
                "gold_sql": gold,
                "db": str(Path("database") / db_id / f"{db_id}.sqlite"),
            }
        )
        if args.limit and len(rows) >= args.limit:
            break

    if not rows:
        raise SystemExit(f"no usable Spider rows from {split_path}; skipped={skipped}")

    (out / "dev.jsonl").write_text(
        "\n".join(jdump(r) for r in rows) + "\n", encoding="utf-8"
    )
    (out / "manifest.json").write_text(
        jdump(
            {
                "dataset_id": "spider-execution",
                "source": "Spider text-to-SQL benchmark",
                "spider_root": str(root),
                "split": args.split,
                "rows": len(rows),
                "db_count": len({r["db_id"] for r in rows}),
                "metric": "execution_accuracy_sqlite",
                "scorer": "posttrainllm eval-sql --db-dir <spider-root>",
                "select_only": args.select_only,
                "skipped": skipped,
                "notes": [
                    "Requires local Spider SQLite databases; no DB bundle is committed.",
                    "Rows are eval-sql compatible after generation adds predicted_sql.",
                    "Schema text is introspected from sqlite_master to avoid stale tables metadata.",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} Spider execution rows to {out / 'dev.jsonl'}")


if __name__ == "__main__":
    main()
