#!/usr/bin/env bash
# Smoke-check the golden-path docs surfaces.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/docs-checks/check_docs_world_class.py"
echo "docs-world-class-smoke ok"

