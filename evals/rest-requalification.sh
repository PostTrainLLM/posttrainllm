#!/usr/bin/env bash
# Frozen same-host ReST requalification for Issue #138 task 5.
#
# Usage:
#   BFCL_ROOT=/path/to/gorilla/berkeley-function-call-leaderboard \
#     bash evals/rest-requalification.sh frontier
#   bash evals/rest-requalification.sh download
#   BFCL_ROOT=... bash evals/rest-requalification.sh local
#   BFCL_ROOT=... bash evals/rest-requalification.sh all
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAGE="${1:-all}"
RUN_DIR="$ROOT/runs/verified-wins/rest-4b-requalification-v1"
MODEL_DIR="$RUN_DIR/models"
STOCK_DIR="$MODEL_DIR/stock-4b"
CANDIDATE_DIR="$MODEL_DIR/rest-4b"
SEED=13803
STOCK_REV="cdbee75f17c01a7cc42f958dc650907174af0554"
CANDIDATE_REV="b332dfe437dc201922d50b28eddf0c99ebcc79a7"
BFCL_REV="6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
EXCLUDED_BREADTH_IDS="multi_turn_base_66,multi_turn_base_92,multi_turn_base_96,multi_turn_base_121,multi_turn_base_135,multi_turn_base_158,multi_turn_base_179"

mkdir -p "$RUN_DIR" "$MODEL_DIR"

validate_manifest() {
  python3 scripts/experiments/validate_verified_win_manifest.py \
    evals/verified-wins/rest-requalification-v1.json --stage run
}

verify_bfcl() {
  : "${BFCL_ROOT:?Set BFCL_ROOT to the pinned berkeley-function-call-leaderboard directory}"
  local actual
  actual="$(git -C "$BFCL_ROOT" rev-parse HEAD)"
  if [[ "$actual" != "$BFCL_REV" ]]; then
    echo "BFCL revision mismatch: expected $BFCL_REV, got $actual" >&2
    exit 1
  fi
}

frontier() {
  verify_bfcl
  BFCL_ROOT="$BFCL_ROOT" MT_DATA=scripts/fixtures/multi_turn_hard_data.jsonl \
    MT_GOLD=scripts/fixtures/multi_turn_hard_gold.jsonl \
    MT_OUTPUT="$RUN_DIR/frontier-depth.json" MT_SEED="$SEED" \
    CODEX_MODEL=gpt-5.5 CODEX_REASONING=high \
    python3 scripts/bfcl/bfcl_multiturn_codex.py 12
  BFCL_ROOT="$BFCL_ROOT" MT_DATA=scripts/fixtures/multi_turn_breadth_data.jsonl \
    MT_GOLD=scripts/fixtures/multi_turn_breadth_gold.jsonl \
    MT_OUTPUT="$RUN_DIR/frontier-breadth.json" MT_SEED="$SEED" \
    MT_EXCLUDE_IDS="$EXCLUDED_BREADTH_IDS" \
    CODEX_MODEL=gpt-5.5 CODEX_REASONING=high \
    python3 scripts/bfcl/bfcl_multiturn_codex.py 52
  python3 scripts/bfcl/check_rest_frontier.py \
    --depth "$RUN_DIR/frontier-depth.json" \
    --breadth "$RUN_DIR/frontier-breadth.json"
}

download_models() {
  python3 scripts/bfcl/check_rest_frontier.py \
    --depth "$RUN_DIR/frontier-depth.json" \
    --breadth "$RUN_DIR/frontier-breadth.json"
  hf download Qwen/Qwen3-4B-Instruct-2507 --revision "$STOCK_REV" \
    --local-dir "$STOCK_DIR"
  hf download posttrainllm/qwen3-4b-rest-fused --revision "$CANDIDATE_REV" \
    --local-dir "$CANDIDATE_DIR"
  hf cache verify Qwen/Qwen3-4B-Instruct-2507 --revision "$STOCK_REV" \
    --local-dir "$STOCK_DIR"
  hf cache verify posttrainllm/qwen3-4b-rest-fused --revision "$CANDIDATE_REV" \
    --local-dir "$CANDIDATE_DIR"
  MODEL_DIR="$MODEL_DIR" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["MODEL_DIR"])
size = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
limit = 20 * 1024**3
print(f"model pair bytes={size} ({size / 1024**3:.2f} GiB)")
if size > limit:
    raise SystemExit(f"model pair exceeds frozen 20 GiB cap: {size}")
PY
}

run_arm() {
  local model="$1"
  local model_id="$2"
  local suite="$3"
  local data="$4"
  local gold="$5"
  local exclude_args=()
  if [[ "$suite" == "breadth" ]]; then
    IFS=',' read -r -a excluded_ids <<< "$EXCLUDED_BREADTH_IDS"
    for excluded_id in "${excluded_ids[@]}"; do
      exclude_args+=(--exclude-id "$excluded_id")
    done
  fi
  BFCL_ROOT="$BFCL_ROOT" uv run --no-project --with mlx-lm==0.31.3 \
    python scripts/bfcl/run_rest_arm.py \
      --model "$model" --model-id "$model_id" --suite "$suite" \
      --data "$data" --gold "$gold" --seed "$SEED" \
      "${exclude_args[@]}" \
      --output "$RUN_DIR/$model_id-$suite.json"
}

local_eval() {
  verify_bfcl
  python3 scripts/bfcl/check_rest_frontier.py \
    --depth "$RUN_DIR/frontier-depth.json" \
    --breadth "$RUN_DIR/frontier-breadth.json"
  [[ -f "$STOCK_DIR/model.safetensors.index.json" ]]
  [[ -f "$CANDIDATE_DIR/model.safetensors.index.json" ]]

  # Alternated arm order across suite blocks: A-B, then B-A.
  run_arm "$STOCK_DIR" stock-4b depth \
    scripts/fixtures/multi_turn_hard_data.jsonl \
    scripts/fixtures/multi_turn_hard_gold.jsonl
  run_arm "$CANDIDATE_DIR" rest-4b depth \
    scripts/fixtures/multi_turn_hard_data.jsonl \
    scripts/fixtures/multi_turn_hard_gold.jsonl
  run_arm "$CANDIDATE_DIR" rest-4b breadth \
    scripts/fixtures/multi_turn_breadth_data.jsonl \
    scripts/fixtures/multi_turn_breadth_gold.jsonl
  run_arm "$STOCK_DIR" stock-4b breadth \
    scripts/fixtures/multi_turn_breadth_data.jsonl \
    scripts/fixtures/multi_turn_breadth_gold.jsonl

  python3 scripts/bfcl/compare_rest_requalification.py \
    --frontier-depth "$RUN_DIR/frontier-depth.json" \
    --frontier-breadth "$RUN_DIR/frontier-breadth.json" \
    --stock-depth "$RUN_DIR/stock-4b-depth.json" \
    --candidate-depth "$RUN_DIR/rest-4b-depth.json" \
    --stock-breadth "$RUN_DIR/stock-4b-breadth.json" \
    --candidate-breadth "$RUN_DIR/rest-4b-breadth.json" \
    --output "$RUN_DIR/comparison.json"
}

validate_manifest
case "$STAGE" in
  frontier) frontier ;;
  download) download_models ;;
  local) local_eval ;;
  compare)
    python3 scripts/bfcl/compare_rest_requalification.py \
      --frontier-depth "$RUN_DIR/frontier-depth.json" \
      --frontier-breadth "$RUN_DIR/frontier-breadth.json" \
      --stock-depth "$RUN_DIR/stock-4b-depth.json" \
      --candidate-depth "$RUN_DIR/rest-4b-depth.json" \
      --stock-breadth "$RUN_DIR/stock-4b-breadth.json" \
      --candidate-breadth "$RUN_DIR/rest-4b-breadth.json" \
      --output "$RUN_DIR/comparison.json"
    ;;
  all) frontier; download_models; local_eval ;;
  *) echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac
