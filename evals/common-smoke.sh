#!/usr/bin/env bash
# Test for evals/_common.sh — verifies the shared smoke-script helpers
# (resolve_posttrainllm, fail) behave correctly. No GPU, no network, no build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

pass=0; failed=0
check() { if eval "$2"; then echo "  ✓ $1"; pass=$((pass+1)); else echo "  ✗ $1"; failed=$((failed+1)); fi; }

# 1) fail() is defined as a function by the sourced helper
check "fail() is defined" '[ "$(type -t fail)" = function ]'

tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# 2) prefers an existing release binary under $NATIVE
mkdir -p "$tmp/.build/release"
printf '#!/bin/sh\necho fake\n' > "$tmp/.build/release/posttrainllm"; chmod +x "$tmp/.build/release/posttrainllm"
got="$(NATIVE="$tmp" resolve_posttrainllm 2>/dev/null)"
check "prefers existing release binary" '[ "$got" = "$tmp/.build/release/posttrainllm" ]'

# 3) falls back to debug when no release exists
rm -rf "$tmp/.build/release"; mkdir -p "$tmp/.build/debug"
printf '#!/bin/sh\necho fake\n' > "$tmp/.build/debug/posttrainllm"; chmod +x "$tmp/.build/debug/posttrainllm"
got="$(NATIVE="$tmp" resolve_posttrainllm 2>/dev/null)"
check "falls back to debug binary" '[ "$got" = "$tmp/.build/debug/posttrainllm" ]'

# 4) diagnostics go to stderr — stdout is the path only (single clean line)
got="$(NATIVE="$tmp" resolve_posttrainllm 2>/dev/null)"
check "stdout is a single clean line" '[ "$(printf "%s" "$got" | wc -l | tr -d " ")" = 0 ]'

# 5) resolves the real repo binary if one is already built (no build triggered)
if [ -x "$ROOT/native-mac/.build/release/posttrainllm" ] || [ -x "$ROOT/native-mac/.build/debug/posttrainllm" ]; then
  got="$(resolve_posttrainllm 2>/dev/null)"
  check "resolves a real executable from the repo" '[ -x "$got" ]'
else
  echo "  - skipped real-binary check (no build present)"
fi

echo "common-smoke: $pass passed, $failed failed"
[ "$failed" -eq 0 ] || exit 1
echo "ALL common-smoke checks passed."
