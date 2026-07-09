#!/usr/bin/env bash
# A1 acceptance — re-run the +3pp BFCL ship gate against an existing adapter
# from a clean checkout. RUN ON A GPU MAC with a BFCL checkout.
#
#   BFCL_ROOT=~/bfcl ADAPTER=specialists/a1-tool-caller/a1.lora bash evals/a1-acceptance.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"

BASE="${BASE:-qwen3-4b-instruct-2507}"
ADAPTER="${ADAPTER:?set ADAPTER=<a1.lora>}"
BFCL_ROOT="${BFCL_ROOT:?set BFCL_ROOT=<local BFCL checkout>}"
THRESH_PP="${THRESH_PP:-3}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

"$BIN" eval-bfcl "$BASE" --bfcl-root "$BFCL_ROOT" --out "$WORK/baseline.jsonl"
"$BIN" eval-bfcl "$BASE" --lora "$ADAPTER" --bfcl-root "$BFCL_ROOT" --out "$WORK/candidate.jsonl"
"$BIN" eval-gate --baseline "$WORK/baseline.jsonl" --candidate "$WORK/candidate.jsonl" \
    --threshold "$THRESH_PP" --out "$WORK/gate-result.json" \
    || fail "A1 ship gate FAILED (adapter did not clear +${THRESH_PP}pp BFCL)"
echo "ACCEPTANCE OK: A1 adapter clears +${THRESH_PP}pp BFCL"
