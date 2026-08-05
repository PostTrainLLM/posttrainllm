#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3.12 tests/test_game_arena.py
python3.12 scripts/game_arena.py \
  --config configs/game-arena/candidate-v1.json \
  --root "$ROOT" \
  --check evals/game-arena/candidate-v1.json
python3.12 -m json.tool configs/game-arena/candidate-v1.json >/dev/null
python3.12 -m json.tool evals/game-arena/candidate-v1.json >/dev/null
python3.12 -m json.tool browser/src/data/benchmarks/game-arena-candidate-v1.json >/dev/null
cmp evals/game-arena/candidate-v1.json browser/src/data/benchmarks/game-arena-candidate-v1.json
if command -v openspec >/dev/null 2>&1; then
  openspec validate add-extensible-game-arena --strict
else
  echo "openspec not installed; skipping authoring-only spec validation"
fi
