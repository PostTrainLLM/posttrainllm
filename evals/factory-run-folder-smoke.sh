#!/usr/bin/env bash
# No-MLX smoke for the canonical factory run folder API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

func assertTrue(_ condition: @autoclosure () -> Bool, _ msg: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(msg)\n", stderr)
        exit(1)
    }
}

let out = URL(fileURLWithPath: CommandLine.arguments[1])
let bundle = FactoryRun.Bundle(
    config: FactoryRun.Config(
        runId: "2026-07-02-smoke-sft-v1",
        target: "smoke-target",
        ownerGoal: "Prove the factory run folder can be emitted without compute.",
        baseModel: .init(id: "fixture-base", revision: "abc123", precision: "bf16"),
        candidate: .init(method: "sft-lora", adapterFormat: "tgla",
                         trainingCommand: "tinygpt sft fixture-base --data data.jsonl"),
        eval: .init(primary: "fixture-gate", regression: "fixture-regression",
                    threshold: .init(primaryMin: 0.9, breadthDropMaxPp: 3))
    ),
    dataset: FactoryRun.DatasetManifest(
        datasetId: "smoke-dataset",
        sources: [.init(kind: "fixture", path: "evals/smoke.jsonl", rows: 12)],
        processing: .init(dedupe: true, qualityFilter: true, heldoutSplit: "locked"),
        counts: .init(trainRows: 10, heldoutRows: 2, droppedRows: 1)
    ),
    baseline: FactoryRun.EvalResult(modelId: "base", command: "tinygpt eval-gate base",
                                    suite: "fixture-gate", score: 0.70,
                                    passed: false, date: "2026-07-02"),
    candidate: FactoryRun.EvalResult(modelId: "candidate",
                                     command: "tinygpt eval-gate candidate",
                                     suite: "fixture-gate", score: 0.93,
                                     passed: true, date: "2026-07-02",
                                     latencyMs: 42, peakRssMb: 128,
                                     tokensPerSecond: 77),
    artifact: FactoryRun.Artifact(artifactId: "smoke-adapter",
                                  kind: "adapter",
                                  path: "specialists/smoke-adapter",
                                  baseModel: "fixture-base",
                                  format: "tgla",
                                  packageDir: "specialists/smoke-adapter",
                                  shipped: true),
    decision: FactoryRun.DecisionRecord(decision: .ship,
                                        reason: "Fixture cleared the threshold.",
                                        nextAction: "Register fixture package.")
)

try FactoryRunFolder.write(bundle, to: out, trainLog: "fixture train log\n")
let validated = try FactoryRunFolder.validate(directory: out)
assertTrue(validated == bundle, "folder read/validate roundtrip")

let expectedFiles = [
    FactoryRunFolder.configFile,
    FactoryRunFolder.datasetFile,
    FactoryRunFolder.baselineFile,
    FactoryRunFolder.candidateFile,
    FactoryRunFolder.artifactFile,
    FactoryRunFolder.decisionFile,
    FactoryRunFolder.reportFile,
    FactoryRunFolder.trainLogFile,
]
for file in expectedFiles {
    assertTrue(FileManager.default.fileExists(atPath: out.appendingPathComponent(file).path),
               "missing \(file)")
}
let report = try String(contentsOf: out.appendingPathComponent(FactoryRunFolder.reportFile),
                        encoding: .utf8)
assertTrue(report.contains("Decision: ship"), "report decision")
assertTrue(report.contains("| fixture-gate | 0.7000 | 0.9300 | 0.2300 | yes |"),
           "report before/after row")
let configJSON = try String(contentsOf: out.appendingPathComponent(FactoryRunFolder.configFile),
                            encoding: .utf8)
assertTrue(configJSON.contains("\"run_id\""), "snake_case config JSON")

print("SMOKE OK: factory run folder write/read/report")
SWIFT

swiftc \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  "$WORK/main.swift" \
  -o "$WORK/factory-run-folder-smoke"

"$WORK/factory-run-folder-smoke" "$WORK/run"
