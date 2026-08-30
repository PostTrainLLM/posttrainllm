#!/usr/bin/env bash
#
# run_quality_evals.sh — drive lm-evaluation-harness against the flagship
# posttrainllm checkpoint. Wraps `python_ref/lm_eval_tinygpt.py` with sane
# defaults; writes per-task JSON into `bench/results/<model-tag>-<date>/`.
#
# Pre-reqs (one-time):
#   1. Build the posttrainllm CLI:
#        cd native-mac
#        DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
#          xcodebuild -scheme posttrainllm -destination "platform=macOS" \
#          -derivedDataPath /tmp/posttrainllm-smoke -configuration Release build
#      (this is the same incantation the project's smoke build uses; the
#       built binary lands at /tmp/posttrainllm-smoke/Build/Products/Release/posttrainllm)
#
#   2. Wire `case "serve":` into Sources/TinyGPT/TinyGPT.swift's dispatch.
#      See TODO(serve-merge) in that file. Until then `posttrainllm serve` is
#      compiled-in but not callable via the CLI.
#
#   3. Install lm-evaluation-harness:
#        python -m venv .venv
#        source .venv/bin/activate
#        pip install lm-eval==0.4.10
#      ^ pin 0.4.10 because 0.4.11 has a stop-sequence bug that breaks
#        generate-until tasks (GSM8K, HumanEval, IFEval). See
#        docs/integrations/lm_eval_integration.md "Known issues" for details.
#      (this script does NOT auto-install pip packages — the project's
#       AGENTS.md prohibits unsupervised installs. Run the install manually.)
#
# Usage:
#   evals/run_quality_evals.sh                         # flagship + default task set
#   evals/run_quality_evals.sh /path/to/model.tinygpt  # explicit checkpoint
#   TASKS=hellaswag evals/run_quality_evals.sh         # only one task
#   LIMIT=50 evals/run_quality_evals.sh                # smoke-test with 50 examples/task

set -eo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

MODEL_PATH="${1:-/tmp/flagship-huge.tinygpt}"
# Default task set — fast multiple-choice tasks that work well on small
# checkpoints. Add GSM8K / IFEval / MMLU-Pro for stronger signals if your
# model can handle them (and you have an hour to spare).
TASKS="${TASKS:-hellaswag,arc_easy}"
LIMIT="${LIMIT:-}"  # empty = full task; set to e.g. 50 for smoke runs
MAX_CONTEXT="${MAX_CONTEXT:-}"  # empty = model's native context length

# Locate the binary; fall back to PATH lookup.
TINYGPT_BIN="${TINYGPT_BIN:-/tmp/posttrainllm-smoke/Build/Products/Release/posttrainllm}"
if [[ ! -x "$TINYGPT_BIN" ]]; then
    TINYGPT_BIN="$(command -v posttrainllm || true)"
    if [[ -z "$TINYGPT_BIN" ]]; then
        echo "error: can't find posttrainllm binary. Build it first or set TINYGPT_BIN." >&2
        exit 1
    fi
fi

# Pre-flight: confirm `posttrainllm serve` is callable. If the main case dispatch
# in TinyGPT.swift isn't wired yet (see TODO(serve-merge) in that file),
# fall back to the stand-in `posttrainllm-serve-smoke` binary.
if ! "$TINYGPT_BIN" serve --help >/dev/null 2>&1; then
    SMOKE_BIN="$(dirname "$TINYGPT_BIN")/posttrainllm-serve-smoke"
    if [[ -x "$SMOKE_BIN" ]]; then
        echo "note: main 'posttrainllm' lacks 'serve' subcommand — falling back to $SMOKE_BIN" >&2
        TINYGPT_BIN="$SMOKE_BIN"
    else
        echo "error: '$TINYGPT_BIN serve' isn't callable and posttrainllm-serve-smoke is missing." >&2
        echo "  Wire case \"serve\": into Sources/TinyGPT/TinyGPT.swift, OR build the smoke target:" >&2
        echo "    xcodebuild -scheme posttrainllm-serve-smoke -derivedDataPath /tmp/posttrainllm-smoke -configuration Release build" >&2
        exit 1
    fi
fi

# Sanity: file exists.
if [[ ! -e "$MODEL_PATH" ]]; then
    echo "error: model path doesn't exist: $MODEL_PATH" >&2
    exit 1
fi

# Output dir with date stamp.
MODEL_TAG="$(basename "$MODEL_PATH" .tinygpt)"
DATE_STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$REPO_ROOT/bench/results/${MODEL_TAG}-${DATE_STAMP}"
mkdir -p "$OUT_DIR"

# Extra args.
EXTRA_ARGS=()
if [[ -n "$LIMIT" ]]; then
    EXTRA_ARGS+=("--limit" "$LIMIT")
fi
if [[ -n "$MAX_CONTEXT" ]]; then
    EXTRA_ARGS+=("--max-context" "$MAX_CONTEXT")
fi

echo "posttrainllm binary: $TINYGPT_BIN"
echo "model:          $MODEL_PATH"
echo "tasks:          $TASKS"
echo "output:         $OUT_DIR"
[[ -n "$LIMIT" ]] && echo "limit:          $LIMIT/task"
echo ""

# TODO: confirm lm-eval is installed. Skipping `pip install` per AGENTS.md
# (no unsupervised installs). If lm-eval isn't on PATH, the wrapper script
# will surface the error directly.
if ! command -v lm-eval >/dev/null 2>&1; then
    echo "warning: lm-eval not on PATH. Install with:" >&2
    echo "    pip install lm-eval==0.4.10" >&2
    echo "(continuing — wrapper script will fail with a clearer error)" >&2
fi

exec python "$REPO_ROOT/python_ref/lm_eval_tinygpt.py" \
    "$MODEL_PATH" \
    --tasks "$TASKS" \
    --output-path "$OUT_DIR" \
    --posttrainllm-bin "$TINYGPT_BIN" \
    "${EXTRA_ARGS[@]}"
