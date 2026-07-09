#!/usr/bin/env bash
# Guarded runner for the B26 full-vs-deferred BFCL acceptance gate.
#
# This is intentionally protected by --confirm-heavy-run because it starts two
# real BFCL runs against a model. Use the smoke script for no-model validation:
#   bash evals/b26-deferred-parity-smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TINYGPT="${TINYGPT:-$ROOT/native-mac/.build/arm64-apple-macosx/release/posttrainllm}"
MODEL=""
TOOLS=""
OUT_DIR="/tmp/posttrainllm-b26"
CATEGORIES="simple,multiple,parallel,parallel_multiple,relevance,irrelevance,live_simple,live_multiple,live_parallel,live_parallel_multiple"
BFCL_ROOT=""
BFCL_MODEL=""
SERVE_PORT="8097"
FORCE=0
CONFIRM=0
DRY_RUN=0

usage() {
  cat <<EOF
usage: evals/b26-deferred-parity-run.sh --model <path> --tools <json> --confirm-heavy-run [options]

Runs the real B26 acceptance gate:
  1. posttrainllm eval-bfcl --tool-mode full
  2. posttrainllm eval-bfcl --tool-mode deferred
  3. scripts/b26_deferred_parity_report.py --require-hop-stats

Options:
  --model PATH             Specialist model path or HF dir (required)
  --tools JSON             OpenAI-compatible tool catalog JSON (required)
  --out-dir DIR            Artifact directory (default: /tmp/posttrainllm-b26)
  --categories CSV         BFCL categories CSV (default: 10-category gate)
  --bfcl-root DIR          Override local BFCL checkout
  --bfcl-model NAME        Override BFCL registry model id
  --serve-port N           Port for the managed posttrainllm serve (default: 8097)
  --posttrainllm PATH           posttrainllm binary (default: native-mac release binary)
  --force                  Remove existing gate artifacts before running
  --dry-run                Print commands without starting model evals
  --confirm-heavy-run      Required; acknowledges this starts real model evals
  -h, --help               Show this help

Environment:
  TINYGPT                  Alternative posttrainllm binary path

Outputs:
  <out-dir>/bfcl-full.jsonl
  <out-dir>/bfcl-deferred.jsonl
  <out-dir>/b26-parity.json
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="${2:?--model needs a value}"; shift 2 ;;
    --tools) TOOLS="${2:?--tools needs a value}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:?--out-dir needs a value}"; shift 2 ;;
    --categories|--tasks) CATEGORIES="${2:?--categories needs a value}"; shift 2 ;;
    --bfcl-root) BFCL_ROOT="${2:?--bfcl-root needs a value}"; shift 2 ;;
    --bfcl-model) BFCL_MODEL="${2:?--bfcl-model needs a value}"; shift 2 ;;
    --serve-port) SERVE_PORT="${2:?--serve-port needs a value}"; shift 2 ;;
    --posttrainllm) TINYGPT="${2:?--posttrainllm needs a value}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --confirm-heavy-run) CONFIRM=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

print_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    print_cmd "$@"
  else
    "$@"
  fi
}

if [[ "$CONFIRM" -ne 1 && "$DRY_RUN" -ne 1 ]]; then
  echo "refusing to start the real B26 gate without --confirm-heavy-run" >&2
  usage >&2
  exit 2
fi
if [[ -z "$MODEL" || -z "$TOOLS" ]]; then
  echo "--model and --tools are required" >&2
  usage >&2
  exit 2
fi
if [[ "$DRY_RUN" -ne 1 && ! -x "$TINYGPT" ]]; then
  echo "posttrainllm binary is not executable: $TINYGPT" >&2
  echo "Build it first, for example:" >&2
  echo "  cd '$ROOT/native-mac' && swift build -c release --product posttrainllm" >&2
  exit 2
fi
if [[ "$DRY_RUN" -ne 1 && ! -e "$MODEL" ]]; then
  echo "model path does not exist: $MODEL" >&2
  exit 2
fi
if [[ "$DRY_RUN" -ne 1 && ! -f "$TOOLS" ]]; then
  echo "tools JSON does not exist: $TOOLS" >&2
  exit 2
fi

FULL_JSONL="$OUT_DIR/bfcl-full.jsonl"
DEFERRED_JSONL="$OUT_DIR/bfcl-deferred.jsonl"
REPORT_JSON="$OUT_DIR/b26-parity.json"

run_cmd mkdir -p "$OUT_DIR"

if [[ "$FORCE" -eq 1 ]]; then
  run_cmd rm -f "$FULL_JSONL" "$DEFERRED_JSONL" "$REPORT_JSON"
elif [[ "$DRY_RUN" -ne 1 && ( -e "$FULL_JSONL" || -e "$DEFERRED_JSONL" || -e "$REPORT_JSON" ) ]]; then
  echo "refusing to append to existing B26 artifacts under $OUT_DIR; pass --force to replace them" >&2
  exit 2
fi

COMMON_ARGS=(
  --tools "$TOOLS"
  --categories "$CATEGORIES"
  --serve-port "$SERVE_PORT"
)
if [[ -n "$BFCL_ROOT" ]]; then
  COMMON_ARGS+=(--bfcl-root "$BFCL_ROOT")
fi
if [[ -n "$BFCL_MODEL" ]]; then
  COMMON_ARGS+=(--bfcl-model "$BFCL_MODEL")
fi

echo "[b26] full-schema BFCL -> $FULL_JSONL"
run_cmd "$TINYGPT" eval-bfcl "$MODEL" \
  "${COMMON_ARGS[@]}" \
  --tool-mode full \
  --model-name b26-full \
  --out "$FULL_JSONL"

echo "[b26] deferred-tool BFCL -> $DEFERRED_JSONL"
run_cmd "$TINYGPT" eval-bfcl "$MODEL" \
  "${COMMON_ARGS[@]}" \
  --tool-mode deferred \
  --model-name b26-deferred \
  --out "$DEFERRED_JSONL"

echo "[b26] parity report -> $REPORT_JSON"
run_cmd python3 "$ROOT/scripts/b26_deferred_parity_report.py" \
  --full "$FULL_JSONL" \
  --deferred "$DEFERRED_JSONL" \
  --require-hop-stats \
  --out "$REPORT_JSON"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[b26] dry run only; no evals were started."
fi
