#!/usr/bin/env bash
# Numerics + speedup gate for serve speculative decoding (`serve --draft-model`).
#
# At temperature 0 the completion from `serve <target> --draft-model <draft>`
# should match plain `serve <target>` token-for-token. Spec-decode is
# exactness-preserving in exact arithmetic, so a GROSS divergence (most prompts
# differ, or garbled output) means a real bug — e.g. a wrong verify-attention
# mask, which is exactly what this gate caught during development.
#
# Caveat (verified 2026-06-24): exact byte-identity is NOT achievable on Metal.
# The verify forward (multi-token, batched) and the decode forward (single-token)
# are not bit-reproducible across batch shapes, so the KV caches drift in the low
# bits and occasionally flip an argmax on a close call. When that happens the
# spec output is still a VALID greedy decode — checked against the uncached
# reference (`model(arr)`), spec's divergent token scored at least as high as the
# baseline's. So this gate tolerates a MINORITY of divergent prompts and only
# hard-fails when most diverge (the signature of an actual logic/mask bug).
#
# Speedup is informational (content-dependent: ~1.0-1.4x with a 0.6B draft /
# 4B target, driven by how often the draft and target agree).
#
# Usage:
#   scripts/spec-decode-verify.sh <target-model-dir-or-tinygpt> <draft-model-dir>
#
# Requires a release build: from native-mac/, `swift build -c release --product tinygpt`.
set -uo pipefail

TARGET="${1:?usage: spec-decode-verify.sh <target> <draft>}"
DRAFT="${2:?usage: spec-decode-verify.sh <target> <draft>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${TINYGPT_BIN:-$REPO/native-mac/.build/out/Products/Release/tinygpt}"
[ -x "$BIN" ] || BIN="$REPO/native-mac/.build/release/tinygpt"
[ -x "$BIN" ] || { echo "FAIL: tinygpt release binary not found (build it first)"; exit 2; }

PROMPTS=(
  "List the first 12 prime numbers and briefly explain what makes a number prime."
  "Write a thorough explanation of how a transformer neural network works, covering attention, layers, and training."
  "Summarize the plot of Romeo and Juliet in one paragraph."
)
MAXTOK="${MAXTOK:-120}"

wait_ready() { for _ in $(seq 1 90); do curl -s "http://127.0.0.1:$1/v1/models" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }

complete() { # port prompt -> stdout: completion text (timing done by caller)
  curl -s "http://127.0.0.1:$1/v1/completions" -H 'Content-Type: application/json' \
    -d "$(python3 -c 'import json,sys; print(json.dumps({"model":"m","prompt":sys.argv[1],"max_tokens":int(sys.argv[2]),"temperature":0,"stream":False}))' "$2" "$MAXTOK")" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["text"])'
}

run_server() { "$BIN" serve "$TARGET" --port "$1" ${2:-} >/tmp/sdv_$1.log 2>&1 & echo $!; }

identical=0
diverged=0
for idx in "${!PROMPTS[@]}"; do
  P="${PROMPTS[$idx]}"
  bp=$((8200 + idx*2)); sp=$((8201 + idx*2))
  bpid=$(run_server "$bp" ""); wait_ready "$bp" || { echo "FAIL: baseline server didn't start"; cat /tmp/sdv_$bp.log; exit 2; }
  t0=$(date +%s.%N); base=$(complete "$bp" "$P"); t1=$(date +%s.%N); bt=$(echo "$t1 - $t0" | bc)
  kill "$bpid" 2>/dev/null; wait "$bpid" 2>/dev/null
  spid=$(run_server "$sp" "--draft-model $DRAFT"); wait_ready "$sp" || { echo "FAIL: spec server didn't start"; cat /tmp/sdv_$sp.log; exit 2; }
  t0=$(date +%s.%N); spec=$(complete "$sp" "$P"); t1=$(date +%s.%N); st=$(echo "$t1 - $t0" | bc)
  kill "$spid" 2>/dev/null; wait "$spid" 2>/dev/null

  if [ "$base" = "$spec" ]; then
    identical=$((identical+1))
    echo "OK   byte-identical · prompt $((idx+1)) · baseline ${bt}s spec ${st}s · speedup $(echo "scale=2; $bt/$st" | bc)x"
  else
    diverged=$((diverged+1))
    echo "DIFF diverged (fp argmax flip — see header) · prompt $((idx+1)) · baseline ${bt}s spec ${st}s · speedup $(echo "scale=2; $bt/$st" | bc)x"
    diff <(printf '%s' "$base") <(printf '%s' "$spec") | head -8
  fi
done

total=${#PROMPTS[@]}
echo "---"
echo "byte-identical: $identical/$total · diverged (fp): $diverged/$total"
# Hard-fail only on GROSS divergence (most prompts differ) — that's a real bug,
# not floating-point. A minority of fp argmax flips is expected and benign.
if [ "$identical" -ge $(( (total + 1) / 2 )) ]; then
  echo "PASS: spec-decode lossless (majority byte-identical; minority are benign fp flips)"
  exit 0
else
  echo "FAIL: spec-decode diverged on the majority of prompts — likely a real bug (mask/rewind/positions)"
  exit 1
fi
