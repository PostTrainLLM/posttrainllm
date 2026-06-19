#!/usr/bin/env bash
# B29 smoke: `tinygpt traces-to-data` reads 5 fixture .atraj files,
# applies tool-echo drop + exact dedup + MinHash near-dedup, and emits
# exactly 2 SFT rows (the two semantically-distinct prompts).
#
# Fixtures (under evals/traces-to-data-fixtures/):
#   01 "What is 2 + 2?"            → keep
#   02 same as 01                  → exact-dropped
#   03 "What is 2 + 2 ?" (spaces)  → MinHash-dropped (near-dup of 01)
#   04 "What is the capital of France?" → keep
#   05 tool-call without answer    → tool-echo-dropped
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX="$ROOT/evals/traces-to-data-fixtures"
NATIVE="$ROOT/native-mac"

BIN=""
for cand in "$NATIVE/.build/release/tinygpt" "$NATIVE/.build/debug/tinygpt"; do
  [ -x "$cand" ] && BIN="$cand" && break
done
if [ -z "$BIN" ]; then
  echo "no built binary found — building debug…"
  (cd "$NATIVE" && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift build)
  BIN="$NATIVE/.build/debug/tinygpt"
fi
echo "binary: $BIN"

fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/sft.jsonl"

# 1) default settings (threshold 0.85) — math near-dup (only one space
# differs) has Jaccard ~0.75, below default; expect 3 emitted rows:
# math, math-near-dup, geography. Tool-echo and exact-dup are dropped.
echo "--- default filters (threshold 0.85) ---"
out="$("$BIN" traces-to-data "$FIX" --task math-and-geo --out "$OUT")" \
  || fail "default run exited non-zero"
echo "$out"
[ -s "$OUT" ] || fail "expected non-empty output JSONL"
rows="$(wc -l < "$OUT" | tr -d ' ')"
[ "$rows" = "3" ] || fail "expected 3 rows at default threshold, got $rows"
grep -q '"What is 2 + 2?"' "$OUT" || fail "missing math prompt"
grep -q '"What is the capital of France?"' "$OUT" || fail "missing geography prompt"
# Assistant content is JSON inside JSON, so \"answer\": \"…\" is escaped on disk.
grep -q '\\"4\\"' "$OUT" || fail "missing math answer 4"
grep -q '\\"Paris\\"' "$OUT" || fail "missing geography answer Paris"

# Tool-echo trajectory's bare tool-call JSON must NOT appear as an
# assistant response in the output.
if grep -q '"{\\\"tool\\\":' "$OUT"; then
  fail "tool-echo assistant turn leaked into output"
fi

echo "$out" | grep -q "raw (user→assistant) samples harvested: 4" \
  || fail "expected 4 harvested samples (5 trajectories, 1 tool-echo dropped at harvest)"
echo "$out" | grep -q "exact-duplicates dropped:               1" \
  || fail "expected 1 exact-duplicate drop"

# 1b) lower threshold (0.6) — math near-dup now collapses. Expect 2 rows.
echo "--- looser threshold (0.6) ---"
OUT_LOOSE="$TMP/sft-loose.jsonl"
out2="$("$BIN" traces-to-data "$FIX" --task math-and-geo --out "$OUT_LOOSE" --minhash-threshold 0.6)" \
  || fail "looser run exited non-zero"
rows_loose="$(wc -l < "$OUT_LOOSE" | tr -d ' ')"
[ "$rows_loose" = "2" ] || fail "expected 2 rows at threshold 0.6, got $rows_loose"
echo "$out2" | grep -q "minhash near-duplicates dropped:        1" \
  || fail "expected 1 MinHash near-duplicate drop at threshold 0.6"

# 2) --no-tool-echo-drop — expect 4 rows (math + math-near-dup + geo + bare tool call)
echo "--- --no-tool-echo-drop ---"
OUT2="$TMP/sft-noecho.jsonl"
"$BIN" traces-to-data "$FIX" --task all --out "$OUT2" --no-tool-echo-drop >/dev/null \
  || fail "--no-tool-echo-drop run exited non-zero"
rows2="$(wc -l < "$OUT2" | tr -d ' ')"
[ "$rows2" = "4" ] \
  || fail "expected 4 rows with --no-tool-echo-drop, got $rows2"

# 3) --dry-run does not write the output
echo "--- --dry-run ---"
OUT3="$TMP/sft-dry.jsonl"
"$BIN" traces-to-data "$FIX" --task all --out "$OUT3" --dry-run >/dev/null \
  || fail "--dry-run exited non-zero"
[ ! -f "$OUT3" ] || fail "--dry-run should not have written $OUT3"

# 4) --judge-model is explicitly deferred — should exit non-zero with a message
echo "--- --judge-model rejection ---"
if "$BIN" traces-to-data "$FIX" --task t --out "$TMP/never.jsonl" --judge-model fakeq3 >/dev/null 2>&1; then
  fail "expected non-zero exit when --judge-model is passed (V1 deferred)"
fi

echo "SMOKE PASS"
