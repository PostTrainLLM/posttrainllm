import XCTest
@testable import TinyGPTRun
@testable import TinyGPTCheck

/// Runner-planning tests for `model-run` — pure fixtures over a
/// ModelCheckReport, no network and no subprocesses. Each case maps to
/// an acceptance row from issue #157: safetensors+verified → native
/// first; GGUF → ollama, or lms when Ollama is absent; unsupported
/// arch → the installed alternative; nothing installed → a named
/// blocker rather than a silent failure.
final class RunnerPlanTests: XCTestCase {

    // MARK: - fixtures

    private func report(formats: [String],
                        checkedStatus: ModelCheckReport.Verdict = .expectedToWork,
                        checkedDetail: String = "verified architecture",
                        ollama: Bool = false,
                        lms: Bool = false,
                        mlxLm: Bool = false,
                        llamaCpp: Bool = false,
                        gated: Bool = false,
                        variant: String? = nil) -> ModelCheckReport {
        var runtimes: [ModelCheckReport.RuntimeProbe] = [
            .init(name: "ollama", found: ollama, version: ollama ? "0.34.2" : nil,
                  detail: "test"),
            .init(name: "lms (LM Studio)", found: lms,
                  version: lms ? "0.3.27" : nil, detail: "test"),
            .init(name: "llama.cpp", found: llamaCpp,
                  version: llamaCpp ? "7000" : nil, detail: "test"),
            .init(name: "python3 ML stack", found: mlxLm,
                  version: mlxLm ? "mlx==0.31.2, mlx-lm==0.31.3" : nil,
                  detail: "test"),
        ]
        if !ollama && !lms && !mlxLm && !llamaCpp { runtimes = [] }
        return ModelCheckReport(
            schemaVersion: 1, checkedAt: "2026-09-22T00:00:00Z",
            input: "x/y",
            model: .init(id: "x/y", revision: "main", task: "text-generation",
                         library: "transformers",
                         architectures: ["LlamaForCausalLM"], formats: formats,
                         selectedVariant: variant, gated: gated,
                         lastModified: nil),
            environment: .init(chip: "Apple M5 Pro", arch: "arm64",
                               ramBytes: 48 * 1_073_741_824,
                               freeDiskBytes: 400 * 1_073_741_824,
                               macOSVersion: "macOS 26.0", source: "detected",
                               runtimes: runtimes),
            verdict: checkedStatus,
            verdictSummary: "summary",
            checkedPath: .init(name: "posttrainllm native runtime",
                               status: checkedStatus, detail: checkedDetail),
            otherPaths: [], requiredChanges: [], evidence: [],
            nextActions: [], agentPrompt: "", limitations: [])
    }

    private func runners(_ r: ModelCheckReport,
                         forced: Runner? = nil) -> [Runner] {
        RunnerPlanner.plans(for: r, forced: forced).map(\.runner)
    }

    // MARK: - safetensors

    func testVerifiedSafetensorsPrefersNative() {
        let r = report(formats: ["safetensors"], ollama: true, mlxLm: true)
        XCTAssertEqual(runners(r).first, .native)
        XCTAssertTrue(runners(r).contains(.mlxLm))   // installed alternative still listed
        XCTAssertFalse(runners(r).contains(.ollama)) // nothing GGUF to pull
    }

    func testSafetensorsOnlyOnNativeWhenCheckedOK() {
        let r = report(formats: ["safetensors"])
        XCTAssertEqual(runners(r), [.native])
    }

    func testUnsupportedArchSkipsNativeForMlxLm() {
        // MoE on the checked path → native would build the wrong model;
        // the installed alternative is the plan.
        let r = report(formats: ["safetensors"],
                       checkedStatus: .unsupportedOnCheckedPath,
                       checkedDetail: "MoE — the HF loader builds a dense MLP",
                       mlxLm: true)
        XCTAssertEqual(runners(r), [.mlxLm])
    }

    func testUnknownCheckedPathStaysOffNative() {
        let r = report(formats: ["safetensors"],
                       checkedStatus: .unknown,
                       checkedDetail: "architecture not in the verified set",
                       mlxLm: true)
        XCTAssertFalse(runners(r).contains(.native))
        XCTAssertEqual(runners(r), [.mlxLm])
    }

    func testSafetensorsUnsupportedNothingInstalled() {
        let r = report(formats: ["safetensors"],
                       checkedStatus: .unsupportedOnCheckedPath,
                       checkedDetail: "MoE — the HF loader builds a dense MLP")
        XCTAssertTrue(runners(r).isEmpty)
        let blocker = RunnerPlanner.blocker(for: r)
        XCTAssertTrue(blocker.contains("mlx-lm"))
        XCTAssertTrue(blocker.contains("dense MLP"))
    }

    // MARK: - GGUF

    func testGGUFPrefersOllama() {
        let r = report(formats: ["gguf"], checkedStatus: .changesRequired,
                       ollama: true, lms: true, llamaCpp: true,
                       variant: "Qwen3-4B-Q4_K_M.gguf")
        // lms + llama-cli stay live fallbacks — detected ≠ working.
        XCTAssertEqual(runners(r), [.ollama, .lms, .llamaCpp])
    }

    func testGGUFFallsBackToLmsWithoutOllama() {
        let r = report(formats: ["gguf"], checkedStatus: .changesRequired,
                       lms: true)
        XCTAssertEqual(runners(r), [.lms])
    }

    func testGGUFNeverPlansNative() {
        // gguf-load validates structure only — it must not appear as a
        // run path even when the checked path cleared.
        let r = report(formats: ["gguf"],
                       checkedStatus: .changesRequired,
                       checkedDetail: "verified loadable by gguf-load")
        XCTAssertFalse(runners(r).contains(.native))
    }

    func testGGUFFallsBackToLlamaCliAlone() {
        let r = report(formats: ["gguf"], checkedStatus: .changesRequired,
                       llamaCpp: true)
        XCTAssertEqual(runners(r), [.llamaCpp])
    }

    func testGGUFNoRuntimeIsNamedBlocker() {
        let r = report(formats: ["gguf"])
        XCTAssertTrue(runners(r).isEmpty)
        let blocker = RunnerPlanner.blocker(for: r)
        XCTAssertTrue(blocker.contains("ollama"))
        XCTAssertTrue(blocker.contains("LM Studio"))
    }

    // MARK: - forced runtime

    func testForcedRunnerNarrowsToOne() {
        let r = report(formats: ["safetensors"], ollama: true, mlxLm: true)
        XCTAssertEqual(runners(r, forced: .mlxLm), [.mlxLm])
    }

    func testForcedUnavailableRunnerIsBlocker() {
        let r = report(formats: ["gguf"], lms: true)
        XCTAssertTrue(runners(r, forced: .ollama).isEmpty)
        XCTAssertTrue(RunnerPlanner.blocker(for: r, forced: .ollama)
            .contains("ollama"))
    }

    func testForcedNativeOnGGUFRefused() {
        let r = report(formats: ["gguf"], ollama: true)
        XCTAssertTrue(runners(r, forced: .native).isEmpty)
        XCTAssertTrue(RunnerPlanner.blocker(for: r, forced: .native)
            .contains("safetensors"))
    }

    // MARK: - ollama quant tag

    func testQuantTagFromSelectedVariant() {
        let r = report(formats: ["gguf"], variant: "Qwen3-4B-Instruct-Q4_K_M.gguf")
        XCTAssertEqual(ModelRunner.ggufQuantTag(report: r), "Q4_K_M")
    }

    func testQuantTagRejectsNonQuantComponent() {
        // "Qwen3" must not read as quant Q3 — only the trailing
        // quant-shaped filename component counts.
        let r = report(formats: ["gguf"], variant: "Qwen3-4B-F16.gguf")
        XCTAssertEqual(ModelRunner.ggufQuantTag(report: r), "F16")
        let noQuant = report(formats: ["gguf"], variant: "model-weights.gguf")
        XCTAssertNil(ModelRunner.ggufQuantTag(report: noQuant))
        let noVariant = report(formats: ["gguf"])
        XCTAssertNil(ModelRunner.ggufQuantTag(report: noVariant))
    }
}
