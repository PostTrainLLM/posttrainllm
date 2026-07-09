# evals/_common.sh — shared helpers for posttrainllm eval smoke scripts.
#
# Source this AFTER `set -euo pipefail` and after defining $ROOT:
#   source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
#
# Consolidated from the binary-resolution + fail() boilerplate that was
# copy-pasted verbatim across the smoke scripts.

# fail <msg>: print a SMOKE FAIL line to stderr and exit non-zero.
fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

# resolve_posttrainllm: print the path to a usable `posttrainllm` binary, preferring a
# release build, then debug, and building debug if neither exists. Honors
# $NATIVE if set, else derives it from $ROOT.
#
# Diagnostics go to stderr so the binary path is the only thing on stdout:
#   BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
resolve_posttrainllm() {
  local native="${NATIVE:-$ROOT/native-mac}"
  local bin=""
  for cand in "$native/.build/release/posttrainllm" "$native/.build/debug/posttrainllm"; do
    [ -x "$cand" ] && { bin="$cand"; break; }
  done
  if [ -z "$bin" ]; then
    echo "no built binary found — building debug…" >&2
    # Prefer the conventional Xcode path; fall back to the active toolchain
    # if it isn't present (e.g. an Xcode beta installed under a different name).
    local devdir="/Applications/Xcode.app/Contents/Developer"
    [ -d "$devdir" ] || devdir="$(xcode-select -p 2>/dev/null || true)"
    ( cd "$native" && DEVELOPER_DIR="$devdir" xcrun swift build ) >&2
    bin="$native/.build/debug/posttrainllm"
  fi
  [ -x "$bin" ] || return 1
  printf '%s\n' "$bin"
}
