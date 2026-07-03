#!/usr/bin/env bash
# No-model smoke for scripts/measure_sql_routed_perf.py.
#
# Runs the harness in mock mode over the first 5 rows of
# evals/sql-poc-expanded/dev.jsonl into a temp dir and asserts every
# report field exists with plausible values. Passes with no network and
# no models.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

DATA="$ROOT/evals/sql-poc-expanded/dev.jsonl"
[ -f "$DATA" ] || { echo "SMOKE FAIL: missing fixture $DATA" >&2; exit 1; }

# Offline stand-in: sleep briefly and print a fixed SQL-ish string so
# tokens/sec is non-zero.
MOCK_CMD='python3 -c "import time; time.sleep(0.01); print(\"select 1 from t where x = 5;\")"'

OUT="$WORK/report.json"

python3 "$ROOT/scripts/measure_sql_routed_perf.py" \
  --data "$DATA" \
  --limit 5 \
  --mock \
  --mock-cmd "$MOCK_CMD" \
  --out "$OUT"

python3 - "$OUT" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    r = json.load(f)

def check(cond, msg):
    if not cond:
        print(f"SMOKE FAIL: {msg}", file=sys.stderr)
        sys.exit(1)

for field in ("rows", "latency_ms", "peak_rss_mb", "tokens_per_s", "command", "mock"):
    check(field in r, f"missing field {field}")

check(r["rows"] == 5, f"rows == 5 (got {r['rows']})")
check(r["mock"] is True, "mock is True")
for sub in ("p50", "p95", "mean"):
    check(sub in r["latency_ms"], f"missing latency_ms.{sub}")
    check(r["latency_ms"][sub] > 0, f"latency_ms.{sub} > 0")
check(r["latency_ms"]["p95"] >= r["latency_ms"]["p50"], "p95 >= p50")
check(r["peak_rss_mb"] > 0, f"peak_rss_mb > 0 (got {r['peak_rss_mb']})")
check(r["tokens_per_s"] > 0, f"tokens_per_s > 0 (got {r['tokens_per_s']})")
check(isinstance(r["command"], str) and r["command"], "command non-empty string")
check(r.get("failures", 0) == 0, f"no failures (got {r.get('failures')})")
print("SMOKE OK: sql-perf mock report", path)
PY
