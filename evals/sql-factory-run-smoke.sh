#!/usr/bin/env bash
# No-MLX smoke for the current SQL routed report artifact run folder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/scripts/render_sql_factory_run.py" --out "$WORK/sql-run"

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

func assertTrue(_ condition: @autoclosure () -> Bool, _ msg: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(msg)\n", stderr)
        exit(1)
    }
}

let run = URL(fileURLWithPath: CommandLine.arguments[1])
let bundle = try FactoryRunFolder.validate(directory: run)
assertTrue(bundle.config.runId == "2026-07-02-sql-routed-qwen06-v1", "run id")
assertTrue(bundle.config.target == "sql-routed-specialist-poc", "target")
assertTrue(bundle.dataset.counts.trainRows == 5675, "train row count")
assertTrue(bundle.dataset.counts.heldoutRows == 114, "heldout row count")
assertTrue(bundle.baseline.score == 0.160, "baseline score")
assertTrue(bundle.candidate.score == 0.860, "candidate score")
assertTrue(bundle.decision.decision == .retryEval, "decision")
assertTrue(bundle.decision.blockedBy.contains("public execution DB bundle not local"), "blocker")

let report = try String(contentsOf: run.appendingPathComponent("report.md"), encoding: .utf8)
assertTrue(report.contains("Public b-mc2 exact, 64 rows"), "public metric")
assertTrue(report.contains("build_sql_spider_execution_gate.py"), "next gate")

print("SMOKE OK: SQL routed factory run artifact")
SWIFT

swiftc \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  "$WORK/main.swift" \
  -o "$WORK/sql-factory-run-smoke"

"$WORK/sql-factory-run-smoke" "$WORK/sql-run"
