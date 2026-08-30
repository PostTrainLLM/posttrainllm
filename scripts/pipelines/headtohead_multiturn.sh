#!/usr/bin/env bash
# Conclusive head-to-head on the multi-turn HARD gate (the frontier-validated one):
# every candidate, same plan-then-execute system prompt, same 12 tasks.
#
#   - local mlx candidates  -> scripts/bfcl/bfcl_multiturn_eval.py     (MODEL=<path>)
#   - OpenAI-endpoint ones  -> scripts/bfcl/bfcl_multiturn_deepseek.py (DS_URL + DS_MODEL)
#     (frontier = api.deepseek.com; Gemma = LM Studio at :1234)
#
# Edit CANDIDATES then: scripts/pipelines/headtohead_multiturn.sh [n=12] [data_tag=hard]
set -uo pipefail
N="${1:-12}"; TAG="${2:-hard}"
DATA="scripts/fixtures/multi_turn_${TAG}_data.jsonl"
GOLD="scripts/fixtures/multi_turn_${TAG}_gold.jsonl"
B4="/Users/sarthak/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554"
LMS="http://localhost:1234/v1/chat/completions"

PLAN_PROMPT="You are an autonomous tool-using agent. For each user turn: (1) first think briefly about the FULL sequence of function calls the task needs; (2) then execute them one at a time, reading each tool result before the next call; (3) NEVER repeat a call that already succeeded — check the latest tool results to see what is already done; (4) once EVERY requested action is complete, stop and emit no tool call. Track the current directory and existing files/dirs from the tool results as you go."

# name | kind(local|openai) | model_ref | url(openai only)
CANDIDATES=(
  "DeepSeek-V4-pro (frontier anchor)|openai|deepseek-v4-pro|https://api.deepseek.com/chat/completions"
  "Gemma-3-12b (Pace incumbent?)|openai|google/gemma-3-12b|$LMS"
  "Gemma-4-12b-qat|openai|google/gemma-4-12b-qat|$LMS"
  "Qwen3-4B-2507 stock|local|$B4|"
  "Qwen3-4B-2507 DISTILLED|local|/tmp/mt4b_fused|"
)

echo "# Head-to-head — multi-turn $TAG gate (n=$N, plan prompt)"
echo "| Model | task-completion |"
echo "|---|---|"
for c in "${CANDIDATES[@]}"; do
  IFS='|' read -r name kind ref url <<< "$c"
  if [ "$kind" = local ]; then
    pct=$(MODEL="$ref" MT_SYS="$PLAN_PROMPT" MT_DATA="$DATA" MT_GOLD="$GOLD" \
          python3 scripts/bfcl/bfcl_multiturn_eval.py "$N" 2>/dev/null | grep -oE "= [0-9.]+% ==" | grep -oE "[0-9.]+")
  else
    keyarg="/tmp/deepseek_key"; [ "$url" = "$LMS" ] && keyarg="/tmp/_no_key"
    pct=$(DS_KEY_FILE="$keyarg" DS_URL="$url" DS_MODEL="$ref" MT_SYS="$PLAN_PROMPT" \
          MT_DATA="$DATA" MT_GOLD="$GOLD" python3 scripts/bfcl/bfcl_multiturn_deepseek.py "$N" 2>/dev/null \
          | grep -oE "= [0-9.]+%" | grep -oE "[0-9.]+")
  fi
  echo "| $name | ${pct:-ERR}% |"
done
