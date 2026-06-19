#!/usr/bin/env bash
# Phase-2 of "try everything we discussed": runs after the VibeThinker GSM8K job (VIBE_DONE marker).
# Each step is independent (|| logs and continues) so one failure doesn't block the rest.
B4="/Users/sarthak/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554"
VIBE="$HOME/.cache/tinygpt/models/vibethinker-3b-mlx"
GP="You are an autonomous tool-using agent. For each user turn: (1) plan the full sequence of function calls the task needs; (2) execute them, reading each tool result; (3) never repeat a call that already succeeded; (4) once every requested action is complete, stop and emit no tool call. Use the tool results to track the current state as you go."

echo "waiting for VibeThinker GSM8K (VIBE_DONE) ..."
until grep -q "VIBE_DONE" /tmp/vibe_gsm8k.log 2>/dev/null; do sleep 30; done
echo "=== GPU free $(date +%H:%M) — running remaining experiments ==="

echo "===== [1/3] DISTRIBUTED-BOUNDARY DP PoC (mlx.distributed) ====="
for N in 1 2 4; do
  echo "--- mlx.launch -n $N (effective batch = 64*$N) ---"
  mlx.launch -n "$N" scripts/dist_dp_poc.py 2>&1 | tail -5 || echo "  (n=$N failed)"
done

echo "===== [2/3] rollout_fast VALIDATION (8 breadth tasks; expect ~stock 60% => ~5/8, no errors) ====="
MODEL="$B4" MT_SYS="$GP" MT_BATCH=8 \
  MT_DATA=scripts/fixtures/multi_turn_breadth_data.jsonl MT_GOLD=scripts/fixtures/multi_turn_breadth_gold.jsonl \
  python3 scripts/rollout_fast.py 8 2>&1 | tail -8 || echo "  rollout_fast failed"

echo "===== [3/3] VibeThinker as agentic-distill BASE (file-ops gold -> SFT -> eval hard+breadth) ====="
if python3 -c "from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained('$VIBE'); raise SystemExit(0 if getattr(t,'chat_template',None) else 1)" 2>/dev/null; then
  EVAL_SETS="hard breadth" bash scripts/distill_multiturn.sh \
    "$HOME/.cache/tinygpt/rest_artifacts/gold_traj.jsonl" "$VIBE" vibe_distill 2>&1 \
    | grep -E "render|max-seq|n_train|Iter 360:|### |task-completion|fused model|Error|Traceback" || echo "  vibe distill failed"
else
  echo "  SKIP: VibeThinker has no chat_template (reasoning-specialist lacks tool-calling template) — itself a finding."
fi
echo "ALL_EXPERIMENTS_DONE"
