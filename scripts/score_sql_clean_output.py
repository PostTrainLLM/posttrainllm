#!/usr/bin/env python3
"""Clean-SQL raw-output metric for the qwen06-sql-hygiene-dpo-v1 gate.

A completion is "clean" iff the raw generated text is a single bare SQL
statement (docs/NEXT.md frozen target definition):

- starts with SELECT (case-insensitive, after stripping whitespace)
- no markdown fence anywhere
- at most one `;`, with nothing but whitespace after it

Prose prefixes ("Answer: select ...") fail the SELECT check; trailing
explanations fail the nothing-after-`;` check; fenced blocks fail the
fence check. Execution accuracy is scored separately by `tinygpt
eval-sql`; this metric only judges output hygiene.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def is_clean(text: str) -> tuple[bool, str]:
    s = text.strip()
    if not s.lower().startswith("select"):
        return False, "no_select_prefix"
    if "```" in text:
        return False, "markdown_fence"
    if s.count(";") > 1:
        return False, "multiple_statements"
    if ";" in s and not s.endswith(";"):
        return False, "text_after_semicolon"
    return True, "clean"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("preds", help="predictions .jsonl")
    p.add_argument("--field", default="predicted_sql", help="raw completion field")
    p.add_argument("--out", default="", help="optional per-row labels .jsonl")
    args = p.parse_args()

    rows = [
        json.loads(line)
        for line in Path(args.preds).read_text().splitlines()
        if line.strip()
    ]
    labeled = []
    clean = 0
    reasons: dict[str, int] = {}
    for row in rows:
        ok, reason = is_clean(str(row.get(args.field) or ""))
        clean += ok
        reasons[reason] = reasons.get(reason, 0) + 1
        labeled.append({"id": row.get("id"), "clean": ok, "reason": reason})

    if args.out:
        Path(args.out).write_text(
            "\n".join(json.dumps(r, separators=(",", ":")) for r in labeled) + "\n"
        )
    rate = clean / len(rows) if rows else 0.0
    print(
        json.dumps(
            {"rows": len(rows), "clean": clean, "clean_rate": round(rate, 3), "reasons": reasons}
        )
    )


if __name__ == "__main__":
    main()
