#!/usr/bin/env bash
# evals/automix-smoke.sh — B21 micro-AutoMixer search-loop smoke.
#
# Runs `posttrainllm automix --dry-run` (synthetic scorer with a known geometric
# optimum, no GPU/training) over 3 corpora and asserts the surrogate-guided
# search converges near that optimum. This exercises the whole loop —
# Dirichlet sampling, quadratic surrogate fit, EI proposal, stop rule — in CI.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

"$BIN" automix --corpus code=/dev/null --corpus web=/dev/null --corpus math=/dev/null \
    --dry-run --proxy-runs 8 --max-iters 8 --out "$TMP/am.jsonl" >/dev/null 2>&1 \
    || fail "automix dry-run failed"
[ -s "$TMP/am.jsonl" ] || fail "report not written"
[ -s "$TMP/automix-recommendation.json" ] || fail "recommendation not written"

python3 - "$TMP/automix-recommendation.json" <<'PY'
import json, sys
rec = json.load(open(sys.argv[1]))
r = rec["ratio"]
# synthetic target = geometric 0.5^i normalized over 3 corpora
tgt = {"code": 4/7, "web": 2/7, "math": 1/7}
dev = max(abs(r[k] - tgt[k]) for k in tgt)
ssum = sum(r.values())
assert abs(ssum - 1.0) < 1e-4, f"ratios must sum to 1, got {ssum}"
assert dev < 0.12, f"recommendation {r} too far from optimum {tgt} (dev {dev:.3f})"
assert rec["best_score"] > -0.02, f"best_score {rec['best_score']} not near optimum (0)"
print(f"  converged: code={r['code']:.3f} web={r['web']:.3f} math={r['math']:.3f} "
      f"(max dev {dev:.3f} from optimum, score {rec['best_score']:.4f})")
PY

echo "SMOKE OK: automix search loop"
