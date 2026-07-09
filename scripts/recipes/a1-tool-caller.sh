#!/usr/bin/env bash
# A1 — first tool-calling specialist: qwen3-4b + LoRA, +3pp BFCL ship gate.
#
# Orchestrates the shipped CLI end-to-end: baseline BFCL → SFT (LoRA, with B15
# layer-wise LR decay) → adapter BFCL (via eval-bfcl --lora) → eval-gate on
# +3pp. RUN ON A GPU MAC with a local BFCL checkout — this is not a CI smoke;
# it trains a 4B adapter (~hours) and runs the Berkeley Function-Calling suite.
#
#   BFCL_ROOT=~/bfcl DATA=tools.jsonl bash scripts/recipes/a1-tool-caller.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/evals/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"

BASE="${BASE:-qwen3-4b-instruct-2507}"          # HF dir or gallery id (posttrainllm pull)
DATA="${DATA:?set DATA=<tool-calling SFT jsonl> ({instruction,input?,response})}"
OUT="${OUT:-$ROOT/specialists/a1-tool-caller/a1.lora}"
STEPS="${STEPS:-2000}"; RANK="${RANK:-16}"; LLRD="${LLRD:-0.9}"
BFCL_ROOT="${BFCL_ROOT:?set BFCL_ROOT=<local BFCL checkout>}"
THRESH_PP="${THRESH_PP:-3}"                       # +3pp ship gate
WORK="$(mktemp -d)"; mkdir -p "$(dirname "$OUT")"

echo "[1/4] baseline BFCL ($BASE)"
"$BIN" eval-bfcl "$BASE" --bfcl-root "$BFCL_ROOT" --out "$WORK/baseline.jsonl"

echo "[2/4] SFT LoRA adapter (rank $RANK, $STEPS steps, llrd $LLRD)"
"$BIN" sft "$BASE" --data "$DATA" --out "$OUT" \
    --template chatml --rank "$RANK" --steps "$STEPS" --llrd "$LLRD"

echo "[3/4] adapter BFCL (eval-bfcl --lora)"
"$BIN" eval-bfcl "$BASE" --lora "$OUT" --bfcl-root "$BFCL_ROOT" --out "$WORK/candidate.jsonl"

echo "[4/4] ship gate: candidate >= baseline + ${THRESH_PP}pp"
"$BIN" eval-gate --baseline "$WORK/baseline.jsonl" --candidate "$WORK/candidate.jsonl" \
    --threshold "$THRESH_PP" --out "$(dirname "$OUT")/gate-result.json"

echo "A1 recipe complete — adapter at $OUT, gate-result.json alongside"
