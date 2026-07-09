#!/usr/bin/env bash
# B30 smoke: `posttrainllm reasoning-classify` trains a bag-of-trigram softmax-4
# on a synthetic 80-row 4-class fixture, evaluates on a 32-row held-out,
# asserts macro-F1 ≥ 0.5 (PRD acceptance criterion). Then re-runs in --score
# mode to confirm the round-trip adds the `reasoning_depth` field. No GPU.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX="$ROOT/evals/reasoning-classifier-fixtures"
NATIVE="$ROOT/native-mac"

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
echo "binary: $BIN"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MODEL="$TMP/reason.tgfr"

# 1) train mode — 80 train rows, 32 held-out, expect macro-F1 ≥ 0.5
echo "--- train ---"
out="$("$BIN" reasoning-classify \
  --train "$FIX/train.jsonl" \
  --heldout "$FIX/heldout.jsonl" \
  --out "$MODEL")" || fail "train exited non-zero"
echo "$out"
[ -s "$MODEL" ] || fail "expected model file at $MODEL"

# parse the macro-F1 line and assert ≥ 0.5
macroF1=$(echo "$out" | awk '/macro-F1:/ {print $2}' | tail -1)
[ -n "$macroF1" ] || fail "could not parse macro-F1 from output"
awk -v v="$macroF1" 'BEGIN{exit !(v+0 >= 0.5)}' \
  || fail "macro-F1 $macroF1 below 0.5 acceptance bar"
echo "macro-F1 ok: $macroF1"

# 2) score mode — round-trip adds reasoning_depth field
echo "--- score ---"
SCORED="$TMP/scored.jsonl"
"$BIN" reasoning-classify \
  --score "$FIX/heldout.jsonl" \
  --model "$MODEL" \
  --out "$SCORED" >/dev/null \
  || fail "score exited non-zero"
[ -s "$SCORED" ] || fail "expected scored.jsonl"
# every row should have the new field
total=$(wc -l < "$SCORED" | tr -d ' ')
with_field=$(grep -c '"reasoning_depth":' "$SCORED" || true)
[ "$with_field" = "$total" ] \
  || fail "only $with_field/$total scored rows carry reasoning_depth"
echo "scored $total rows, all carry reasoning_depth ✓"

# 3) filter mode — downsample scored to target mix
echo "--- filter ---"
BAL="$TMP/balanced.jsonl"
"$BIN" reasoning-classify \
  --filter "$SCORED" \
  --target-mix "single=0.4,multi=0.4,comparison=0.2,other=0.0" \
  --out "$BAL" >/dev/null \
  || fail "filter exited non-zero"
[ -s "$BAL" ] || fail "expected balanced.jsonl"
# `other` was set to 0 in the target — assert none survive AND that the
# filter did not collapse to empty (a misclassify-everything-as-other run
# would pass an "other=0" check while producing zero usable rows).
[ "$(wc -l < "$BAL" | tr -d ' ')" -gt 0 ] \
  || fail "filter produced empty output"
other_after=$(grep -c '"reasoning_depth":"other"' "$BAL" || true)
[ "$other_after" = "0" ] \
  || fail "expected 0 'other' rows after filter (got $other_after)"
# at least one of the surviving target classes must actually appear
for cls in single-hop multi-hop comparison; do
  c=$(grep -c "\"reasoning_depth\":\"$cls\"" "$BAL" || true)
  [ "$c" -gt 0 ] || fail "expected at least one $cls row after filter"
done
echo "filter dropped 'other' and kept positive-target classes ✓"

echo "SMOKE PASS"
