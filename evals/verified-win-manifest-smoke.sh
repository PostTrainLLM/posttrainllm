#!/usr/bin/env bash
# No-model smoke for Issue #138's fail-closed experiment contracts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATOR="$ROOT/scripts/experiments/validate_verified_win_manifest.py"
MANIFESTS=("$ROOT"/evals/verified-wins/*.json)

python3 "$VALIDATOR" "${MANIFESTS[@]}" --stage design >/dev/null

if python3 "$VALIDATOR" "${MANIFESTS[@]}" --stage run >/dev/null 2>&1; then
  echo "FAIL: design-only manifests must not pass the run freeze" >&2
  exit 1
fi

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
