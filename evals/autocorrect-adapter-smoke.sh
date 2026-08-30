#!/usr/bin/env bash
# Offline smoke for the autocorrect encoder-decoder LoRA adapter path.
#
# Runs no training and loads no checkpoint. The torch-backed tests build a tiny
# randomly-initialized T5 and skip cleanly when torch is unavailable, so this is
# safe on CI where torch is deliberately not installed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The frozen recipe must still agree with the thresholds, the manifests, and the
# measured base-selection record.
python3 "$ROOT/scripts/research/autocorrect_adapter.py" validate

# Both stage plans must resolve without executing anything.
python3 "$ROOT/scripts/research/autocorrect_adapter.py" plan --stage tiny_overfit >/dev/null
python3 "$ROOT/scripts/research/autocorrect_adapter.py" plan --stage pilot >/dev/null

# Training must stay refused without operator approval...
if python3 "$ROOT/scripts/research/autocorrect_adapter.py" train --stage tiny_overfit >/dev/null 2>&1; then
  echo "autocorrect-adapter-smoke: FAIL train must refuse without operator approval" >&2
  exit 1
fi

# ...and must still refuse WITH approval while the recipe is retired. Approval
# is not a licence to train under a recipe that reached its stop rule.
if python3 "$ROOT/scripts/research/autocorrect_adapter.py" train --stage pilot \
     --i-have-operator-approval >/dev/null 2>&1; then
  echo "autocorrect-adapter-smoke: FAIL train must refuse under a retired recipe" >&2
  exit 1
fi

python3 "$ROOT/tests/test_autocorrect_adapter.py"

echo "autocorrect-adapter-smoke: all checks passed"
