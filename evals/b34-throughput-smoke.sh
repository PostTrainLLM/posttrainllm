#!/usr/bin/env bash
# B34 no-model smoke: local threaded OpenAI-compatible mock endpoint,
# sequential vs bounded-concurrent request submission.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/tests/b34_throughput_smoke.py" "$@"
