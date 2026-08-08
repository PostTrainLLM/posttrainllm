#!/usr/bin/env bash
# Dependency-free graph, routing, cascade, privacy, and adapter smoke. No model or network use.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES="$ROOT/evals/capability-graph/fixtures"

python3 "$ROOT/scripts/capability_graph.py" validate
python3 "$ROOT/scripts/capability_graph.py" inspect --capability file-ops >/dev/null
python3 "$ROOT/scripts/capability_graph.py" dry-run \
  --request "$FIXTURES/request-file-ops-v1.json" \
  --installed "$FIXTURES/installed-v1.json" \
  --router-output "$FIXTURES/router-file-ops-v1.json" >/dev/null
python3 "$ROOT/scripts/capability_graph.py" cascade \
  --request "$FIXTURES/request-file-ops-v1.json" \
  --installed "$FIXTURES/installed-v1.json" \
  --router-output "$FIXTURES/router-file-ops-v1.json" \
  --outcomes "$FIXTURES/outcomes-accept-v1.json" >/dev/null
python3 -m unittest tests.test_capability_graph
openspec validate specialist-capability-graph --type spec --strict

echo "capability-graph-smoke: all checks passed"
