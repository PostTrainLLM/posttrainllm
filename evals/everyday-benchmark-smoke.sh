#!/usr/bin/env bash
# Stdlib-only benchmark contract, scorer, routing, resource, and privacy smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/scripts/check_everyday_benchmark.py" \
  "$ROOT/configs/everyday-benchmark/suite-v1.json" \
  "$ROOT/configs/everyday-benchmark/tasks/pace-intent-routing-v1.json" \
  "$ROOT/evals/everyday-benchmark/fixtures/pace-intent-public-dev-v1.json" \
  "$ROOT/evals/everyday-benchmark/fixtures/entries/generalist-fixture-v1.json" \
  "$ROOT/evals/everyday-benchmark/fixtures/entries/adapted-fixture-v1.json" \
  "$ROOT/evals/everyday-benchmark/fixtures/entries/system-fixture-v1.json" \
  "$ROOT/configs/everyday-benchmark/entries/pace-intent-v8-qwen-cascade-v1.json"

python3 "$ROOT/tests/test_everyday_benchmark.py"
python3 "$ROOT/tests/test_selective_cascade.py"

echo "everyday-benchmark-smoke: all checks passed"
