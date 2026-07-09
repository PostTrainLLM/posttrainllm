#!/usr/bin/env bash
# evals/project-validate-smoke.sh — B31 posttrainllm validate-project.
# The shipped example manifest validates; a duplicate-id manifest fails.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"

"$BIN" validate-project "$ROOT/examples/posttrainllm.project.json" >/dev/null 2>&1 \
    || fail "the shipped example manifest should validate"

if "$BIN" validate-project "$ROOT/evals/project-fixtures/invalid-dup.json" >/dev/null 2>&1; then
    fail "duplicate-model-id manifest should NOT validate"
fi

# B31 gallery-resolve: example resolves against a gallery containing its pins…
"$BIN" validate-project "$ROOT/examples/posttrainllm.project.json" \
    --gallery "$ROOT/evals/project-fixtures/gallery.json" >/dev/null 2>&1 \
    || fail "example pins should resolve in the full gallery fixture"
# …but fails against a gallery missing some pins.
PARTIAL="$(mktemp)"; trap 'rm -f "$PARTIAL"' EXIT
printf '{"version":1,"models":[{"id":"qwen3-4b-instruct-2507","name":"x","file":"x.bin"}]}' > "$PARTIAL"
if "$BIN" validate-project "$ROOT/examples/posttrainllm.project.json" --gallery "$PARTIAL" >/dev/null 2>&1; then
    fail "gallery missing pins should NOT resolve"
fi

echo "SMOKE OK: validate-project (B31) — structural + gallery-resolve"
