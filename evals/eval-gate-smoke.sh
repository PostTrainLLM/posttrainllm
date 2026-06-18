#!/usr/bin/env bash
# B32 smoke test for `tinygpt eval-gate`.
#
# Asserts the exit-code contract with committed fixtures — no GPU, no
# server, no network:
#   - a candidate that matches the baseline           → exit 0 (PASS)
#   - a candidate that regresses past threshold        → exit 1 (FAIL)
#   - --update-baseline re-stamps the baseline         → exit 0
#
# Usage: bash evals/eval-gate-smoke.sh
# CI:    runs on the self-hosted Mac job after `swift build`.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX="$ROOT/evals/eval-gate-fixtures"
SPEC="$FIX/eval-gate.json"
BASELINE="$FIX/baseline.jsonl"
BUDGET="$ROOT/evals/sample-budget.json"

# Resolve the tinygpt binary: prefer release, then debug, else build.
TINYGPT="$ROOT/native-mac/.build/release/tinygpt"
[ -x "$TINYGPT" ] || TINYGPT="$ROOT/native-mac/.build/debug/tinygpt"
if [ ! -x "$TINYGPT" ]; then
  echo "==> tinygpt binary not found; building (debug)…"
  ( cd "$ROOT/native-mac" && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift build )
  TINYGPT="$ROOT/native-mac/.build/debug/tinygpt"
fi
echo "==> using $TINYGPT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
fail=0

assert_exit() {
  local want="$1"; shift
  local label="$1"; shift
  set +e
  "$@" >"$WORK/out.txt" 2>&1
  local got=$?
  set -e
  if [ "$got" -eq "$want" ]; then
    echo "  ✓ $label (exit $got)"
  else
    echo "  ✗ $label — expected exit $want, got $got"
    sed 's/^/      /' "$WORK/out.txt"
    fail=1
  fi
}

echo "==> PASS case: candidate matches baseline"
assert_exit 0 "matching candidate passes" \
  "$TINYGPT" eval-gate --spec "$SPEC" --baseline "$BASELINE" \
    --candidate "$FIX/candidate-pass.jsonl" --out "$WORK/gate-pass.json"

echo "==> FAIL case: candidate regresses past threshold"
assert_exit 1 "regressed candidate fails" \
  "$TINYGPT" eval-gate --spec "$SPEC" --baseline "$BASELINE" \
    --candidate "$FIX/candidate-fail.jsonl" --out "$WORK/gate-fail.json"

echo "==> result JSON is written + well-formed"
if python3 -c "import json,sys; d=json.load(open('$WORK/gate-fail.json')); sys.exit(0 if d['passed'] is False and d['failedCount']>=1 else 1)"; then
  echo "  ✓ gate-result.json reports passed=false, failedCount>=1"
else
  echo "  ✗ gate-result.json missing or malformed"; fail=1
fi

echo "==> K-pass candidate stats are preserved"
assert_exit 0 "repeated candidate passes with uncertainty stats" \
  "$TINYGPT" eval-gate --spec "$SPEC" --baseline "$BASELINE" \
    --candidate "$FIX/candidate-repeat.jsonl" --passes 3 --budget "$BUDGET" --out "$WORK/gate-repeat.json"
if python3 -c "import json,sys; d=json.load(open('$WORK/gate-repeat.json')); s=d['suites'][0].get('candidateStats'); p=d.get('protocol') or {}; b=p.get('budget') or {}; ok=s and s['n']==3 and 'ci95Low' in s and 'ci95High' in s and len(s['trialScores'])==3 and p.get('passes')==3 and b.get('max_steps')==8 and b.get('sampling_seed')==17; sys.exit(0 if ok else 1)"; then
  echo "  ✓ gate-result.json carries n/stdev/ci95/trialScores for repeated rows"
else
  echo "  ✗ repeated-run stats or protocol budget missing from gate-result.json"; fail=1
fi

echo "==> command-driven suite receives protocol env"
cat > "$WORK/emit-row.py" <<'PY'
import json, os, sys, time, uuid
budget_path = os.environ.get("TINYGPT_EVAL_BUDGET")
out = os.environ["TINYGPT_EVAL_OUT"]
passes = int(os.environ.get("TINYGPT_EVAL_PASSES", "1"))
if not budget_path:
    raise SystemExit("TINYGPT_EVAL_BUDGET missing")
budget = json.load(open(budget_path))
row = {
    "run_id": str(uuid.uuid4()),
    "model_path": "/tmp/protocol-env-model",
    "model_name": "protocol-env-model",
    "baseline": False,
    "task": "bfcl",
    "subtask": "simple",
    "metric": "accuracy",
    "score": 0.8,
    "n_examples": 1,
    "wall_seconds": 0.0,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "harness_version": "env-smoke",
    "protocol": {"passes": passes, "budget": budget},
}
with open(out, "a") as f:
    f.write(json.dumps(row, sort_keys=True) + "\n")
PY
cat > "$WORK/command-spec.json" <<JSON
{
  "baseline": "$BASELINE",
  "default_threshold": 2.0,
  "suites": [
    {
      "name": "bfcl",
      "task": "bfcl",
      "subtask": "simple",
      "metric": "accuracy",
      "command": ["python3", "$WORK/emit-row.py"]
    }
  ]
}
JSON
assert_exit 0 "command suite receives TINYGPT_EVAL_BUDGET/PASSES" \
  "$TINYGPT" eval-gate --spec "$WORK/command-spec.json" \
    --passes 2 --budget "$BUDGET" --out "$WORK/gate-command.json"
if python3 -c "import json,sys; d=json.load(open('$WORK/gate-command.json')); p=d.get('protocol') or {}; ok=d.get('passed') is True and p.get('passes')==2; sys.exit(0 if ok else 1)"; then
  echo "  ✓ command-driven gate-result preserves protocol passes"
else
  echo "  ✗ command-driven protocol metadata missing"; fail=1
fi

echo "==> --update-baseline re-stamps from a candidate run"
cp "$BASELINE" "$WORK/baseline.jsonl"
assert_exit 0 "update-baseline succeeds" \
  "$TINYGPT" eval-gate --spec "$SPEC" --baseline "$WORK/baseline.jsonl" \
    --candidate "$FIX/candidate-fail.jsonl" --update-baseline
# After re-stamping with the regressed run, that same candidate now passes.
assert_exit 0 "re-stamped baseline accepts the new numbers" \
  "$TINYGPT" eval-gate --spec "$SPEC" --baseline "$WORK/baseline.jsonl" \
    --candidate "$FIX/candidate-fail.jsonl" --out "$WORK/gate-restamp.json"

if [ "$fail" -eq 0 ]; then
  echo "ALL eval-gate smoke checks passed."
else
  echo "eval-gate smoke FAILED." >&2
fi
exit "$fail"
