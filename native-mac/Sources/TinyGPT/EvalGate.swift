import Foundation
import TinyGPTIO
import TinyGPTModel

/// `posttrainllm eval-gate` (B32) — run a project's declared eval suites against
/// a baseline and exit non-zero when any suite regresses past its threshold.
///
/// The judgement lives in `TinyGPTModel.EvalGate` (pure, unit-tested). This
/// command is the orchestration shell: resolve the spec, obtain candidate
/// rows (from a `--candidate` JSONL or by running the suites), compare,
/// print, write `gate-result.json`, and set the exit code.
enum EvalGateCommand {
    static func run(args: [String]) {
        var specPath: String? = nil
        var candidatePath: String? = nil
        var baselineOverride: String? = nil
        var outPath: String? = nil
        var thresholdOverride: Double? = nil
        var budgetPath: String? = nil
        var factoryRunPath: String? = nil
        var passes = 1
        var updateBaseline = false

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--spec": specPath = value(args, &i)
            case "--candidate": candidatePath = value(args, &i)
            case "--baseline": baselineOverride = value(args, &i)
            case "--out": outPath = value(args, &i)
            case "--threshold": thresholdOverride = Double(value(args, &i) ?? "")
            case "--budget": budgetPath = value(args, &i)
            case "--factory-run": factoryRunPath = value(args, &i)
            case "--passes": passes = Int(value(args, &i) ?? "") ?? 1
            case "--update-baseline": updateBaseline = true; i += 1
            case "-h", "--help": exitUsage(0)
            default:
                fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }

        // 1. Resolve the spec.
        let baseSpec = resolveSpec(explicitPath: specPath)
        let baselinePath = baselineOverride ?? baseSpec.baseline
        let spec = EvalGate.Spec(
            baseline: baselinePath,
            defaultThreshold: thresholdOverride ?? baseSpec.defaultThreshold,
            suites: baseSpec.suites)
        let budget = loadBudget(budgetPath)
        let protocolBlock = EvalGate.AgentEvalProtocol(passes: passes, budget: budget)
        if factoryRunPath != nil && updateBaseline {
            fputs("--factory-run cannot be combined with --update-baseline\n", stderr)
            exit(2)
        }

        var factoryContext: FactoryRunEvidence.Context?
        let evaluationStartedAt = Date()
        if let factoryRunPath {
            do {
                // Fail before a suite can load a model when frozen run context
                // or the declared baseline is unavailable.
                _ = try EvalGate.loadRows(fromJSONLAt: baselinePath)
                let directory = URL(fileURLWithPath: factoryRunPath)
                factoryContext = try FactoryRunEvidence.inspect(
                    directory: directory,
                    expectedPhase: .trained
                )
                let declaredPrimary = factoryContext!.config.eval.primary
                let declaredMatches = spec.suites.filter {
                    $0.name == declaredPrimary || $0.resolvedTask == declaredPrimary
                }
                guard declaredMatches.count == 1 else {
                    throw FactoryRunEvidence.EvidenceError.invalidSlice(
                        "frozen primary suite '\(declaredPrimary)' must match one eval-gate suite"
                    )
                }
                if let candidatePath {
                    _ = try EvalGate.loadRows(fromJSONLAt: candidatePath)
                }
                _ = try FactoryRunEvidence.beginEvaluation(directory: directory)
            } catch {
                fputs("eval-gate factory-run preflight failed: \(error)\n", stderr)
                exit(2)
            }
        }

        // 2. Obtain candidate rows + the JSONL file they came from (so
        //    --update-baseline can copy full EvalCompare.Row fidelity).
        let (candidateRows, candidateFile) = resolveCandidate(
            candidatePath: candidatePath, spec: spec, passes: passes, budgetPath: budgetPath)

        // 3. --update-baseline: re-stamp the baseline from the candidate run.
        if updateBaseline {
            guard let src = candidateFile else {
                fputs("--update-baseline needs candidate rows from a file or a suite run\n", stderr)
                exit(2)
            }
            do {
                let data = try Data(contentsOf: URL(fileURLWithPath: src))
                try data.write(to: URL(fileURLWithPath: baselinePath), options: .atomic)
                print("✓ baseline re-stamped: \(baselinePath) (\(candidateRows.count) rows)")
                exit(0)
            } catch {
                fputs("could not write baseline \(baselinePath): \(error)\n", stderr); exit(1)
            }
        }

        // 4. Load baseline + evaluate.
        let baselineRows: [EvalGate.Row]
        do {
            baselineRows = try EvalGate.loadRows(fromJSONLAt: baselinePath)
        } catch {
            fputs("could not read baseline \(baselinePath): \(error)\n", stderr)
            fputs("hint: run with --update-baseline once to stamp the first baseline\n", stderr)
            exit(2)
        }

        let summarized = EvalGate.summarizedByKey(candidateRows)
        let hasRepeatedRows = !summarized.stats.isEmpty
        let rowsForGate = (passes > 1 || hasRepeatedRows) ? summarized.rows : candidateRows
        let report = EvalGate.evaluate(
            baseline: baselineRows,
            candidate: rowsForGate,
            candidateStats: summarized.stats,
            spec: spec,
            evalProtocol: protocolBlock)

        if let factoryRunPath, let factoryContext {
            do {
                let primary = try primarySuite(
                    report,
                    named: factoryContext.config.eval.primary
                )
                guard let baselineScore = primary.baselineScore,
                      let candidateScore = primary.candidateScore else {
                    throw FactoryRunEvidence.EvidenceError.invalidSlice(
                        "primary suite is missing baseline or candidate score"
                    )
                }
                guard let candidateFile else {
                    throw FactoryRunEvidence.EvidenceError.invalidSlice(
                        "candidate E0 source is unavailable"
                    )
                }
                let baselineId = try uniqueModelId(at: baselinePath, baseline: true)
                let candidateId = try uniqueCandidateModelId(at: candidateFile)
                let command = "posttrainllm eval-gate --factory-run"
                let date = ISO8601DateFormatter().string(from: Date())
                let baseline = FactoryRun.EvalResult(
                    modelId: baselineId,
                    command: command,
                    suite: factoryContext.config.eval.primary,
                    score: baselineScore,
                    date: date,
                    notes: "Recorded from the frozen eval-gate baseline row."
                )
                let candidate = FactoryRun.EvalResult(
                    modelId: candidateId,
                    command: command,
                    suite: factoryContext.config.eval.primary,
                    score: candidateScore,
                    passed: primary.verdict == .pass,
                    date: date,
                    notes: "Recorded from the same eval-gate invocation as the baseline."
                )
                _ = try FactoryRunEvidence.finishEvaluation(
                    directory: URL(fileURLWithPath: factoryRunPath),
                    baseline: baseline,
                    candidate: candidate,
                    evalTimeSeconds: -evaluationStartedAt.timeIntervalSinceNow,
                    command: command
                )
                print("✓ recorded canonical evaluation evidence in \(factoryRunPath)")
            } catch {
                fputs("eval-gate completed but could not record factory-run evidence: \(error)\n",
                      stderr)
                exit(1)
            }
        }

        // 5. Print + persist + exit code.
        printReport(report, spec: spec, passes: passes)
        writeResult(report, to: outPath ?? "gate-result.json")
        exit(report.passed ? 0 : 1)
    }

    // MARK: - spec resolution

    private static func resolveSpec(explicitPath: String?) -> EvalGate.Spec {
        if let p = explicitPath {
            guard let s = loadStandaloneSpec(p) else {
                fputs("could not parse eval-gate spec at \(p)\n", stderr); exit(2)
            }
            return s
        }
        // Default search order: ./eval-gate.json, then the project file.
        if FileManager.default.fileExists(atPath: "eval-gate.json"),
           let s = loadStandaloneSpec("eval-gate.json") {
            return s
        }
        if FileManager.default.fileExists(atPath: "posttrainllm.project.json") {
            if let manifest = try? ProjectManifest.load(path: "posttrainllm.project.json"),
               let s = manifest.eval {
                return s
            }
            fputs("posttrainllm.project.json has no \"eval\" block; add one or pass --spec\n", stderr)
            exit(2)
        }
        fputs("no eval-gate spec found (looked for --spec, ./eval-gate.json, ./posttrainllm.project.json)\n", stderr)
        exit(2)
    }

    private static func loadStandaloneSpec(_ path: String) -> EvalGate.Spec? {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)) else { return nil }
        return try? EvalGate.Spec.jsonDecoder.decode(EvalGate.Spec.self, from: data)
    }

    private static func loadBudget(_ path: String?) -> EvalGate.AgentEvalBudget? {
        guard let path else { return nil }
        do {
            let data = try Data(contentsOf: URL(fileURLWithPath: path))
            let dec = JSONDecoder()
            return try dec.decode(EvalGate.AgentEvalBudget.self, from: data)
        } catch {
            fputs("could not parse eval budget at \(path): \(error)\n", stderr)
            exit(2)
        }
    }

    // MARK: - candidate resolution

    /// Returns (rows, sourceJSONLPath). When `--candidate` is given we read
    /// it directly (the GPU-free CI path). Otherwise we run each declared
    /// suite's command, appending to one temp JSONL, K times for K passes.
    private static func resolveCandidate(candidatePath: String?,
                                         spec: EvalGate.Spec,
                                         passes: Int,
                                         budgetPath: String?) -> ([EvalGate.Row], String?) {
        if let p = candidatePath {
            guard let rows = try? EvalGate.loadRows(fromJSONLAt: p) else {
                fputs("could not read candidate \(p)\n", stderr); exit(2)
            }
            return (rows, p)
        }

        // Run the suites. Each suite command is expected to write
        // EvalCompare.Row JSONL to the path we pass as TINYGPT_EVAL_OUT.
        guard !spec.suites.isEmpty else {
            fputs("no --candidate and spec declares no suites to run\n", stderr); exit(2)
        }
        let temp = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("posttrainllm-gate-\(UUID().uuidString.prefix(8)).jsonl")
        for pass in 0..<max(1, passes) {
            for suite in spec.suites {
                guard let cmd = suite.command, let exe = cmd.first else {
                    fputs("suite '\(suite.name)' has no command; cannot run (pass --candidate instead)\n", stderr)
                    exit(2)
                }
                let exeURL = EvalHarnessSupport.resolveExecutable(exe)
                    ?? URL(fileURLWithPath: exe)
                // Process() does no shell expansion, so substitute the
                // $TINYGPT_EVAL_OUT token in the argv ourselves (and still
                // export it as env for harnesses that read it directly).
                let expanded = cmd.dropFirst().map {
                    $0.replacingOccurrences(of: "${TINYGPT_EVAL_OUT}", with: temp.path)
                        .replacingOccurrences(of: "$TINYGPT_EVAL_OUT", with: temp.path)
                }
                var env = ["TINYGPT_EVAL_OUT": temp.path]
                if let budgetPath {
                    env["TINYGPT_EVAL_BUDGET"] = budgetPath
                }
                env["TINYGPT_EVAL_PASSES"] = "\(max(1, passes))"
                let status = EvalHarnessSupport.runProcess(exeURL, expanded, env: env)
                if status != 0 {
                    fputs("suite '\(suite.name)' exited \(status) on pass \(pass + 1)\n", stderr)
                    exit(status)
                }
            }
        }
        let rows = (try? EvalGate.loadRows(fromJSONLAt: temp.path)) ?? []
        return (rows, temp.path)
    }

    // MARK: - render

    private static func printReport(_ report: EvalGate.Report, spec: EvalGate.Spec, passes: Int) {
        let nameW = max(12, report.suites.map { ($0.name + "/" + ($0.subtask ?? $0.metric)).count }.max() ?? 12)
        print("")
        print("eval-gate — baseline \(spec.baseline)" + (passes > 1 ? "  (K=\(passes) passes, mean)" : ""))
        let header = "suite".padding(toLength: nameW, withPad: " ", startingAt: 0)
            + "  base    cand    Δpp     thr    verdict"
        print(header)
        print(String(repeating: "─", count: header.count))
        for s in report.suites {
            let label = (s.name + "/" + (s.subtask ?? s.metric)).padding(toLength: nameW, withPad: " ", startingAt: 0)
            let base = s.baselineScore.map { String(format: "%.3f", $0) } ?? "  —  "
            let cand: String
            if let stats = s.candidateStats, stats.n > 1 {
                let halfWidth = (stats.ci95High - stats.ci95Low) / 2.0
                cand = String(format: "%.3f±%.3f", stats.mean, halfWidth)
            } else {
                cand = s.candidateScore.map { String(format: "%.3f", $0) } ?? "  —  "
            }
            let delta = s.deltaPP.map { String(format: "%+.1f", $0) } ?? "  —  "
            let thr = String(format: "%.1f", s.thresholdPP)
            let mark: String
            switch s.verdict {
            case .pass: mark = "PASS"
            case .fail: mark = "FAIL ✗"
            case .missing: mark = "MISSING"
            }
            print("\(label)  \(base)   \(cand)   \(delta.padding(toLength: 6, withPad: " ", startingAt: 0)) \(thr.padding(toLength: 5, withPad: " ", startingAt: 0))  \(mark)")
        }
        print(String(repeating: "─", count: header.count))
        if report.passed {
            print("✓ gate PASSED — \(report.suites.count) suites, 0 regressions"
                + (report.missingCount > 0 ? " (\(report.missingCount) missing baseline)" : ""))
        } else {
            print("✗ gate FAILED — \(report.failedCount) suite(s) regressed past threshold")
        }
        print("")
    }

    private static func writeResult(_ report: EvalGate.Report, to path: String) {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? enc.encode(report) else { return }
        try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
    }

    private static func primarySuite(_ report: EvalGate.Report,
                                     named primary: String) throws -> EvalGate.SuiteResult {
        let matches = report.suites.filter { suite in
            suite.name == primary || suite.task == primary
                || [suite.task, suite.subtask].compactMap { $0 }.joined(separator: "/") == primary
        }
        guard matches.count == 1, let match = matches.first else {
            throw FactoryRunEvidence.EvidenceError.invalidSlice(
                "primary suite '\(primary)' matched \(matches.count) gate rows"
            )
        }
        return match
    }

    private struct ModelIdentityRow: Decodable {
        let modelName: String
        let baseline: Bool

        enum CodingKeys: String, CodingKey {
            case modelName = "model_name"
            case baseline
        }
    }

    private static func uniqueCandidateModelId(at path: String) throws -> String {
        try uniqueModelId(at: path, baseline: false)
    }

    private static func uniqueModelId(at path: String, baseline: Bool) throws -> String {
        let text = try String(contentsOfFile: path, encoding: .utf8)
        let decoder = JSONDecoder()
        let names = try Set(text.split(separator: "\n").compactMap { line -> String? in
            let row = try decoder.decode(ModelIdentityRow.self, from: Data(line.utf8))
            return row.baseline == baseline ? row.modelName : nil
        })
        guard names.count == 1, let name = names.first,
              !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw FactoryRunEvidence.EvidenceError.invalidSlice(
                "E0 rows must name exactly one \(baseline ? "baseline" : "candidate") model"
            )
        }
        return name
    }

    // MARK: - arg helper

    private static func value(_ args: [String], _ i: inout Int) -> String? {
        guard i + 1 < args.count else { i += 1; return nil }
        let v = args[i + 1]; i += 2; return v
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm eval-gate [options]

        Run a project's declared eval suites against a baseline and exit
        non-zero when any suite regresses past its threshold. Designed to run
        on a self-hosted Mac runner so the model never leaves the device.

        Spec resolution (first found wins):
          --spec <path>            explicit eval-gate.json
          ./eval-gate.json         standalone spec in the cwd
          ./posttrainllm.project.json   the optional "eval" block (B31)

        Options:
          --candidate <jsonl>      compare these rows instead of running the
                                   suites (CI/test path; no GPU needed)
          --baseline <jsonl>       override the spec's baseline path
          --threshold <pp>         override the default regression tolerance
                                   (percentage points; per-suite values win)
          --budget <json>          attach fixed eval budget/protocol metadata
                                   to gate-result.json and expose it to suite
                                   commands as TINYGPT_EVAL_BUDGET
          --passes <K>             run each suite K times, gate on the mean
          --factory-run <dir>      write canonical before/after fragments and
                                   advance a prepared run from trained to evaluated
          --update-baseline        re-stamp the baseline from this run, exit 0
          --out <path>             gate-result.json location (default: ./)

        Exit code: 0 if all suites pass, 1 if any regresses past threshold.
        """)
        exit(code)
    }
}
