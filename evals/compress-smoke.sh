#!/usr/bin/env bash
# evals/compress-smoke.sh — B25 V1 extractive-compression smoke.
#
# Compresses a doc mixing RoPE sentences with off-topic filler against a RoPE
# query; asserts the output keeps a relevant sentence, drops the off-topic
# filler, and is shorter than the original.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
DOC="$ROOT/evals/compress-fixtures/doc.txt"
[ -f "$DOC" ] || fail "missing fixture $DOC"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/compressed.txt"

"$BIN" compress "what is RoPE rotary position embedding" \
    --doc "$DOC" --threshold 0.2 --out "$OUT" >/dev/null 2>&1 || fail "compress failed"
[ -s "$OUT" ] || fail "no compressed output"

orig_chars=$(wc -c < "$DOC" | tr -d ' ')
kept_chars=$(wc -c < "$OUT" | tr -d ' ')

grep -qi "rope" "$OUT" || fail "compressed output dropped all RoPE sentences"
if grep -qi "croissant\|picnic\|barked" "$OUT"; then fail "off-topic filler survived compression"; fi
[ "$kept_chars" -lt "$orig_chars" ] || fail "output not shorter ($kept_chars >= $orig_chars)"

echo "  kept RoPE content, dropped filler; ${orig_chars}->${kept_chars} chars"
echo "SMOKE OK: compress (B25 V1 lexical)"
