#!/usr/bin/env bash
# evals/scaledown-smoke.sh — E6 V1 self-contained compression eval (pure CPU).
#
# Runs `tinygpt eval-scaledown` over a tiny QA set and asserts the compressor
# both shortens the context (ratio < 1) and keeps the answer (retention == 1).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
QA="$ROOT/evals/scaledown-fixtures/qa.jsonl"
[ -f "$QA" ] || fail "missing fixture $QA"

out="$("$BIN" eval-scaledown "$QA" --keep-frac 0.4)" || fail "eval-scaledown failed"
echo "  $out"
ratio=$(echo "$out" | sed -n 's/.*compression_ratio=\([0-9.]*\).*/\1/p')
ret=$(echo "$out"   | sed -n 's/.*answer_retention=\([0-9.]*\).*/\1/p')
python3 - "$ratio" "$ret" <<'PY'
import sys
ratio, ret = float(sys.argv[1]), float(sys.argv[2])
assert 0 < ratio < 1.0, f"compression_ratio {ratio} should shorten the context"
assert ret == 1.0, f"answer_retention {ret} — compressor dropped a gold answer"
print(f"  ratio {ratio:.3f} (<1, shortened) · retention {ret:.3f} (answers kept)")
PY
echo "SMOKE OK: eval-scaledown (E6 V1)"
