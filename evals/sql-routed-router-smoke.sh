#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d /tmp/tinygpt-sql-router.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

python3 - "$TMP/unlabeled.jsonl" <<'PY'
import json, sys
out = open(sys.argv[1], "w")
for line in open("evals/sql-routed-mixed-v1/mixed114.jsonl"):
    if not line.strip():
        continue
    row = json.loads(line)
    row.pop("route", None)
    out.write(json.dumps(row, separators=(",", ":")) + "\n")
PY

python3 scripts/run_sql_routed_generate.py \
  --input "$TMP/unlabeled.jsonl" \
  --routes-out "$TMP/routes.jsonl" \
  --route-only

python3 - "$TMP/routes.jsonl" <<'PY'
import collections, json, sys

routes = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
counts = collections.Counter(row["route"] for row in routes)
assert len(routes) == 114, len(routes)
assert counts == {"public": 64, "synthetic": 50}, counts

reasons = collections.Counter(row["reason"] for row in routes)
assert reasons["known_public_source"] == 64, reasons
assert reasons["sqlite_db_field"] == 50, reasons
assert min(row["confidence"] for row in routes) >= 0.99
PY

echo "sql-routed-router-smoke: ok"
