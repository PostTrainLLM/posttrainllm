#!/usr/bin/env bash
# Smoke for the public-style SQL training dataset builder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/scripts/build_sql_public_training.py" \
  --out "$WORK/sql-public" \
  --scan 260 \
  --dev-limit 12 \
  --train-limit 24 \
  --train-start 120

python3 - "$WORK/sql-public" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
train = [json.loads(line) for line in (root / "train.jsonl").read_text().splitlines()]
dev = [json.loads(line) for line in (root / "dev.jsonl").read_text().splitlines()]
prefs = [json.loads(line) for line in (root / "preferences.jsonl").read_text().splitlines()]
manifest = json.loads((root / "manifest.json").read_text())

assert len(train) == 24, len(train)
assert len(dev) == 12, len(dev)
assert len(prefs) == len(train), (len(prefs), len(train))
assert manifest["train_rows"] == len(train)
assert manifest["dev_rows"] == len(dev)
assert manifest["non_overlap_key"] == "source_index"

train_ids = {r["source_index"] for r in train}
dev_ids = {r["source_index"] for r in dev}
assert train_ids.isdisjoint(dev_ids), "train/dev overlap"
assert {r["curriculum"] for r in train}
assert {r["curriculum"] for r in dev}

for row in train:
    assert row["instruction"].startswith("You are a text-to-SQL model.")
    assert row["response"].lower().startswith("select ")
    assert row["response"].endswith(";")

for row in dev:
    assert row["prompt"].startswith("You are a text-to-SQL model.")
    assert row["gold_sql"].lower().startswith("select ")
    assert row["gold_sql"].endswith(";")

for row in prefs:
    assert row["chosen"] != row["rejected"]
    assert row["failure_type"].startswith("sql_")

print("SMOKE OK: public SQL training builder")
PY
