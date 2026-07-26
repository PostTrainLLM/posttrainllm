#!/usr/bin/env bash
# Smoke-check the structured attempt ledger.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/check_attempt_ledger.py"
python3 "$ROOT/tests/test_query_attempts.py"

echo "attempt-ledger-smoke ok"
