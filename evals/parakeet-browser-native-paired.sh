#!/usr/bin/env bash
# Run the frozen Parakeet browser-vs-native ASR comparison from Issue #138.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLUIDAUDIO_SOURCE="${FLUIDAUDIO_SOURCE:?set FLUIDAUDIO_SOURCE to the pinned fluidaudio-web checkout}"
WHISPERKIT_MODEL_PATH="${WHISPERKIT_MODEL_PATH:?set WHISPERKIT_MODEL_PATH to the pinned Core ML model directory}"
RUN_DIR="$ROOT/runs/verified-wins/parakeet-browser-native-paired-v1"
FIXTURE="$ROOT/evals/parakeet-wgsl/reference-fixture-v1.json"
AUDIO_DIR="$RUN_DIR/audio"
PORT="${PARAKEET_BENCH_PORT:-4174}"
SOURCE_REVISION="ab738c92b8a6af0dcdfe51dddd062427a5ec7689"
WEIGHTS_REVISION="6c6bcda07b23fd91778062b435b1a5f2f6d07504"
VOCAB_REVISION="f88260fa0777fe0868dda6df85d1a98f012a4a7a"
MODEL_REVISION="97a5bf9bbc74c7d9c12c755d04dea59e672e3808"
CONFIG_SHA256="f01d83dd891791d6f12421c05d3ed8ebbe70866f10d6c9a7a7e80b558ce5a0f1"
GENERATION_CONFIG_SHA256="7fbb053a023be11fbeccd8421811610308143daa93d9617c52aab4a0fa1491c6"

mkdir -p "$RUN_DIR"
if [[ -e "$RUN_DIR/browser-predictions.json" || -e "$RUN_DIR/native-report" ]]; then
  echo "parakeet-paired: output already exists; refusing to overwrite" >&2
  exit 1
fi

(
  cd "$FLUIDAUDIO_SOURCE"
  exec ./node_modules/.bin/vite --host 127.0.0.1 --port "$PORT" --strictPort
) >"$RUN_DIR/vite.log" 2>&1 &
SERVER_PID=$!
cleanup() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
for _ in {1..50}; do
  if curl -fsS "http://127.0.0.1:$PORT/" >/dev/null; then break; fi
  sleep 0.1
done
curl -fsS "http://127.0.0.1:$PORT/" >/dev/null

(
  cd "$ROOT/browser"
  node scripts/run-parakeet-asr.mjs \
    --base-url "http://127.0.0.1:$PORT/" \
    --fixture "$FIXTURE" \
    --audio-dir "$AUDIO_DIR" \
    --output "$RUN_DIR/browser-predictions.json" \
    --source-root "$FLUIDAUDIO_SOURCE" \
    --source-revision "$SOURCE_REVISION" \
    --weights-revision "$WEIGHTS_REVISION" \
    --vocab-revision "$VOCAB_REVISION"
)
cleanup
trap - EXIT

python3 "$ROOT/scripts/asr/run_whisperkit_native.py" \
  --fixture "$FIXTURE" \
  --audio-dir "$AUDIO_DIR" \
  --report-dir "$RUN_DIR/native-report" \
  --receipt "$RUN_DIR/native-raw.json" \
  --cli /opt/homebrew/bin/whisperkit-cli \
  --cli-version v1.1.0 \
  --model-path "$WHISPERKIT_MODEL_PATH" \
  --model-revision "$MODEL_REVISION" \
  --config-sha256 "$CONFIG_SHA256" \
  --generation-config-sha256 "$GENERATION_CONFIG_SHA256"

python3 "$ROOT/scripts/asr/adapt_whisperkit_reports.py" \
  --fixture "$FIXTURE" \
  --raw-receipt "$RUN_DIR/native-raw.json" \
  --report-dir "$RUN_DIR/native-report" \
  --output "$RUN_DIR/native-predictions.json"
python3 "$ROOT/scripts/asr/score_asr.py" \
  --fixture "$FIXTURE" \
  --prediction "$RUN_DIR/native-predictions.json" \
  --output "$RUN_DIR/native-score.json"
python3 "$ROOT/scripts/asr/score_asr.py" \
  --fixture "$FIXTURE" \
  --prediction "$RUN_DIR/browser-predictions.json" \
  --output "$RUN_DIR/browser-score.json"
python3 "$ROOT/scripts/asr/compare_asr.py" \
  --native-score "$RUN_DIR/native-score.json" \
  --browser-score "$RUN_DIR/browser-score.json" \
  --browser-raw "$RUN_DIR/browser-predictions.json" \
  --output "$RUN_DIR/comparison.json"
