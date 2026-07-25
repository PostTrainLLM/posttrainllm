#!/usr/bin/env bash
# No-GPU smoke for durable factory-run lifecycle metadata.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

RUNS="$WORK/runs"
RUN="$RUNS/smoke-run"
mkdir -p "$RUN"

python3 - "$RUN/config.json" <<'PY'
import json, sys
json.dump({
    "run_id": "smoke-run",
    "target": "lifecycle-smoke",
    "owner_goal": "Exercise lifecycle metadata without model work.",
    "base_model": {"id": "fixture-base"},
    "candidate": {"method": "metadata-only"},
    "eval": {"primary": "fixture-gate"},
}, open(sys.argv[1], "w"), indent=2)
PY

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(message)\n", stderr)
        exit(1)
    }
}

let root = URL(fileURLWithPath: CommandLine.arguments[1])
let run = root.appendingPathComponent("smoke-run")
let start = ISO8601DateFormatter().date(from: "2026-07-25T00:00:00Z")!

let created = try FactoryRunLifecycle.initialize(
    directory: run,
    source: "smoke",
    command: "factory-run init",
    now: start
)
require(created.phase == .created && created.revision == 1, "init status")

let ready = try FactoryRunLifecycle.transition(
    directory: run,
    to: .dataReady,
    expectedRevision: created.revision,
    source: "smoke",
    command: "factory-run transition",
    now: start.addingTimeInterval(1)
)
require(ready.phase == .dataReady && ready.revision == 2, "transition status")

do {
    _ = try FactoryRunLifecycle.transition(
        directory: run,
        to: .training,
        expectedRevision: 1
    )
    require(false, "stale writer was accepted")
} catch FactoryRunLifecycle.LifecycleError.staleRevision {
    // expected
}

let listed = try FactoryRunLifecycle.list(root: root)
require(listed.count == 1 && listed[0].status.runId == "smoke-run", "list")
try FactoryRun.encode(listed).write(to: root.appendingPathComponent("list.json"))

try Data("partial".utf8).write(
    to: run.appendingPathComponent(".run-status.interrupted.tmp")
)
let badPointer: [String: Any] = [
    "schema_version": 1,
    "relative_run_path": "../escape",
    "run_id": "escape",
    "lifecycle_revision": 1,
    "phase": "created",
    "updated_at": "2026-07-25T00:00:00Z",
]
try JSONSerialization.data(withJSONObject: badPointer).write(
    to: root.appendingPathComponent(FactoryRunLifecycle.currentPointerFile)
)

let preview = try FactoryRunLifecycle.reconcile(root: root)
require(preview.dryRun, "reconcile defaults to dry-run")
require(preview.diagnostics.contains { $0.kind == "invalid-pointer" }, "pointer diagnostic")
require(preview.diagnostics.contains { $0.kind == "abandoned-temporary" }, "temporary diagnostic")
try FactoryRun.encode(preview).write(to: root.appendingPathComponent("reconcile-dry.json"))

let repaired = try FactoryRunLifecycle.reconcile(root: root, write: true)
require(!repaired.dryRun && !repaired.repairs.isEmpty, "write reconciliation")
require(
    !FileManager.default.fileExists(
        atPath: run.appendingPathComponent(".run-status.interrupted.tmp").path
    ),
    "temporary cleanup"
)
try FactoryRun.encode(repaired).write(to: root.appendingPathComponent("reconcile-write.json"))
print("factory-run-lifecycle Swift smoke ok")
SWIFT

CLANG_MODULE_CACHE_PATH="$WORK/clang-module-cache" swiftc \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  "$WORK/main.swift" \
  -o "$WORK/factory-run-lifecycle-smoke"

"$WORK/factory-run-lifecycle-smoke" "$RUNS"

python3 - "$RUNS" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
status = json.load(open(root / "smoke-run/run-status.json"))
listed = json.load(open(root / "list.json"))
dry = json.load(open(root / "reconcile-dry.json"))
written = json.load(open(root / "reconcile-write.json"))
assert status["phase"] == "data-ready" and status["revision"] == 2
assert listed[0]["status"]["run_id"] == "smoke-run"
assert dry["dry_run"] is True and written["dry_run"] is False
assert json.load(open(root / "current-run.json"))["run_id"] == "smoke-run"
print("factory-run-lifecycle JSON smoke ok")
PY

# Compile the real factory-run command against only TinyGPTIO, then exercise
# its init/status/transition/list/reconcile JSON surfaces.
CLANG_MODULE_CACHE_PATH="$WORK/clang-module-cache" swiftc \
  -emit-library -emit-module -module-name TinyGPTIO \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  -emit-module-path "$WORK/TinyGPTIO.swiftmodule" \
  -o "$WORK/libTinyGPTIO.dylib"

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation
import TinyGPTIO

FactoryRunCommand.run(args: Array(CommandLine.arguments.dropFirst()))
SWIFT

CLANG_MODULE_CACHE_PATH="$WORK/clang-module-cache" swiftc \
  -I "$WORK" -L "$WORK" -lTinyGPTIO \
  "$ROOT/native-mac/Sources/TinyGPT/FactoryRunCommand.swift" \
  "$WORK/main.swift" \
  -o "$WORK/factory-run-cli"

CLI_RUN="$RUNS/cli-run"
mkdir -p "$CLI_RUN"
python3 - "$CLI_RUN/config.json" <<'PY'
import json, sys
json.dump({
    "run_id": "cli-run",
    "target": "lifecycle-cli-smoke",
    "owner_goal": "Exercise the real metadata-only CLI parser.",
    "base_model": {"id": "fixture-base"},
    "candidate": {"method": "metadata-only"},
    "eval": {"primary": "fixture-gate"},
}, open(sys.argv[1], "w"), indent=2)
PY

DYLD_LIBRARY_PATH="$WORK" "$WORK/factory-run-cli" init --json "$CLI_RUN" \
  >"$WORK/cli-init.json"
DYLD_LIBRARY_PATH="$WORK" "$WORK/factory-run-cli" status --json "$CLI_RUN" \
  >"$WORK/cli-status.json"
DYLD_LIBRARY_PATH="$WORK" "$WORK/factory-run-cli" transition \
  --phase data-ready --expected-revision 1 --json "$CLI_RUN" \
  >"$WORK/cli-transition.json"
DYLD_LIBRARY_PATH="$WORK" "$WORK/factory-run-cli" list --active --json "$RUNS" \
  >"$WORK/cli-list.json"
DYLD_LIBRARY_PATH="$WORK" "$WORK/factory-run-cli" reconcile --json "$RUNS" \
  >"$WORK/cli-reconcile.json"

python3 - "$WORK" <<'PY'
import json, pathlib, sys
work = pathlib.Path(sys.argv[1])
assert json.load(open(work / "cli-init.json"))["phase"] == "created"
assert json.load(open(work / "cli-status.json"))["revision"] == 1
transition = json.load(open(work / "cli-transition.json"))
assert transition["phase"] == "data-ready" and transition["revision"] == 2
assert {item["status"]["run_id"] for item in json.load(open(work / "cli-list.json"))} == {
    "smoke-run", "cli-run",
}
assert json.load(open(work / "cli-reconcile.json"))["dry_run"] is True
print("factory-run lifecycle CLI JSON smoke ok")
PY

python3 - "$ROOT/native-mac/Sources/TinyGPT/FactoryRunCommand.swift" <<'PY'
import pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text()
assert text.startswith("import Foundation\nimport TinyGPTIO\n")
for forbidden in ("import TinyGPTModel", "import MLX", "URLSession", "Serve.start(", "Train.run("):
    assert forbidden not in text, forbidden
print("factory-run lifecycle command remains metadata-only")
PY

echo "factory-run-lifecycle-smoke ok"
