#!/usr/bin/env bash
# evals/router-bakeoff-smoke.sh — B2–B7 router bake-off scorer (no model).
# Scores a predictions fixture (classifier 3/4, fsm 2/4) and asserts the
# per-method accuracy + winner.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
PREDS="$ROOT/evals/router-bakeoff-fixtures/preds.jsonl"
[ -f "$PREDS" ] || fail "missing fixture $PREDS"

out="$("$BIN" eval-router "$PREDS")" || fail "eval-router failed"
echo "$out" | sed 's/^/  /'
echo "$out" | grep -q "classifier accuracy=0.750" || fail "expected classifier 0.750, got: $out"
echo "$out" | grep -q "fsm.*accuracy=0.500"       || fail "expected fsm 0.500, got: $out"
echo "$out" | grep -q "winner: classifier (+25.0pp)" || fail "expected classifier winner +25pp, got: $out"
echo "SMOKE OK: eval-router bake-off (B2-B7)"
