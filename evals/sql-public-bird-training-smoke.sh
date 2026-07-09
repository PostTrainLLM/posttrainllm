#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="$(mktemp -d /tmp/posttrainllm-sql-bird.XXXXXX)"
python3 scripts/build_sql_bird_public_training.py \
  --out "$OUT" \
  --bird-limit 32 \
  --bmc2-limit 16 \
  --max-prompt-chars 2600

python3 - "$OUT/train.jsonl" "$OUT/manifest.json" <<'PY'
import json, sys
rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
manifest = json.load(open(sys.argv[2]))
assert len(rows) == 48, len(rows)
assert manifest["source_counts"]["xu3kev/BIRD-SQL-data-train"] == 32
assert manifest["source_counts"]["b-mc2/sql-create-context"] == 16
assert all(row["response"].strip().lower().startswith("select ") for row in rows)
assert all(row["response"].strip().endswith(";") for row in rows)
assert any(row.get("curriculum") == "join" for row in rows)
PY

echo "sql-public-bird-training-smoke: ok"
