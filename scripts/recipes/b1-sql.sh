#!/usr/bin/env bash
# B1 — text-to-SQL specialist recipe. Cookie-cuts A1 with the SQL eval gate.
# UNTESTED — runs GPU training + a serve; not a CI smoke. Pipeline:
#   sft (LoRA + B15 llrd) → generate predicted_sql → eval-sql → eval-gate.
#
#   DATA=spider-sft.jsonl DEV=spider-dev.jsonl DB_DIR=./dbs bash scripts/recipes/b1-sql.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/evals/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"

BASE="${BASE:-qwen3-4b-instruct-2507}"
DATA="${DATA:?set DATA=<SQL SFT jsonl {instruction,response}>}"
DEV="${DEV:?set DEV=<dev jsonl {question, gold_sql, db}>}"
DB_DIR="${DB_DIR:?set DB_DIR=<dir of sqlite DBs>}"
OUT="${OUT:-$ROOT/specialists/b1-sql/b1.lora}"
STEPS="${STEPS:-2000}"; RANK="${RANK:-16}"
WORK="$(mktemp -d)"; mkdir -p "$(dirname "$OUT")"

echo "[1/3] SFT LoRA"
"$BIN" sft "$BASE" --data "$DATA" --out "$OUT" --rank "$RANK" --steps "$STEPS" --llrd 0.9

echo "[2/3] generate predicted_sql on dev"
"$BIN" generate "$BASE" --lora "$OUT" --data "$DEV" \
    --prompt-field question --out-field predicted_sql --out "$WORK/preds.jsonl"

echo "[3/3] eval-sql execution accuracy"
"$BIN" eval-sql "$WORK/preds.jsonl" --db-dir "$DB_DIR" --out "$(dirname "$OUT")/sql-eval.jsonl"
echo "B1 recipe complete — adapter $OUT, eval rows alongside (review execution_accuracy)"
