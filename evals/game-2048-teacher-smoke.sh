#!/usr/bin/env bash
# Bounded CPU-only expectimax correctness and four-development-seed calibration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/tests/test_game_2048_teacher.py"
python3 "$ROOT/scripts/games/game_2048.py" calibrate-teacher \
  --environment-config "$ROOT/configs/game-2048/environment-v1.json" \
  --config "$ROOT/configs/game-2048/development-eval-v1.json" \
  --teacher-config "$ROOT/configs/game-2048/teacher-calibration-v1.json" \
  --expected-report "$ROOT/evals/game-2048/teacher-calibration-v1.json" \
  --output "$WORK/cohort.json"

echo "game-2048-teacher-smoke: bounded development calibration passed"
