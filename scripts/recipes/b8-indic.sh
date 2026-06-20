#!/usr/bin/env bash
# B8 — multilingual (Indic) specialist recipe. Cookie-cuts A1 with the MILU
# per-language gate. UNTESTED — GPU training + serve, not a CI smoke. Pipeline:
#   sft → generate predicted → eval-milu (per-language + macro).
#
#   DATA=indic-sft.jsonl DEV=milu-dev.jsonl bash scripts/recipes/b8-indic.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/evals/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"

BASE="${BASE:-sarvam-edge}"   # or another Indic-capable base
DATA="${DATA:?set DATA=<Indic SFT jsonl>}"
DEV="${DEV:?set DEV=<MILU dev jsonl {language, question, gold}>}"
OUT="${OUT:-$ROOT/specialists/b8-indic/b8.lora}"
STEPS="${STEPS:-3000}"; RANK="${RANK:-16}"
WORK="$(mktemp -d)"; mkdir -p "$(dirname "$OUT")"

echo "[1/3] SFT LoRA"
"$BIN" sft "$BASE" --data "$DATA" --out "$OUT" --rank "$RANK" --steps "$STEPS" --llrd 0.9

echo "[2/3] generate predictions on MILU dev (keeps the language field)"
"$BIN" generate "$BASE" --lora "$OUT" --data "$DEV" \
    --prompt-field question --out-field predicted --out "$WORK/preds.jsonl"

echo "[3/3] eval-milu per-language breakdown"
"$BIN" eval-milu "$WORK/preds.jsonl" --out "$(dirname "$OUT")/milu-eval.jsonl"
echo "B8 recipe complete — adapter $OUT, per-language + macro rows alongside"
