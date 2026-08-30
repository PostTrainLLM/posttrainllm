#!/usr/bin/env python3
"""Render a qualitative SQL trace review markdown file.

This complements pass/fail metrics with the failure modes that matter for
post-training: reward hacking, hallucinated schema, fake reasoning/prose, and
format collapse.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def tables_and_columns(prompt: str) -> set[str]:
    # Works for compact prompts like "Schema: departments(id, name); ..."
    out: set[str] = set()
    m = re.search(r"schema:\s*(.*?)\s*question:", prompt, flags=re.I | re.S)
    schema = m.group(1) if m else prompt
    for table, cols in re.findall(r"([A-Za-z_][\w]*)\s*\(([^)]*)\)", schema):
        out.add(table.lower())
        for col in cols.split(","):
            name = col.strip().split()[0] if col.strip() else ""
            if name:
                out.add(name.lower())
                out.add(f"{table.lower()}.{name.lower()}")
    return out


def identifiers(sql: str) -> set[str]:
    words = set(re.findall(r"[A-Za-z_][\w]*", sql.lower()))
    return {w for w in words if w not in {
        "select", "from", "where", "join", "on", "and", "or", "as", "count",
        "sum", "avg", "min", "max", "group", "by", "order", "limit", "desc",
        "asc", "distinct", "having", "like", "in", "not", "null",
    }}


def label(row: dict) -> str:
    raw = str(row.get("predicted_sql") or row.get("output") or "")
    scored = str(row.get("scored_sql") or raw)
    low = raw.lower()
    if bool(row.get("exec_match")) or bool(row.get("correct")):
        if raw.strip().lower().startswith("select") and "```" not in raw:
            return "clean_success"
        return "extractor_success_unclean_raw"
    if not raw.strip().lower().startswith("select") and "select" not in low:
        return "no_select_or_format_collapse"
    if "```" in raw or "answer:" in low or "explanation" in low:
        return "prose_or_markdown_wrapped"
    allowed = tables_and_columns(str(row.get("prompt") or ""))
    if allowed:
        extra = identifiers(scored) - allowed
        if extra:
            return "hallucinated_schema"
    if " join " in str(row.get("gold_sql") or "").lower() and " join " not in scored.lower():
        return "missing_join"
    if " join " not in str(row.get("gold_sql") or "").lower() and " join " in scored.lower():
        return "unneeded_join"
    return "wrong_result"


def clip(text: str, n: int = 220) -> str:
    one = " ".join(str(text).split())
    return one if len(one) <= n else one[: n - 3] + "..."


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--rows", required=True, help="eval rows or prediction rows JSONL")
    p.add_argument("--out", required=True)
    p.add_argument("--max-examples", type=int, default=3)
    args = p.parse_args()

    rows = read_jsonl(Path(args.rows))
    labels = [(row, label(row)) for row in rows]
    counts = Counter(lab for _, lab in labels)
    n = len(rows)
    success = sum(1 for row, _ in labels if bool(row.get("exec_match")) or bool(row.get("correct")))

    lines = [
        "# SQL Trace Review",
        "",
        "## Summary",
        "",
        f"- Rows reviewed: {n}",
        f"- Execution/correct successes: {success}",
        f"- Success rate: {success / n:.3f}" if n else "- Success rate: 0.000",
        "",
        "## Failure Taxonomy",
        "",
        "| Label | Rows |",
        "|---|---:|",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"| `{key}` | {value} |")

    lines.extend([
        "",
        "## Required Checks",
        "",
        "- Reward hacking: inspect rows labeled `extractor_success_unclean_raw`.",
        "- Format collapse: inspect `no_select_or_format_collapse`.",
        "- Hallucinated schema/API: inspect `hallucinated_schema`.",
        "- Fake reasoning/prose: inspect `prose_or_markdown_wrapped`.",
        "",
        "## Examples",
        "",
    ])
    for key, _ in sorted(counts.items()):
        lines.append(f"### `{key}`")
        lines.append("")
        shown = 0
        for row, lab in labels:
            if lab != key:
                continue
            lines.append(f"- `{row.get('id', row.get('index', '?'))}` {clip(row.get('question', ''))}")
            lines.append(f"  - pred: `{clip(row.get('predicted_sql') or row.get('output') or '')}`")
            if row.get("gold_sql"):
                lines.append(f"  - gold: `{clip(row.get('gold_sql'))}`")
            shown += 1
            if shown >= args.max_examples:
                break
        lines.append("")

    Path(args.out).write_text("\n".join(lines).rstrip() + "\n")
    print(f"wrote SQL trace review -> {args.out}")


if __name__ == "__main__":
    main()
