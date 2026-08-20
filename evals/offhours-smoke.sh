#!/usr/bin/env bash
# Stdlib-only OffHours contract, scheduling, persistence, resume, and analysis smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/scripts/offhours.py" validate
python3 "$ROOT/scripts/offhours.py" plan --days 2 --tasks-per-day 8 --seed 42 >/dev/null
python3 "$ROOT/tests/test_offhours.py"
python3 "$ROOT/scripts/render_offhours_fixture_report.py" --check

echo "offhours-smoke: all checks passed"
