#!/usr/bin/env bash
# evals/milu-smoke.sh — B8 per-language MILU breakdown (no model).
# Scores a results fixture (hindi 0.5, tamil 0.5, telugu 1.0) and asserts the
# per-language accuracies + macro-average (0.667).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
RES="$ROOT/evals/milu-fixtures/results.jsonl"
[ -f "$RES" ] || fail "missing fixture $RES"

out="$("$BIN" eval-milu "$RES")" || fail "eval-milu failed"
echo "$out" | sed 's/^/  /'
echo "$out" | grep -q "hindi accuracy=0.500"  || fail "expected hindi 0.500: $out"
echo "$out" | grep -q "tamil accuracy=0.500"  || fail "expected tamil 0.500: $out"
echo "$out" | grep -q "telugu accuracy=1.000" || fail "expected telugu 1.000: $out"
echo "$out" | grep -q "macro-average=0.667"   || fail "expected macro 0.667: $out"
echo "SMOKE OK: eval-milu per-language breakdown (B8)"
