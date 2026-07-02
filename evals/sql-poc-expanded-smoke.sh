#!/usr/bin/env bash
# Smoke for the expanded, non-overlapping SQL POC dataset builder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/scripts/build_sql_poc_dataset.py" --out "$WORK/sql" --seed 20260702 --dev-per-domain 18

python3 - "$WORK/sql" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])
train = [json.loads(line) for line in (root / "train.jsonl").read_text().splitlines()]
dev = [json.loads(line) for line in (root / "dev.jsonl").read_text().splitlines()]
prefs = [json.loads(line) for line in (root / "preferences.jsonl").read_text().splitlines()]
manifest = json.loads((root / "manifest.json").read_text())
taxonomy = json.loads((root / "failure_taxonomy.json").read_text())

assert len(train) >= 40, len(train)
assert len(dev) >= 30, len(dev)
assert len(prefs) == len(train), (len(prefs), len(train))
assert manifest["counts"]["train_rows"] == len(train)
assert "sql_prose_wrapped" in taxonomy

train_pairs = {(r["instruction"], r["response"]) for r in train}
dev_pairs = {(r["prompt"], r["gold_sql"]) for r in dev}
assert not (train_pairs & dev_pairs), "train/dev overlap"
assert len({r["domain"] for r in train}) == 5
assert len({r["domain"] for r in dev}) == 5

for row in dev:
    db_path = root / "dbs" / row["db"]
    with sqlite3.connect(db_path) as db:
        db.execute(row["gold_sql"]).fetchall()

for row in prefs[:12]:
    assert row["chosen"].lower().startswith("select")
    assert row["chosen"] != row["rejected"]
    assert row["failure_type"]

print(f"SMOKE OK: expanded SQL dataset train={len(train)} dev={len(dev)} prefs={len(prefs)}")
PY
