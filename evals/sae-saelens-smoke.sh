#!/usr/bin/env bash
# evals/sae-saelens-smoke.sh — B17 SAELens round-trip.
# Trains a tiny SAE on a gallery model, exports to SAELens format, and loads it
# back with the real `sae_lens` package. Skips gracefully (exit 0) when sae_lens
# isn't installed or no gallery model is present, so CI without the heavy dep
# stays green; run locally after `pip install sae_lens` for the real check.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

python3 -c 'import sae_lens' 2>/dev/null || { echo "SKIP: sae_lens not installed (pip install sae_lens)"; exit 0; }
MODEL="$ROOT/data/gallery/shakespeare.tinygpt"
CORPUS="$ROOT/data/examples/shakespeare.txt"
{ [ -f "$MODEL" ] && [ -f "$CORPUS" ]; } || { echo "SKIP: gallery model/corpus not present"; exit 0; }

BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

head -c 200000 "$CORPUS" > "$TMP/c.txt"
"$BIN" sae "$MODEL" --corpus "$TMP/c.txt" --layer 0 --features 512 --steps 100 --out "$TMP/probe.sae" >/dev/null 2>&1 \
    || fail "sae training failed"
"$BIN" sae-to-saelens "$TMP/probe.sae" --out "$TMP/sl" >/dev/null 2>&1 || fail "sae-to-saelens failed"
python3 "$ROOT/scripts/sae_saelens_roundtrip.py" "$TMP/sl" 256 512 2>&1 | grep -v 'RequestsDependencyWarning\|warnings.warn' \
    || fail "SAELens round-trip failed"
echo "SMOKE OK: sae-to-saelens round-trips in SAELens"
