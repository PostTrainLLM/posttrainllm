#!/usr/bin/env python3
"""Classify SQL eval failures and emit preference pairs.

Input is an `eval-sql --out` row trace plus the eval prompt JSONL. Output:

- failure labels for failed rows
- DPO-style `{prompt, chosen, rejected}` rows where chosen is gold SQL
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def classify(row: dict) -> str:
    raw = (row.get("predicted_sql") or "").strip()
    scored = (row.get("scored_sql") or raw).strip()
    err = (row.get("predicted_error") or "").lower()
    scored_l = scored.lower()
    gold_l = (row.get("gold_sql") or "").lower()

    if "select" not in scored_l:
        return "sql_no_select"
    if "no such column" in err or "no such table" in err:
        return "sql_wrong_schema"
    if "syntax error" in err:
        return "sql_prose_wrapped"
    if " join " in scored_l and " join " not in gold_l:
        return "sql_unneeded_join"
    if " join " not in scored_l and " join " in gold_l:
        return "sql_missing_join"
    if any(fn in gold_l for fn in ["sum(", "avg(", "count(", "max(", "min("]):
        if not any(fn in scored_l for fn in ["sum(", "avg(", "count(", "max(", "min("]):
            return "sql_wrong_aggregation"
    if " where " in gold_l and " where " in scored_l:
        return "sql_wrong_filter"
    return "sql_wrong_result"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="eval-sql row trace JSONL")
    ap.add_argument("--prompts", required=True, help="eval prompt JSONL")
    ap.add_argument("--labels-out", required=True)
    ap.add_argument("--prefs-out", required=True)
    ap.add_argument("--summary-out", required=True)
    ns = ap.parse_args()

    rows = read_jsonl(Path(ns.rows))
    prompts = read_jsonl(Path(ns.prompts))
    labels: list[dict] = []
    prefs: list[dict] = []
    counts: Counter[str] = Counter()

    for row in rows:
        if row.get("exec_match"):
            continue
        idx = int(row["index"])
        source = prompts[idx]
        failure_type = classify(row)
        counts[failure_type] += 1
        rejected = (row.get("scored_sql") or row.get("predicted_sql") or "").strip()
        labels.append({
            "index": idx,
            "id": source.get("id"),
            "domain": source.get("domain"),
            "question": row.get("question") or source.get("question"),
            "failure_type": failure_type,
            "predicted_sql": row.get("predicted_sql"),
            "scored_sql": row.get("scored_sql"),
            "gold_sql": row.get("gold_sql"),
            "predicted_error": row.get("predicted_error"),
        })
        prefs.append({
            "id": f"{source.get('id', idx)}-failure-pref",
            "domain": source.get("domain"),
            "failure_type": failure_type,
            "prompt": source["prompt"],
            "chosen": row["gold_sql"],
            "rejected": rejected,
        })

    Path(ns.labels_out).write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in labels) + ("\n" if labels else ""))
    Path(ns.prefs_out).write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in prefs) + ("\n" if prefs else ""))
    Path(ns.summary_out).write_text(json.dumps({
        "failed_rows": len(labels),
        "failure_counts": dict(sorted(counts.items())),
    }, indent=2, sort_keys=True) + "\n")
    print(f"classified {len(labels)} failures: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
