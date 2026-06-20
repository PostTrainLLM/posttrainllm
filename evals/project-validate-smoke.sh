#!/usr/bin/env bash
# evals/project-validate-smoke.sh — B31 tinygpt validate-project.
# The shipped example manifest validates; a duplicate-id manifest fails.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"

"$BIN" validate-project "$ROOT/examples/tinygpt.project.json" >/dev/null 2>&1 \
    || fail "the shipped example manifest should validate"

if "$BIN" validate-project "$ROOT/evals/project-fixtures/invalid-dup.json" >/dev/null 2>&1; then
    fail "duplicate-model-id manifest should NOT validate"
fi

echo "SMOKE OK: validate-project (B31) — example valid, dup-id rejected"
