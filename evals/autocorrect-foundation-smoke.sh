#!/usr/bin/env bash
# No-model smoke for the Mac-local autocorrect foundation.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/tests/test_autocorrect_foundation.py"
python3 "$ROOT/scripts/research/autocorrect_foundation.py" validate
python3 "$ROOT/scripts/research/autocorrect_foundation.py" evaluate \
  --predictions "$ROOT/evals/autocorrect/oracle-predictions-v1.jsonl" >/dev/null

echo "autocorrect-foundation-smoke: all checks passed"
