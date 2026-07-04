#!/usr/bin/env bash
# Smoke-check the structured attempt ledger.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/check_attempt_ledger.py"
echo "attempt-ledger-smoke ok"

