import Foundation

enum EvalBFCL {
    static func run(args: [String]) {
        var categories = "simple,multiple,parallel,parallel_multiple,relevance,irrelevance,live_simple,live_multiple,live_parallel,live_parallel_multiple"
        var root = "\(FileManager.default.homeDirectoryForCurrentUser.path)/.cache/tinygpt/datasets/_external/gorilla-bfcl/berkeley-function-call-leaderboard"
        var bfclModel = "openbmb/MiniCPM-SALA-FC"
        var toolsPath: String?
        var toolMode = "full"
        let parsed = EvalHarnessSupport.parseCommon(args, usage: { exitUsage() })
        var common = parsed.0
        let rest = parsed.1
        var i = 0
        while i < rest.count {
            switch rest[i] {
            case "--tasks", "--categories": categories = rest[i + 1]; i += 2
            case "--bfcl-root": root = rest[i + 1]; i += 2
            case "--bfcl-model": bfclModel = rest[i + 1]; i += 2
            case "--tools": toolsPath = rest[i + 1]; i += 2
            case "--tool-mode":
                toolMode = rest[i + 1]
                guard toolMode == "full" || toolMode == "deferred" else {
                    fputs("--tool-mode must be full or deferred\n", stderr); exitUsage()
                }
                i += 2
            default: fputs("unknown flag: \(rest[i])\n", stderr); exitUsage()
            }
        }
        common = EvalHarnessSupport.require(common, usage: { exitUsage() })
        guard let model = common.modelPath else { exitUsage() }

        let work = URL(fileURLWithPath: "/tmp/tinygpt-bfcl-\(UUID().uuidString.prefix(8))")
        let resultDir = work.appendingPathComponent("result")
        let scoreDir = work.appendingPathComponent("score")
        let toolMetrics = work.appendingPathComponent("tool-metrics.jsonl")
        try? FileManager.default.createDirectory(at: resultDir, withIntermediateDirectories: true)
        try? FileManager.default.createDirectory(at: scoreDir, withIntermediateDirectories: true)

        var serveArgs: [String] = []
        if let toolsPath {
            serveArgs += ["--tools", toolsPath, "--tool-mode", toolMode]
            if toolMode == "deferred" {
                serveArgs += ["--tool-metrics-out", toolMetrics.path]
            }
        } else if toolMode != "full" {
            fputs("--tool-mode deferred requires --tools <path.json>\n", stderr)
            exitUsage()
        }
        let serve = EvalHarnessSupport.startServe(modelPath: model, port: common.servePort, extraArgs: serveArgs)
        defer { if serve.isRunning { serve.terminate() } }

        let py = EvalHarnessSupport.resolveExecutable("python3") ?? URL(fileURLWithPath: "/usr/bin/python3")
        let base = "http://127.0.0.1:\(common.servePort)/v1"
        let env = [
            "OPENAI_API_KEY": "tinygpt",
            "OPENAI_BASE_URL": base,
            "BFCL_PROJECT_ROOT": root
        ]
        let start = Date()
        let genArgs = [
            "-m", "bfcl_eval._llm_response_generation",
            "--model", bfclModel,
            "--test-category"
        ] + categories.split(separator: ",").map(String.init) + [
            "--result-dir", resultDir.path,
            "--skip-server-setup",
            "--allow-overwrite"
        ]
        let genStatus = EvalHarnessSupport.runProcess(py, genArgs, cwd: URL(fileURLWithPath: root), env: env)
        guard genStatus == 0 else { fputs("BFCL generation failed with exit \(genStatus)\n", stderr); exit(genStatus) }

        let evalArgs = [
            "-m", "bfcl_eval.eval_checker.eval_runner",
            "--model", bfclModel,
            "--test-category"
        ] + categories.split(separator: ",").map(String.init) + [
            "--result-dir", resultDir.path,
            "--score-dir", scoreDir.path,
            "--partial-eval"
        ]
        let evalStatus = EvalHarnessSupport.runProcess(py, evalArgs, cwd: URL(fileURLWithPath: root), env: env)
        guard evalStatus == 0 else { fputs("BFCL scoring failed with exit \(evalStatus)\n", stderr); exit(evalStatus) }

        let wall = -start.timeIntervalSinceNow
        guard let scoreURL = EvalHarnessSupport.latestJSON(under: scoreDir),
              let json = EvalHarnessSupport.jsonObject(scoreURL)
        else { fputs("could not find BFCL score JSON under \(scoreDir.path)\n", stderr); exit(1) }

        var emitted = 0
        for (name, score, n) in EvalHarnessSupport.numericScores(json) {
            let metric = name.split(separator: "/").last.map(String.init) ?? "accuracy"
            let subtask = name.split(separator: "/").dropLast().last.map(String.init)
            EvalHarnessSupport.appendRow(common: common, task: "bfcl", subtask: subtask,
                                         metric: metric, score: score, n: n, wall: wall,
                                         harness: "bfcl")
            emitted += 1
        }
        if toolMode == "deferred", let (avgHops, n) = toolHopSummary(toolMetrics) {
            EvalHarnessSupport.appendRow(common: common, task: "bfcl", subtask: "deferred_tools",
                                         metric: "get_tool_info_hops", score: avgHops, n: n,
                                         wall: wall, harness: "bfcl-tool-metrics")
            emitted += 1
        }
        print("✓ wrote \(emitted) BFCL rows to \(common.outJsonl!)")
    }

    private static func toolHopSummary(_ url: URL) -> (Double, Int)? {
        guard let data = try? Data(contentsOf: url),
              let text = String(data: data, encoding: .utf8)
        else { return nil }
        var total = 0.0
        var count = 0
        for line in text.split(separator: "\n") {
            guard let lineData = String(line).data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: lineData) as? [String: Any],
                  let hops = EvalHarnessSupport.doubleValue(obj["get_tool_info_hops"])
            else { continue }
            total += hops
            count += 1
        }
        guard count > 0 else { return nil }
        return (total / Double(count), count)
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt eval-bfcl <model.tinygpt|hf-dir> --out <jsonl> [options]

        --tokenizer <dir>       accepted for symmetry; serve reads model config
        --tasks <csv>           BFCL categories (default: core non-exec set)
        --limit N               reserved for future BFCL run-id sampling
        --serve-port N          local tinygpt serve port (default: 8097)
        --budget <json>         fixed eval budget metadata for emitted rows
        --bfcl-root <dir>       local BFCL checkout
        --bfcl-model NAME       BFCL registry model id (default: openbmb/MiniCPM-SALA-FC)
        --tools <json>          OpenAI-compatible tool schema passed to serve
        --tool-mode MODE        serve tool mode: full|deferred (default: full)
        --model-name NAME       display name in eval-compare
        --model-step N          checkpoint step
        """)
        exit(code)
    }
}
