#!/usr/bin/env bash
# Frozen Needle 2 successor factorial for Issue #138 task 6.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAGE="${1:-preflight}"
RUN_DIR="$ROOT/runs/verified-wins/needle-successor-factorial-v1"
: "${NEEDLE_ROOT:?Set NEEDLE_ROOT to the patched pinned Needle source checkout}"
: "${NEEDLE_MODEL_DIR:?Set NEEDLE_MODEL_DIR to the pinned Needle model files}"
: "${NEEDLE_PYTHON:?Set NEEDLE_PYTHON to the frozen JAX environment Python}"
export JAX_PLATFORMS=cpu
CHECKPOINT="$NEEDLE_MODEL_DIR/checkpoints/needle2.pkl"
SEED=1380401
ARMS=(plain-standard plain-safety distractor-standard distractor-safety)
mkdir -p "$RUN_DIR"

validate() {
  python3 scripts/experiments/validate_verified_win_manifest.py \
    evals/verified-wins/needle-successor-v1.json --stage run
  python3 scripts/needle2_successor_data.py --check
}

eval_one() {
  local model_id="$1"
  local adapter="$2"
  local fixture="$3"
  local output="$4"
  "$NEEDLE_PYTHON" scripts/needle2_successor_eval.py \
    --source-root "$NEEDLE_ROOT" --checkpoint "$CHECKPOINT" \
    --fixture "$fixture" --model "$model_id=$adapter" --output "$output"
}

tiny_train() {
  "$NEEDLE_PYTHON" scripts/needle2_successor_train.py tiny \
    --source-root "$NEEDLE_ROOT" --checkpoint "$CHECKPOINT" --run-dir "$RUN_DIR"
}

tiny_eval() {
  local decision_args=()
  for arm in "${ARMS[@]}"; do
    local adapter="$RUN_DIR/tiny-adapters/$arm-seed-$SEED.pkl"
    local output="$RUN_DIR/tiny-eval-$arm.json"
    eval_one "$arm" "$adapter" "evals/needle2/successor-v1/tiny-$arm.jsonl" "$output"
    decision_args+=(--eval "$output")
  done
  "$NEEDLE_PYTHON" scripts/needle2_successor_decide.py tiny \
    "${decision_args[@]}" --output "$RUN_DIR/tiny-gate.json"
}

tiny() {
  tiny_train
  tiny_eval
}

full() {
  "$NEEDLE_PYTHON" scripts/needle2_successor_train.py full \
    --source-root "$NEEDLE_ROOT" --checkpoint "$CHECKPOINT" --run-dir "$RUN_DIR" \
    --tiny-gate "$RUN_DIR/tiny-gate.json"
  dev
}

dev() {
  [[ -f "$RUN_DIR/full-training.json" ]]
  local model_args=()
  local seed
  for seed in 1380401 1380402 1380403; do
    local arm
    for arm in "${ARMS[@]}"; do
      model_args+=(--model "$arm-seed-$seed=$RUN_DIR/adapters/$arm-seed-$seed.pkl")
    done
  done
  "$NEEDLE_PYTHON" scripts/needle2_successor_eval.py \
    --source-root "$NEEDLE_ROOT" --checkpoint "$CHECKPOINT" \
    --fixture evals/needle2/successor-v1/public-dev-v2.jsonl \
    "${model_args[@]}" --output "$RUN_DIR/dev-eval.json" --resume
  "$NEEDLE_PYTHON" scripts/needle2_successor_decide.py dev \
    --eval "$RUN_DIR/dev-eval.json" \
    --incumbent evals/needle2/bounded-public-smoke-v1.json \
    --output "$RUN_DIR/dev-selection.json"
}

sealed() {
  python3 - "$RUN_DIR/dev-selection.json" <<'PY'
import json
import sys

selection = json.load(open(sys.argv[1]))
if selection.get("sealed_unlocked") is not True:
    raise SystemExit("sealed V2 remains locked: no eligible dev candidate")
PY
  local adapter
  adapter="$(python3 - "$RUN_DIR/dev-selection.json" <<'PY'
import json
import sys
print(json.load(open(sys.argv[1]))["selected_adapter"])
PY
)"
  "$NEEDLE_PYTHON" scripts/needle2_successor_eval.py \
    --source-root "$NEEDLE_ROOT" --checkpoint "$CHECKPOINT" \
    --fixture evals/needle2/successor-v1/sealed-v2.jsonl \
    --model incumbent-float=base --model selected-float="$adapter" \
    --output "$RUN_DIR/sealed-eval.json"
}

validate
case "$STAGE" in
  preflight) "$NEEDLE_PYTHON" -c 'import jax; print(jax.default_backend(), jax.devices())' ;;
  tiny) tiny ;;
  tiny-eval) tiny_eval ;;
  full) full ;;
  dev) dev ;;
  sealed) sealed ;;
  *) echo "unknown stage: $STAGE" >&2; exit 2 ;;
esac
