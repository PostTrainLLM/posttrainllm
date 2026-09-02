#!/usr/bin/env bash
# No-model smoke for Issue #138's fail-closed experiment contracts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$ROOT/scripts/experiments/validate_verified_win_manifest.py"
MANIFESTS=(
  "$ROOT/evals/verified-wins/webgpu-v1.json"
  "$ROOT/evals/verified-wins/parakeet-asr-v1.json"
  "$ROOT/evals/verified-wins/rest-requalification-v1.json"
  "$ROOT/evals/verified-wins/needle-successor-v1.json"
)

python3 "$VALIDATOR" "${MANIFESTS[@]}" --stage design >/dev/null
python3 "$VALIDATOR" "${MANIFESTS[@]}" --stage run >/dev/null

BROKEN="$(mktemp)"
trap 'rm -f "$BROKEN"' EXIT
python3 - "$ROOT/evals/verified-wins/needle-successor-v1.json" "$BROKEN" <<'PY'
import json
import sys

source, target = sys.argv[1:]
data = json.load(open(source, encoding="utf-8"))
data["arms"].pop()
with open(target, "w", encoding="utf-8") as handle:
    json.dump(data, handle)
PY

if python3 "$VALIDATOR" "$BROKEN" --stage design >/dev/null 2>&1; then
  echo "FAIL: incomplete Needle factorial must not validate" >&2
  exit 1
fi

echo "verified-win-manifest-smoke ok"
