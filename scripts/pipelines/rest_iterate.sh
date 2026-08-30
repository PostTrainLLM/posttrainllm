#!/usr/bin/env bash
# One ReST self-improvement iteration (teacher-free) — see docs/prds/self-improving-agents.md.
#
#   1. The CURRENT model rolls out K times/task at temperature on the rollout pool.
#   2. Keep only checker-PASSING trajectories (the model's OWN — correct interleaving + real
#      tool-result values, the thing gold-cloning can't teach; journey §8.5).
#   3. + file-ops gold-clones (depth anchor; gold works there — args are prompt-derivable).
#   4. SFT on the union → fuse → eval depth (hard) + breadth.
#
# Success = breadth rises above the stock baseline (60%) with NO teacher.
# Usage: rest_iterate.sh <current_model_path> <tag> [K=2] [temp=0.7]
set -euo pipefail
MODEL_IN="${1:?current model path}"; TAG="${2:-mt4b_rest}"; K="${3:-2}"; TEMP="${4:-0.7}"
B4="/Users/sarthak/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554"
WINS="/tmp/${TAG}_wins.jsonl"; rm -f "$WINS"
GP="You are an autonomous tool-using agent. For each user turn: (1) plan the full sequence of function calls the task needs; (2) execute them, reading each tool result; (3) never repeat a call that already succeeded; (4) once every requested action is complete, stop and emit no tool call. Use the tool results to track the current state as you go."

echo "== 1/3 roll out (K=$K temp=$TEMP) + keep checker-passing trajectories =="
MODEL="$MODEL_IN" MT_SYS="$GP" MT_TEMP="$TEMP" MT_ROLLOUTS="$K" MT_DUMP_WINS="$WINS" \
  MT_DATA=scripts/fixtures/multi_turn_restpool_data.jsonl \
  MT_GOLD=scripts/fixtures/multi_turn_restpool_gold.jsonl \
  python3 scripts/bfcl/bfcl_multiturn_eval.py 143
echo "   multi-backend wins collected: $(wc -l < "$WINS")"

echo "== 2/3 + file-ops gold-clones (depth anchor) =="
MT_DATA=scripts/fixtures/multi_turn_train_data.jsonl MT_GOLD=scripts/fixtures/multi_turn_train_gold.jsonl \
  MT_OUT=/tmp/${TAG}_fo.jsonl python3 scripts/gold_to_sft_traj.py 100
cat /tmp/${TAG}_fo.jsonl >> "$WINS"
echo "   total SFT trajectories: $(wc -l < "$WINS")"

echo "== 3/3 SFT on the model's own wins + eval (hard depth, breadth) =="
EVAL_SETS="hard breadth" bash scripts/pipelines/distill_multiturn.sh "$WINS" "$B4" "$TAG"
