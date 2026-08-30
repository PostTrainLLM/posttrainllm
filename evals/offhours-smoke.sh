#!/usr/bin/env bash
# Stdlib-only OffHours contract, scheduling, persistence, resume, and analysis smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/scripts/offhours/offhours.py" validate
python3 "$ROOT/scripts/offhours/offhours.py" \
  --config "$ROOT/configs/offhours/tension-v1.json" validate
python3 "$ROOT/scripts/offhours/offhours.py" \
  --config "$ROOT/configs/offhours/tension-v2.json" validate
python3 "$ROOT/scripts/offhours/offhours.py" \
  --config "$ROOT/configs/offhours/occupancy-v1.json" validate
python3 "$ROOT/scripts/offhours/offhours.py" \
  --config "$ROOT/configs/offhours/volume-v1.json" validate
python3 "$ROOT/scripts/offhours/generate_offhours_pilot_v2.py" --check
python3 "$ROOT/scripts/offhours/generate_offhours_pilot_v3.py" --check
python3 "$ROOT/scripts/offhours/package_offhours_saturation.py" --check
python3 "$ROOT/scripts/offhours/offhours.py" plan --days 2 --tasks-per-day 8 --seed 42 >/dev/null
python3 "$ROOT/tests/test_offhours.py"
python3 "$ROOT/scripts/offhours/render_offhours_fixture_report.py" --check

echo "offhours-smoke: all checks passed"
