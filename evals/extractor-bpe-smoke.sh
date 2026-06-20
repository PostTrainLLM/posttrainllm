#!/usr/bin/env bash
# evals/extractor-bpe-smoke.sh — C4 BPE-tokenizer path for the router trainer.
# Runs `train-extractor --tokenizer <hf-dir> --dry-run` so the BPE tokenizer
# loads and the model builds (fast, no training). Needs an HF tokenizer dir:
# set EXTRACTOR_BPE_TOKENIZER, or it uses /tmp/gpt2-tok; skips (exit 0) if
# neither is present so CI without the download stays green.
#
# To populate locally:
#   mkdir -p /tmp/gpt2-tok && curl -sL https://huggingface.co/gpt2/resolve/main/tokenizer.json -o /tmp/gpt2-tok/tokenizer.json
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"

TOK="${EXTRACTOR_BPE_TOKENIZER:-/tmp/gpt2-tok}"
[ -f "$TOK/tokenizer.json" ] || { echo "SKIP: no BPE tokenizer at $TOK (set EXTRACTOR_BPE_TOKENIZER or fetch gpt2 — see header)"; exit 0; }

DATA="$ROOT/evals/extractor-bpe-fixtures/data.jsonl"
[ -f "$DATA" ] || fail "missing fixture $DATA"

out="$("$BIN" train-extractor "$DATA" --tokenizer "$TOK" --vocab-size 50257 --dry-run 2>&1)"
echo "$out" | sed 's/^/  /'
echo "$out" | grep -q "loaded BPE tokenizer" || fail "BPE tokenizer did not load"
echo "$out" | grep -q "3 classes"            || fail "expected 3 tool classes from the fixture"
echo "SMOKE OK: train-extractor BPE tokenizer path (C4)"
