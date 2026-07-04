#!/usr/bin/env bash
# Smoke-check the ground-up owner learning roadmap.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/check_learning_roadmap.py"
echo "learning-roadmap-smoke ok"
