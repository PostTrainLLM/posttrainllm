#!/usr/bin/env bash
# Guards CLI discovery without building or loading a model. When
# POSTTRAINLLM_BIN points to a built executable, also exercises the runtime
# contract. The mac CI job supplies that path after `swift build`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$ROOT/scripts/docs-checks/check_cli_surface.py"

bin="${POSTTRAINLLM_BIN:-}"
if [ -z "$bin" ]; then
  for candidate in \
    "$ROOT/native-mac/.build/release/posttrainllm" \
    "$ROOT/native-mac/.build/debug/posttrainllm"; do
    if [ -x "$candidate" ]; then
      bin="$candidate"
      break
    fi
  done
fi

if [ -z "$bin" ]; then
  echo "CLI runtime checks skipped: no built binary (static contract passed)."
  exit 0
fi
[ -x "$bin" ] || { echo "CLI SURFACE FAIL: binary is not executable: $bin" >&2; exit 1; }

version="$($bin --version)"
[ "$version" = "posttrainllm 0.1.0" ] || {
  echo "CLI SURFACE FAIL: unexpected version output: $version" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

"$bin" commands --json > "$tmp/catalog.json"
python3 - "$tmp/catalog.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
assert payload["schema_version"] == 1
assert payload["cli_version"] == "0.1.0"
assert payload["lab_loop"] == ["target", "data", "post-training", "eval", "package", "report"]
commands = payload["commands"]
assert len(commands) >= 100
assert all(row["invocation"].startswith("posttrainllm ") for row in commands)
assert any(row["name"] == "factory-run" and row["status"] == "retained" for row in commands)
assert any(row["name"] == "experimental rome" and row["status"] == "experimental" for row in commands)
PY

"$bin" --help | grep -q "Retained lab loop"
"$bin" --help | grep -q "posttrainllm commands --json"
! "$bin" --help | grep -q "posttrainllm rome"
"$bin" | grep -q "Retained lab loop"
"$bin" help factory-run | grep -q "reproducible factory runs"
"$bin" experimental --help | grep -q "posttrainllm experimental"

set +e
"$bin" definitely-not-a-command > "$tmp/unknown.out" 2> "$tmp/unknown.err"
status=$?
set -e
[ "$status" -eq 2 ] || {
  echo "CLI SURFACE FAIL: unknown command exited $status, expected 2" >&2
  exit 1
}
grep -q "posttrainllm commands" "$tmp/unknown.err"

echo "CLI runtime OK: version, catalog JSON, help, namespace, and error contract"
