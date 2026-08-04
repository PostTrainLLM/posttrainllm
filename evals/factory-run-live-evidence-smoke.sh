#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

@main
struct Smoke {
    static func main() throws {
        let run = URL(fileURLWithPath: CommandLine.arguments[1])
        try FileManager.default.createDirectory(at: run, withIntermediateDirectories: true)
        try FactoryRunFolder.writeJSON(
            FactoryRun.Config(
                runId: "live-evidence-smoke",
                target: "fixture",
                ownerGoal: "Exercise command evidence without loading a model.",
                baseModel: .init(id: "fixture-base"),
                candidate: .init(method: "sft-lora"),
                eval: .init(primary: "fixture-gate")
            ),
            to: run.appendingPathComponent(FactoryRunFolder.configFile)
        )
        try FactoryRunFolder.writeJSON(
            FactoryRun.DatasetManifest(
                datasetId: "fixture-data",
                sources: [.init(kind: "fixture", path: "fixture.jsonl", rows: 2)],
                counts: .init(trainRows: 1, heldoutRows: 1)
            ),
            to: run.appendingPathComponent(FactoryRunFolder.datasetFile)
        )
        var status = try FactoryRunLifecycle.initialize(directory: run)
        status = try FactoryRunLifecycle.transition(
            directory: run, to: .dataReady, expectedRevision: status.revision,
            source: "smoke", command: "prepare"
        )
        status = try FactoryRunEvidence.beginTraining(directory: run)
        status = try FactoryRunEvidence.finishTraining(
            directory: run,
            artifact: .init(artifactId: "fixture-adapter", kind: "adapter",
                            path: "fixture.lora", baseModel: "fixture-base"),
            summary: "Fixture SFT evidence completed without model execution.",
            trainingTimeSeconds: 0
        )
        status = try FactoryRunEvidence.beginEvaluation(directory: run)
        status = try FactoryRunEvidence.finishEvaluation(
            directory: run,
            baseline: .init(modelId: "fixture-base", suite: "fixture-gate", score: 0.5),
            candidate: .init(modelId: "fixture-adapter", suite: "fixture-gate",
                             score: 0.75, passed: true),
            evalTimeSeconds: 0
        )
        let slices = try FactoryRunEvidence.makeSliceMetrics([
            .init(name: "fixture_gate_accuracy", metric: "accuracy", score: 0.5,
                  rows: 1, baseline: true, higherIsBetter: true),
            .init(name: "fixture_gate_accuracy", metric: "accuracy", score: 0.75,
                  rows: 1, baseline: false, higherIsBetter: true),
        ])
        try FactoryRunEvidence.writeSliceMetrics(slices, directory: run)
        guard status.phase == .evaluated else { throw SmokeError.wrongPhase }
        print("factory-run-live-evidence Swift smoke ok")
    }

    enum SmokeError: Error { case wrongPhase }
}
SWIFT

swiftc \
  -parse-as-library \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunEvidence.swift" \
  "$WORK/main.swift" \
  -o "$WORK/factory-run-live-evidence-smoke"

"$WORK/factory-run-live-evidence-smoke" "$WORK/runs/live-evidence-smoke"

python3 - "$WORK/runs/live-evidence-smoke" "$ROOT" <<'PY'
import json
import pathlib
import sys

run = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
status = json.loads((run / "run-status.json").read_text())
assert status["phase"] == "evaluated", status
for name in (
    "artifact.json", "train.log", "cost.json", "eval-baseline.json",
    "eval-candidate.json", "slice-metrics.json",
):
    assert (run / name).is_file(), name
assert not (run / "decision.json").exists()

sources = {
    "sft": (root / "native-mac/Sources/TinyGPT/SFT.swift").read_text(),
    "gate": (root / "native-mac/Sources/TinyGPT/EvalGate.swift").read_text(),
    "compare": (root / "native-mac/Sources/TinyGPT/EvalCompare.swift").read_text(),
}
for name, source in sources.items():
    assert '"--factory-run"' in source, name
print("factory-run-live-evidence source boundary smoke ok")
PY

echo "factory-run-live-evidence-smoke ok"
