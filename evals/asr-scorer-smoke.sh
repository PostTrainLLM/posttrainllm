#!/usr/bin/env bash
# Dependency-free ASR scorer and frozen-fixture checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 -m unittest discover -s "$ROOT/scripts/asr" -p 'test_*.py'
python3 -m py_compile "$ROOT/scripts/asr/"*.py

echo "asr-scorer-smoke ok"
