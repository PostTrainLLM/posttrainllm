#!/usr/bin/env bash
# evals/determinism-smoke.sh — C9 training determinism harness.
#
# Runs the SAME tiny training twice with the same --seed and compares the
# per-step loss trajectories (captured via --log-jsonl). Asserts:
#   1. step-0 loss is BIT-EXACT (model init + first forward are deterministic),
#   2. the max per-step divergence stays within tolerance,
#   3. a DIFFERENT seed produces a different trajectory (sanity).
#
# Finding (2026-06-20): MLX/Metal training is reproducible to ~1e-5 but NOT
# bit-exact past step 0 — GPU gradient reductions sum in nondeterministic
# order. So full bit-exact step-N replay is not achievable on this backend;
# this harness instead guards against a determinism *regression* (a real bug
# would diverge by O(1), not O(1e-5)). See docs/determinism.md.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
CORPUS="$ROOT/data/examples/tiny-corpus.txt"
[ -f "$CORPUS" ] || fail "missing corpus $CORPUS"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
TOL="${DETERMINISM_TOL:-0.01}"   # max allowed |loss divergence| at same seed

run() {  # run <seed> <out.jsonl>
  "$BIN" train --preset tiny --corpus "$CORPUS" --steps 6 --seed "$1" \
      --log-jsonl "$2" --out "$TMP/m.tinygpt" >/dev/null 2>&1 || fail "train failed (seed $1)"
}

echo "[1/3] two runs, same seed 42"
run 42 "$TMP/a.jsonl"
run 42 "$TMP/b.jsonl"
echo "[2/3] one run, seed 7 (sanity)"
run 7  "$TMP/c.jsonl"

echo "[3/3] compare"
python3 - "$TMP/a.jsonl" "$TMP/b.jsonl" "$TMP/c.jsonl" "$TOL" <<'PY'
import json, sys
def losses(p): return [json.loads(l)["loss"] for l in open(p) if l.strip() and '"loss"' in l]
a, b, c = losses(sys.argv[1]), losses(sys.argv[2]), losses(sys.argv[3])
tol = float(sys.argv[4])
assert a and b and c, "no loss data captured"
assert len(a) == len(b), f"step count mismatch {len(a)} vs {len(b)}"
# 1. step-0 bit-exact
assert a[0] == b[0], f"step-0 not bit-exact: {a[0]!r} vs {b[0]!r}"
# 2. same-seed divergence within tolerance
dmax = max(abs(x - y) for x, y in zip(a, b))
assert dmax <= tol, f"same-seed divergence {dmax:.2e} exceeds tol {tol:.2e} (determinism regression?)"
# 3. different seed actually differs
ddiff = max(abs(x - y) for x, y in zip(a, c))
assert ddiff > dmax, f"seed 7 trajectory ({ddiff:.2e}) not distinct from seed 42"
print(f"  step-0 bit-exact: {a[0]:.6f}")
print(f"  same-seed max divergence: {dmax:.2e} (<= {tol:.0e}) — reproducible, not bit-exact past step 0")
print(f"  cross-seed divergence:    {ddiff:.2e} (distinct trajectory)")
PY

echo "SMOKE OK: determinism harness"
