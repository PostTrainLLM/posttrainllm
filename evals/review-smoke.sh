#!/usr/bin/env bash
# evals/review-smoke.sh — B35 code-review issue-detection scorer (no model).
# Scores a results fixture (tp=2, planted=4, found=3) → recall 0.5, prec 0.667.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
RES="$ROOT/evals/review-fixtures/results.jsonl"
[ -f "$RES" ] || fail "missing fixture $RES"

out="$("$BIN" eval-review "$RES")" || fail "eval-review failed"
echo "  $out"
echo "$out" | grep -q "recall=0.500"    || fail "expected recall 0.500: $out"
echo "$out" | grep -q "precision=0.667" || fail "expected precision 0.667: $out"
echo "$out" | grep -q "f1=0.571"        || fail "expected f1 0.571: $out"
echo "SMOKE OK: eval-review (B35)"
