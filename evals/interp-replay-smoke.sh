#!/usr/bin/env bash
# evals/interp-replay-smoke.sh — B13 interp-replay orchestrator (--dry-run).
# Creates a fake checkpoint history and asserts the walk emits one timeline row
# per (checkpoint × layer) with correct steps + schema.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

for s in 100 200 300; do : > "$TMP/run.step-$s.tinygpt"; done
: > "$TMP/run.final.tinygpt"   # no step marker → should be ignored

"$BIN" interp-replay "$TMP" --probe sae --layers 0,1 --out "$TMP/timeline.jsonl" --dry-run >/dev/null 2>&1 \
    || fail "interp-replay failed"
python3 - "$TMP/timeline.jsonl" <<'PY' || fail "timeline assertions failed"
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert len(rows) == 6, f"expected 3 checkpoints x 2 layers = 6 rows, got {len(rows)}"
steps = sorted({r["step"] for r in rows})
assert steps == [100, 200, 300], f"steps {steps} (final.tinygpt should be dropped)"
for r in rows:
    assert {"step","ckpt_hash","probe","layer","metric","value"} <= r.keys(), f"bad schema: {r}"
print(f"  6 rows, steps {steps}, schema OK")
PY
echo "SMOKE OK: interp-replay (B13 dry-run)"
