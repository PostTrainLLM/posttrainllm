import Foundation
import XCTest
@testable import TinyGPTIO

final class FactoryRunEvidenceTests: XCTestCase {
    private func makeRun() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("factory-run-evidence-tests")
            .appendingPathComponent(UUID().uuidString)
        let run = root.appendingPathComponent("fixture-live-run")
        try FileManager.default.createDirectory(at: run, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }

        try FactoryRunFolder.writeJSON(
            FactoryRun.Config(
                runId: "fixture-live-run",
                target: "fixture-target",
                ownerGoal: "Prove live evidence persistence without a model.",
                baseModel: .init(id: "fixture-base"),
                candidate: .init(method: "sft-lora"),
                eval: .init(primary: "fixture-gate")
            ),
            to: run.appendingPathComponent(FactoryRunFolder.configFile)
        )
        try FactoryRunFolder.writeJSON(
            FactoryRun.DatasetManifest(
                datasetId: "fixture-data",
                sources: [.init(kind: "fixture", path: "evals/fixture.jsonl", rows: 10)],
                counts: .init(trainRows: 8, heldoutRows: 2)
            ),
            to: run.appendingPathComponent(FactoryRunFolder.datasetFile)
        )
        var status = try FactoryRunLifecycle.initialize(directory: run)
        status = try FactoryRunLifecycle.transition(
            directory: run,
            to: .dataReady,
            expectedRevision: status.revision,
            source: "test",
            command: "prepare fixture"
        )
        XCTAssertEqual(status.phase, .dataReady)
        return run
    }

    func testTrainingAndEvaluationEvidenceAdvanceOnlyAfterWrites() throws {
        let run = try makeRun()
        XCTAssertEqual(try FactoryRunEvidence.beginTraining(directory: run).phase, .training)

        let artifact = FactoryRun.Artifact(
            artifactId: "fixture-adapter",
            kind: "adapter",
            path: "runs/fixture-adapter.lora",
            baseModel: "fixture-base",
            format: "lora",
            shipped: false
        )
        let trained = try FactoryRunEvidence.finishTraining(
            directory: run,
            artifact: artifact,
            summary: "SFT completed 2/2 steps in 0.250s with final loss 0.125; adapter saved.",
            trainingTimeSeconds: 0.25
        )
        XCTAssertEqual(trained.phase, .trained)
        XCTAssertTrue(FileManager.default.fileExists(
            atPath: run.appendingPathComponent(FactoryRunFolder.artifactFile).path
        ))
        XCTAssertTrue(FileManager.default.fileExists(
            atPath: run.appendingPathComponent(FactoryRunEvidence.costFile).path
        ))

        XCTAssertEqual(try FactoryRunEvidence.beginEvaluation(directory: run).phase, .evaluating)
        let evaluated = try FactoryRunEvidence.finishEvaluation(
            directory: run,
            baseline: .init(modelId: "fixture-base", suite: "fixture-gate", score: 0.5),
            candidate: .init(modelId: "fixture-adapter", suite: "fixture-gate",
                             score: 0.75, passed: true),
            evalTimeSeconds: 0.5
        )
        XCTAssertEqual(evaluated.phase, .evaluated)
        XCTAssertNoThrow(try FactoryRun.validate(
            FactoryRunFolder.readJSON(
                FactoryRun.EvalResult.self,
                from: run.appendingPathComponent(FactoryRunFolder.candidateFile)
            )
        ))
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: run.appendingPathComponent(FactoryRunFolder.decisionFile).path
        ))
    }

    func testInvalidEvidenceDoesNotAdvanceTraining() throws {
        let run = try makeRun()
        _ = try FactoryRunEvidence.beginTraining(directory: run)
        XCTAssertThrowsError(try FactoryRunEvidence.finishTraining(
            directory: run,
            artifact: .init(artifactId: "", kind: "adapter", path: "x",
                            baseModel: "fixture-base"),
            summary: "invalid artifact",
            trainingTimeSeconds: 1
        ))
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).phase, .training)
    }

    func testRepeatedBoundaryCallCannotSkipPhase() throws {
        let run = try makeRun()
        _ = try FactoryRunEvidence.beginTraining(directory: run)
        XCTAssertThrowsError(try FactoryRunEvidence.beginTraining(directory: run)) { error in
            XCTAssertEqual(
                error as? FactoryRunEvidence.EvidenceError,
                .invalidPhase(expected: .dataReady, actual: .training)
            )
        }
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run).revision, 3)
    }

    func testSliceMetricsRequireSameInstanceCountsAndPreserveLifecycle() throws {
        let run = try makeRun()
        _ = try FactoryRunEvidence.beginTraining(directory: run)
        let artifact = FactoryRun.Artifact(
            artifactId: "fixture-adapter",
            kind: "adapter",
            path: "fixture.lora",
            baseModel: "fixture-base"
        )
        _ = try FactoryRunEvidence.finishTraining(
            directory: run,
            artifact: artifact,
            summary: "Fixture training completed without model execution.",
            trainingTimeSeconds: 0
        )
        let before = try FactoryRunLifecycle.readStatus(directory: run)
        let metrics = try FactoryRunEvidence.makeSliceMetrics([
            .init(name: "fixture_gate_accuracy", metric: "accuracy", score: 0.5,
                  rows: 20, baseline: true, higherIsBetter: true),
            .init(name: "fixture_gate_accuracy", metric: "accuracy", score: 0.7,
                  rows: 20, baseline: false, higherIsBetter: true),
        ])
        try FactoryRunEvidence.writeSliceMetrics(metrics, directory: run)
        XCTAssertEqual(
            try XCTUnwrap(metrics.slices["fixture_gate_accuracy"]?.delta),
            0.2,
            accuracy: 0.000_001
        )
        XCTAssertEqual(try FactoryRunLifecycle.readStatus(directory: run), before)

        XCTAssertThrowsError(try FactoryRunEvidence.makeSliceMetrics([
            .init(name: "mismatch", metric: "accuracy", score: 0.5,
                  rows: 20, baseline: true, higherIsBetter: true),
            .init(name: "mismatch", metric: "accuracy", score: 0.6,
                  rows: 19, baseline: false, higherIsBetter: true),
        ]))
    }
}
