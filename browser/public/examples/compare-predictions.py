"""Exact-match fixture scorer; not a harness-output converter or semantic judge."""

import json
import sys
from collections import Counter
from pathlib import Path


def load(path, prediction=False):
    rows = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        row = json.loads(line)
        key = row.get("id")
        if not isinstance(key, str) or not key or key in rows:
            raise ValueError(f"{path}:{number}: missing or duplicate id")
        if prediction:
            if row.get("status") not in {"ok", "timeout", "error"}:
                raise ValueError(f"{key}: invalid status")
            if row["status"] == "ok" and not isinstance(row.get("output"), str):
                raise ValueError(f"{key}: ok requires string output")
        elif not isinstance(row.get("expected"), str):
            raise ValueError(f"{key}: expected must be a string")
        rows[key] = row
    if not rows:
        raise ValueError(f"{path}: empty input")
    return rows


gold = load(sys.argv[1])
for path in sys.argv[2:]:
    predictions = load(path, prediction=True)
    if predictions.keys() != gold.keys():
        raise ValueError(f"{path}: ids differ from frozen gold")
    failures = Counter(r["status"] for r in predictions.values() if r["status"] != "ok")
    correct = sum(
        r["status"] == "ok" and r["output"] == gold[k]["expected"]
        for k, r in predictions.items()
    )
    print(
        json.dumps(
            {
                "file": path,
                "correct": correct,
                "total": len(gold),
                "exact_match": correct / len(gold),
                "failures": dict(failures),
            }
        )
    )
