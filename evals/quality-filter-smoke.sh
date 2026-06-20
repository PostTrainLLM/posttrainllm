#!/usr/bin/env bash
# evals/quality-filter-smoke.sh — B10 quality classifier end-to-end smoke.
#
# Trains a tiny bag-of-ngrams quality classifier on fixture docs, then
# exercises the --score sidecar mode (one {doc_id,score} JSONL line per
# input doc) and asserts: row count, valid JSON fields, scores in [0,1],
# and that science docs out-score spam docs (the classifier learned).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
FIX="$ROOT/evals/quality-filter-fixtures"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

MODEL="$TMP/qc.tgfq"
SCORES="$TMP/scores.jsonl"

echo "[1/3] train classifier"
"$BIN" train-quality-classifier \
    --positive "$FIX/positive.txt" --negative "$FIX/negative.txt" \
    --out "$MODEL" --epochs 30 --seed 42 >/dev/null
[ -s "$MODEL" ] || fail "classifier model not written"

echo "[2/3] score (sidecar mode, --per-line)"
"$BIN" quality-filter "$FIX/input.txt" --classifier "$MODEL" \
    --score "$SCORES" --per-line >/dev/null
[ -s "$SCORES" ] || fail "scores sidecar not written"

echo "[3/3] assert sidecar shape + separation"
python3 - "$SCORES" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert len(rows) == 4, f"expected 4 score rows, got {len(rows)}"
for i, r in enumerate(rows):
    assert r["doc_id"] == i, f"doc_id mismatch at row {i}: {r}"
    assert 0.0 <= r["score"] <= 1.0, f"score out of [0,1]: {r}"
# input.txt: rows 0,2 = science; rows 1,3 = spam
sci = (rows[0]["score"] + rows[2]["score"]) / 2
spam = (rows[1]["score"] + rows[3]["score"]) / 2
assert sci > spam, f"science ({sci:.3f}) should out-score spam ({spam:.3f})"
print(f"  4 rows OK · science avg {sci:.3f} > spam avg {spam:.3f}")
PY

echo "SMOKE OK: quality-filter --score"
