#!/usr/bin/env bash
# Distill frontier multi-turn trajectories into the student, then re-eval the hard gate.
# Pipeline: render (teacher trajectories -> mlx_lm text) -> LoRA SFT -> fuse -> eval.
#
# Teaches a NEW skill (the agentic loop) the base is weak at (hard tier 58-75%), so SFT
# should help — unlike single-turn SFT which regressed an already-strong base. Conservative
# LR + few epochs + LoRA to limit catastrophic forgetting of single-turn BFCL.
#
# Usage: scripts/distill_multiturn.sh <traj.jsonl> <base_model_path> [out_tag]
set -euo pipefail
TRAJ="${1:?trajectory jsonl}"; BASE="${2:?base model path}"; TAG="${3:-mt_distill}"
SFT_DATA="/tmp/${TAG}_data"; ADAPTER="/tmp/${TAG}_adapter"; FUSED="/tmp/${TAG}_fused"

PLAN_PROMPT="You are an autonomous tool-using agent. For each user turn: (1) first think briefly about the FULL sequence of function calls the task needs; (2) then execute them one at a time, reading each tool result before the next call; (3) NEVER repeat a call that already succeeded — check the latest tool results to see what is already done; (4) once EVERY requested action is complete, stop and emit no tool call. Track the current directory and existing files/dirs from the tool results as you go."

echo "== 1/4 render trajectories -> mlx_lm text =="
TRAJ="$TRAJ" MODEL="$BASE" OUT="$SFT_DATA" python3 scripts/render_sft_from_traj.py
MAXLEN=$(python3 -c "
import json,sys
from transformers import AutoTokenizer
tok=AutoTokenizer.from_pretrained('$BASE')
m=max(len(tok(json.loads(l)['text']).input_ids) for l in open('$SFT_DATA/train.jsonl'))
print(min(6144, ((m//512)+1)*512))" 2>/dev/null)
echo "   max-seq-length=$MAXLEN"
NTRAIN=$(wc -l < "$SFT_DATA/train.jsonl")
ITERS=$(python3 -c "print(min(500, max(150, $NTRAIN*4)))")
echo "   n_train=$NTRAIN iters=$ITERS"

echo "== 2/4 LoRA SFT =="
# grad-checkpoint is REQUIRED: every example is ~3.1-3.7k tokens (18-tool catalog floors
# them), and the 151k-vocab logits over that length OOMs the backward pass without it.
python3 -m mlx_lm lora --model "$BASE" --train --data "$SFT_DATA" \
  --iters "$ITERS" --batch-size 1 --num-layers 16 --learning-rate 1e-5 --grad-checkpoint \
  --max-seq-length "$MAXLEN" --adapter-path "$ADAPTER" --steps-per-report 25 --save-every "$ITERS"

echo "== 3/4 fuse =="
python3 -m mlx_lm fuse --model "$BASE" --adapter-path "$ADAPTER" --save-path "$FUSED"

echo "== 4/4 eval distilled model on the hard gate (12) + hardgen val (40) =="
for SET in hard hardgen; do
  echo "### $SET ###"
  MODEL="$FUSED" MT_SYS="$PLAN_PROMPT" \
    MT_DATA="scripts/fixtures/multi_turn_${SET}_data.jsonl" \
    MT_GOLD="scripts/fixtures/multi_turn_${SET}_gold.jsonl" \
    python3 scripts/bfcl_multiturn_eval.py 40
done
echo "fused model: $FUSED"
