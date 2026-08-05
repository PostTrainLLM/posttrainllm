#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3.12 tests/test_chess_benchmark.py
openspec validate add-chess-specialist-benchmark --strict
openspec validate freeze-chess-benchmark-candidate-suite --strict
openspec validate build-50m-character-chess-specialist --strict
