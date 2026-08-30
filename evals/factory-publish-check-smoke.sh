#!/usr/bin/env bash
# No-MLX smoke for the stricter factory publish evidence check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/scripts/sql/render_sql_factory_run.py" --out "$WORK/sql-run"
python3 "$ROOT/scripts/factory/check_factory_run_publish.py" "$WORK/sql-run" --allow-report-only

echo "factory-publish-check-smoke ok"

