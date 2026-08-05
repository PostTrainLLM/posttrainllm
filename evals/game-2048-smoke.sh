#!/usr/bin/env bash
# Dependency-free CPU-only correctness and tiny-baseline qualification.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tests/test_game_2048.py"
python3 "$ROOT/scripts/game_2048.py" qualify \
  --environment-config "$ROOT/configs/game-2048/environment-v1.json" \
  --config "$ROOT/configs/game-2048/development-eval-v1.json" \
  --transition-fixtures "$ROOT/evals/game-2048/fixtures/board-transitions-v1.json" \
  --expected "$ROOT/evals/game-2048/fixtures/tiny-cohort-v1.json" \
  --output "$WORK/cohort.json"

echo "game-2048-smoke: all checks passed (no model, training, network, or sweep)"
