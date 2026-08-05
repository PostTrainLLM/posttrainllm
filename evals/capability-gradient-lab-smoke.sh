#!/usr/bin/env bash
# Stdlib-only capability-gradient benchmark candidate lab smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Validate the candidate scorecard
python3 "$ROOT/scripts/capability_gradient_lab.py" validate-scorecard

# Validate all development probes (mechanically verified)
python3 "$ROOT/scripts/capability_gradient_lab.py" validate-probes

# Recompute the full deterministic development baselines so prose cannot drift
python3 "$ROOT/scripts/capability_gradient_lab.py" validate-baseline-claims

# Run canonical traces to confirm determinism
python3 "$ROOT/scripts/capability_gradient_lab.py" canonical-trace --env connect4 --seed 42 >/dev/null
python3 "$ROOT/scripts/capability_gradient_lab.py" canonical-trace --env calendar --seed 42 >/dev/null

# Run random-legal baselines to confirm the baseline executor works
python3 "$ROOT/scripts/capability_gradient_lab.py" random-baseline --env connect4 --seeds 0-19 >/dev/null
python3 "$ROOT/scripts/capability_gradient_lab.py" random-baseline --env calendar --seeds 0-19 >/dev/null

# Run the focused test suite
python3 "$ROOT/tests/test_capability_gradient_lab.py"

echo "capability-gradient-lab-smoke: all checks passed"
