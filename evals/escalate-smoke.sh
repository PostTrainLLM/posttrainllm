#!/usr/bin/env bash
# evals/escalate-smoke.sh — B5 defer-to-cloud data-gen + eval (pure CPU).
#
# Exercises the labeling + metrics end-to-end without a model: builds SFT data
# from labeled rollouts (asserts the right keep/escalate/drop split) and scores
# a predictions fixture (asserts the known precision/recall). The SFT training
# run + the cloud teacher that produces real outcomes are the GPU/cloud steps.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
FIX="$ROOT/evals/escalate-fixtures"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

echo "[1/2] build-escalate-data"
"$BIN" build-escalate-data "$FIX/rollouts.jsonl" --out "$TMP/sft.jsonl" >/dev/null 2>&1 || fail "build failed"
# rollouts: 2 keep-local, 2 escalate, 1 drop → 4 SFT rows. The inner defer
# JSON is an escaped string inside the SFT "response" field, so parse it.
python3 - "$TMP/sft.jsonl" <<'PY' || fail "SFT output assertions failed"
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert len(rows) == 4, f"expected 4 SFT rows, got {len(rows)}"
defers = [json.loads(r["response"])["defer_to_cloud"] for r in rows]
assert defers.count(True) == 2, f"expected 2 escalate rows, got {defers.count(True)}"
assert defers.count(False) == 2, f"expected 2 keep-local rows, got {defers.count(False)}"
print("  4 SFT rows: 2 escalate + 2 keep-local")
PY

echo "[2/2] eval-escalate"
out="$("$BIN" eval-escalate "$FIX/predictions.jsonl")" || fail "eval-escalate failed"
echo "  $out"
echo "$out" | grep -q "precision=0.667" || fail "expected precision 0.667, got: $out"
echo "$out" | grep -q "recall=0.667"    || fail "expected recall 0.667, got: $out"

echo "SMOKE OK: build-escalate-data + eval-escalate (B5)"
