import Foundation
import XCTest
@testable import TinyGPTIO

final class FactoryRunTests: XCTestCase {

    private func sampleBundle(decision: FactoryRun.Decision = .ship,
                              shipped: Bool = true,
                              artifact: FactoryRun.Artifact? = nil) -> FactoryRun.Bundle {
        let config = FactoryRun.Config(
            runId: "2026-07-02-pace-planner-sft-v1",
            target: "pace-planner",
            ownerGoal: "Improve action grounding without breadth regression.",
            baseModel: .init(id: "Qwen/Qwen3-4B-Instruct-2507",
                             revision: "abc123",
                             precision: "bf16"),
            candidate: .init(method: "sft-lora",
                             adapterFormat: "tgla",
                             trainingCommand: "posttrainllm sft ..."),
            eval: .init(primary: "pace-v11-ship-gate",
                        regression: "bfcl-heldout-breadth",
                        threshold: .init(primaryMin: 0.95, breadthDropMaxPp: 3)))
        let dataset = FactoryRun.DatasetManifest(
            datasetId: "pace-planner-v11-sft",
            sources: [.init(kind: "trace", path: "evals/pace.jsonl", rows: 709)],
            processing: .init(dedupe: true, qualityFilter: true, heldoutSplit: "locked"),
            counts: .init(trainRows: 600, heldoutRows: 109, droppedRows: 12))
        let baseline = FactoryRun.EvalResult(
            modelId: "base",
            command: "posttrainllm eval-gate --candidate base.jsonl",
            suite: "pace-v11-ship-gate",
            score: 0.75,
            passed: false,
            latencyMs: 100,
            peakRssMb: 7000,
            tokensPerSecond: 35)
        let candidate = FactoryRun.EvalResult(
            modelId: "candidate",
            command: "posttrainllm eval-gate --candidate cand.jsonl",
            suite: "pace-v11-ship-gate",
            score: 0.96,
            passed: true,
            latencyMs: 112,
            peakRssMb: 7200,
            tokensPerSecond: 33)
        let defaultArtifact = FactoryRun.Artifact(
            artifactId: "pace-planner-sft-v1",
            kind: "adapter",
            path: "~/.cache/posttrainllm/models/pace-planner-sft-v1",
            baseModel: "Qwen/Qwen3-4B-Instruct-2507",
            format: "tgla",
            packageDir: "specialists/pace-planner-sft-v1",
            shipped: shipped)
        return FactoryRun.Bundle(
            config: config,
            dataset: dataset,
            baseline: baseline,
            candidate: candidate,
            artifact: artifact ?? defaultArtifact,
            decision: .init(decision: decision,
                            reason: "Primary score cleared threshold.",
                            nextAction: "Register package."))
    }

    func test_jsonRoundTripUsesSnakeCaseSchema() throws {
        let bundle = sampleBundle()
        let data = try FactoryRun.encode(bundle.config)
        let json = String(decoding: data, as: UTF8.self)
        XCTAssertTrue(json.contains(#""run_id""#))
        XCTAssertTrue(json.contains(#""base_model""#))
        XCTAssertTrue(json.contains(#""training_command""#))
        let decoded = try FactoryRun.decode(FactoryRun.Config.self, from: data)
        XCTAssertEqual(decoded, bundle.config)
    }

    func test_validateAcceptsCompleteShipBundle() throws {
        XCTAssertNoThrow(try sampleBundle().validate())
    }

    func test_validateRejectsShipWithoutArtifact() throws {
        let bundle = sampleBundle(artifact: nil)
        let missing = FactoryRun.Bundle(
            config: bundle.config,
            dataset: bundle.dataset,
            baseline: bundle.baseline,
            candidate: bundle.candidate,
            artifact: nil,
            decision: .init(decision: .ship, reason: "no artifact"))
        XCTAssertThrowsError(try missing.validate()) { error in
            XCTAssertEqual(error as? FactoryRun.ValidationError, .shipDecisionMissingArtifact)
        }
    }

    func test_validateRejectsShipWithUnshippedArtifact() throws {
        let bundle = sampleBundle(shipped: false)
        XCTAssertThrowsError(try bundle.validate()) { error in
            XCTAssertEqual(error as? FactoryRun.ValidationError,
                           .shipDecisionWithUnshippedArtifact(id: "pace-planner-sft-v1"))
        }
    }

    func test_validateRejectsEmptyDatasetSources() {
        let dataset = FactoryRun.DatasetManifest(datasetId: "empty", sources: [])
        XCTAssertThrowsError(try FactoryRun.validate(dataset)) { error in
            XCTAssertEqual(error as? FactoryRun.ValidationError, .emptySources)
        }
    }

    func test_markdownReportContainsBeforeAfterAndDecision() {
        let report = sampleBundle().markdownReport()
        XCTAssertTrue(report.contains("Decision: ship"))
        XCTAssertTrue(report.contains("| pace-v11-ship-gate | 0.7500 | 0.9600 | 0.2100 | yes |"))
        XCTAssertTrue(report.contains("Register package."))
    }
}
