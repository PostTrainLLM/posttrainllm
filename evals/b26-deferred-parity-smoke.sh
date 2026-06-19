#!/usr/bin/env bash
# No-model smoke for the B26 deferred-tools parity report.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat >"$WORK/full.jsonl" <<'JSONL'
{"task":"bfcl","subtask":"simple","metric":"accuracy","score":0.80,"n_examples":100,"model_name":"full","model_path":"/m","run_id":"f1","baseline":false,"wall_seconds":1,"timestamp":"t"}
{"task":"bfcl","subtask":"multiple","metric":"accuracy","score":0.70,"n_examples":100,"model_name":"full","model_path":"/m","run_id":"f2","baseline":false,"wall_seconds":1,"timestamp":"t"}
JSONL

cat >"$WORK/deferred-pass.jsonl" <<'JSONL'
{"task":"bfcl","subtask":"simple","metric":"accuracy","score":0.79,"n_examples":100,"model_name":"deferred","model_path":"/m","run_id":"d1","baseline":false,"wall_seconds":1,"timestamp":"t"}
{"task":"bfcl","subtask":"multiple","metric":"accuracy","score":0.69,"n_examples":100,"model_name":"deferred","model_path":"/m","run_id":"d2","baseline":false,"wall_seconds":1,"timestamp":"t"}
{"task":"bfcl","subtask":"deferred_tools","metric":"get_tool_info_hops","score":1.5,"n_examples":200,"model_name":"deferred","model_path":"/m","run_id":"d3","baseline":false,"wall_seconds":1,"timestamp":"t"}
JSONL

cat >"$WORK/deferred-fail.jsonl" <<'JSONL'
{"task":"bfcl","subtask":"simple","metric":"accuracy","score":0.70,"n_examples":100,"model_name":"deferred","model_path":"/m","run_id":"d1","baseline":false,"wall_seconds":1,"timestamp":"t"}
{"task":"bfcl","subtask":"multiple","metric":"accuracy","score":0.60,"n_examples":100,"model_name":"deferred","model_path":"/m","run_id":"d2","baseline":false,"wall_seconds":1,"timestamp":"t"}
JSONL

python3 "$ROOT/scripts/b26_deferred_parity_report.py" \
  --full "$WORK/full.jsonl" \
  --deferred "$WORK/deferred-pass.jsonl" \
  --require-hop-stats \
  --out "$WORK/pass-report.json" >/tmp/b26-parity-pass.out

if python3 - "$WORK/pass-report.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
ok = d["score_gate"] == "pass" and d["hop_gate"] == "pass" and round(d["delta_pp"], 1) == -1.0
sys.exit(0 if ok else 1)
PY
then
  echo "  ok pass case"
else
  echo "  fail pass case" >&2
  exit 1
fi

if python3 "$ROOT/scripts/b26_deferred_parity_report.py" \
  --full "$WORK/full.jsonl" \
  --deferred "$WORK/deferred-fail.jsonl" >/tmp/b26-parity-fail.out 2>&1; then
  echo "  fail expected score regression to exit non-zero" >&2
  exit 1
else
  echo "  ok fail case"
fi

echo "ALL b26 deferred parity smoke checks passed."
