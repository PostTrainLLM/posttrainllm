import Foundation
import TinyGPTCheck
import TinyGPTData

/// `posttrainllm model-run <url>` — check → pick runtime → download →
/// run → verify. Closes the loop that `model-check` opens: instead of
/// only predicting compatibility, it executes the best *installed*
/// runtime and reports measured success/failure.
///
/// Runner selection:
///   GGUF repo           → ollama (`ollama run hf.co/<id>`) or lms hint
///   safetensors verified→ native posttrainllm (download → hf-load)
///   safetensors other   → mlx-lm (widest arch table, auto-downloads)
///   gated without token → named blocker (accept license + HF_TOKEN)
///
/// Every runner is a bounded subprocess (timeout, captured output);
/// failures surface the runtime's real error, which is itself evidence.
/// `--chat` execs into the runtime's interactive session instead of the
/// bounded sample. Nothing is left running afterwards.
enum ModelRun {

    enum Runner: String {
        case native = "native"       // posttrainllm hf-load
        case mlxSwift = "mlx-swift"  // MLX-Swift-LM in-process (wide arch table)
        case mlxLm  = "mlx-lm"       // python3 -m mlx_lm
        case ollama = "ollama"       // ollama run hf.co/<id>
    }

    static func run(args: [String]) {
        var refString: String? = nil
        var chat = false
        var maxTokens = 32
        var forcedRunner: Runner? = nil
        var prompt = "Say hello in one sentence."
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--chat":       chat = true; i += 1
            case "--max-tokens": maxTokens = Int(args[i + 1]) ?? maxTokens; i += 2
            case "--prompt":     prompt = args[i + 1]; i += 2
            case "--runtime":    forcedRunner = Runner(rawValue: args[i + 1]); i += 2
            case "-h", "--help": usage(0)
            default:
                if args[i].hasPrefix("-") { fputs("model-run: unknown flag \(args[i])\n", stderr); usage(2) }
                refString = args[i]; i += 1
            }
        }
        guard let refString else { usage(2) }

        // 1. Check — reuse the full machinery, verdicts and all.
        print("checking \(refString)…")
        let report: ModelCheckReport
        do { report = try ModelCheckService.check(input: refString) }
        catch { fputs("check failed: \(error)\n", stderr); exit(2) }
        print("verdict: \(report.verdict.rawValue) — \(report.verdictSummary)\n")

        // 2. Access gate first — nothing runs gated without a token.
        if report.model.gated,
           (ProcessInfo.processInfo.environment["HF_TOKEN"] ?? "").isEmpty {
            fputs("""
            blocked: \(report.model.id) is gated — accept the license at
              https://huggingface.co/\(report.model.id)
            and set HF_TOKEN, then re-run.
            """, stderr)
            exit(3)
        }

        // 3. Pick runners, try each in order — a detected runtime can
        // still be broken (partial installs happen), so failure falls
        // through to the next candidate rather than dead-ending.
        let plans = runnerPlans(report: report, forced: forcedRunner)
        guard !plans.isEmpty else {
            fputs("no runnable path for this verdict — see `model-check` report.\n", stderr)
            exit(3)
        }
        for (i, plan) in plans.enumerated() {
            if i > 0 { print("falling back to \(plan.runner.rawValue)…") }
            print("runner: \(plan.runner.rawValue) — \(plan.why)\n")
            let ok: Bool
            switch plan.runner {
            case .ollama:
                ok = runOllama(report: report, prompt: prompt,
                               tokens: maxTokens, chat: chat)
            case .mlxSwift:
                ok = runMlxSwift(id: report.model.id, prompt: prompt,
                                 tokens: maxTokens, chat: chat)
            case .mlxLm:
                ok = runMlxLm(id: report.model.id, prompt: prompt,
                              tokens: maxTokens, chat: chat)
            case .native:
                ok = runNative(report: report, prompt: prompt,
                               tokens: maxTokens)
            }
            if ok { reportSuccess(runner: plan.runner.rawValue,
                                  hint: chatHint(plan.runner, report: report)) }
            fputs("  \(plan.runner.rawValue) failed — trying next runner if any\n", stderr)
        }
        fputs("all runnable paths failed — real errors above.\n", stderr)
        exit(6)
    }

    private struct Plan {
        let runner: Runner
        let why: String
    }

    /// Ordered runner candidates. The order encodes preference: native
    /// first when the checked path is compatible (it's the *verification*
    /// step), installed alternatives after.
    private static func runnerPlans(report: ModelCheckReport,
                                    forced: Runner?) -> [Plan] {
        let env = report.environment.runtimes
        let hasOllama = env.contains { $0.name == "ollama" && $0.found }
        let hasMlxLm = env.contains { $0.name == "python3 ML stack" && $0.found
                                     && ($0.version?.contains("mlx-lm") ?? false) }
        let fmts = Set(report.model.formats)
        let checkedOK = report.checkedPath.status == .expectedToWork
            || report.checkedPath.status == .changesRequired

        if let forced {
            return [Plan(runner: forced, why: "forced via --runtime")]
        }

        var plans: [Plan] = []
        if fmts.contains("safetensors") && checkedOK {
            plans.append(Plan(runner: .native,
                why: "checked path compatible — verify with a real hf-load"))
        }
        if fmts.contains("gguf") && hasOllama {
            plans.append(Plan(runner: .ollama,
                why: "GGUF repo + Ollama installed — `ollama run hf.co/` pulls and runs directly"))
        }
        // MLX-Swift-LM is compiled in — always available, wider arch
        // table than our loader (MoE, VLM-adjacent, more quants).
        if fmts.contains("safetensors") {
            plans.append(Plan(runner: .mlxSwift,
                why: "MLX-Swift-LM in-process — wide architecture table, auto-downloads to the HF cache"))
        }
        if fmts.contains("safetensors") && hasMlxLm {
            plans.append(Plan(runner: .mlxLm,
                why: "python3 mlx-lm fallback — wider arch table, auto-downloads"))
        }
        // GGUF native attempt only when the checked path verified the
        // quant — downloading GBs to fail on a known-incompatible
        // K-quant is a waste.
        if fmts.contains("gguf") && checkedOK {
            plans.append(Plan(runner: .native,
                why: "GGUF header verified a supported quant — native gguf-load"))
        }
        return plans
    }

    // MARK: - runners

    /// `ollama run hf.co/<id> "<prompt>"` — one-shot non-interactive;
    /// ollama pulls the GGUF on first call. `--chat` execs interactive.
    private static func runOllama(report: ModelCheckReport, prompt: String,
                                  tokens: Int, chat: Bool) -> Bool {
        let id = report.model.id
        let model = "hf.co/\(id)"
        if chat {
            ensureOllamaDaemon()
            interactive(["ollama", "run", model])
        }
        var r = execCapture(["ollama", "run", model, prompt],
                            timeout: 1800)   // first run may pull GBs
        // Installed ≠ serving — start the daemon ourselves, retry once,
        // and kill only the process we spawned.
        var daemon: Process? = nil
        if r.status != 0, r.stderr.contains("could not connect") || r.stdout.contains("could not connect") {
            daemon = ensureOllamaDaemon()
            if daemon != nil {
                r = execCapture(["ollama", "run", model, prompt], timeout: 1800)
            }
        }
        // ollama's hf.co pull chokes on HF's Xet CDN cross-host redirects.
        // Robust fallback: download the GGUF ourselves (our downloader
        // follows redirects), `ollama create` from a Modelfile, run that.
        if r.status != 0,
           let variant = report.model.selectedVariant, variant.hasSuffix(".gguf") {
            print("ollama hf.co pull failed (Xet redirect) — downloading the GGUF directly…")
            if let local = try? downloadGGUF(report: report, variant: variant) {
                let name = "posttrainllm-" + variant
                    .replacingOccurrences(of: ".gguf", with: "")
                    .lowercased()
                let modelfile = local.deletingLastPathComponent()
                    .appendingPathComponent("Modelfile")
                try? "FROM \"\(local.path)\"\n".write(to: modelfile, atomically: true, encoding: .utf8)
                let c = execCapture(["ollama", "create", name, "-f", modelfile.path], timeout: 300)
                if c.status == 0 {
                    r = execCapture(["ollama", "run", name, prompt], timeout: 600)
                }
            }
        }
        daemon?.terminate()
        return printOutcome(runner: "ollama", result: r)
    }

    /// Download the selected GGUF variant into the model cache.
    private static func downloadGGUF(report: ModelCheckReport, variant: String) throws -> URL {
        let dir = try modelCacheDir(report.model.id)
        let dest = dir.appendingPathComponent(variant)
        if !FileManager.default.fileExists(atPath: dest.path) {
            let url = "https://huggingface.co/\(report.model.id)/resolve/\(report.model.revision)/\(variant)"
            print("  \(variant)…")
            try HFDatasets.streamDownload(urlString: url, to: dest) { done, total in
                if total > 0 { fputs("\r    \(done * 100 / total)%", stderr) }
            }
            fputs("\n", stderr)
        }
        return dest
    }

    /// Start `ollama serve` if the daemon isn't answering; returns the
    /// spawned process (caller terminates it) or nil if it was already
    /// up or couldn't start.
    private static func ensureOllamaDaemon() -> Process? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = ["ollama", "serve"]
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        guard (try? p.run()) != nil else { return nil }
        // Poll `ollama list` until the daemon answers (≤10 s).
        for _ in 0..<50 {
            Thread.sleep(forTimeInterval: 0.2)
            let probe = Process()
            probe.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            probe.arguments = ["ollama", "list"]
            probe.standardOutput = FileHandle.nullDevice
            probe.standardError = FileHandle.nullDevice
            if (try? probe.run()) != nil {
                probe.waitUntilExit()
                if probe.terminationStatus == 0 { return p }
            }
        }
        p.terminate()
        return nil
    }

    /// MLX-Swift-LM via the `posttrainllm-mlxrun` sibling executable —
    /// Apple's maintained HF model impls (LLM + VLM + embedders), runs
    /// in its own process so load failures are captured results.
    /// Honors HF_TOKEN via the HubClient env auto-detect.
    private static func runMlxSwift(id: String, prompt: String,
                                    tokens: Int, chat: Bool) -> Bool {
        guard let bin = mlxrunBinary() else {
            fputs("posttrainllm-mlxrun not built — run `swift build --product posttrainllm-mlxrun`\n", stderr)
            return false
        }
        if chat { interactive([bin, id, "--chat"]) }
        let r = execCapture([bin, id, "--prompt", prompt,
                             "--max-tokens", String(tokens)],
                            timeout: 1800)
        return printOutcome(runner: "mlx-swift", result: r)
    }

    /// Locate the sibling `posttrainllm-mlxrun` next to this binary,
    /// else on PATH.
    private static func mlxrunBinary() -> String? {
        let self_ = CommandLine.arguments[0]
        let sibling = (self_ as NSString).deletingLastPathComponent
            + "/posttrainllm-mlxrun"
        if FileManager.default.fileExists(atPath: sibling) { return sibling }
        let which = execCapture(["which", "posttrainllm-mlxrun"], timeout: 5)
        let p = which.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
        return which.status == 0 && !p.isEmpty ? p : nil
    }

    /// `python3 -m mlx_lm generate` — auto-downloads to the HF cache,
    /// covers MoE/VLM/quantized archs our native loader doesn't.
    private static func runMlxLm(id: String, prompt: String,
                                 tokens: Int, chat: Bool) -> Bool {
        if chat { interactive(["python3", "-m", "mlx_lm", "chat", "--model", id]) }
        let r = execCapture(["python3", "-m", "mlx_lm", "generate",
                             "--model", id, "--prompt", prompt,
                             "--max-tokens", String(tokens)],
                            timeout: 1800)
        return printOutcome(runner: "mlx-lm", result: r)
    }

    /// Native path: download needed files to the posttrainllm cache,
    /// then shell out to `hf-load --sample` so a load failure is a
    /// captured result, not a process kill.
    private static func runNative(report: ModelCheckReport,
                                  prompt: String, tokens: Int) -> Bool {
        let id = report.model.id
        do {
            let dir = try modelCacheDir(id)
            let wanted = neededFiles(report: report)
            print("downloading \(wanted.count) files → \(dir.path)")
            for f in wanted {
                let dest = dir.appendingPathComponent(f)
                try FileManager.default.createDirectory(
                    at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)
                if FileManager.default.fileExists(atPath: dest.path) { continue }
                let url = "https://huggingface.co/\(id)/resolve/\(report.model.revision)/\(f)"
                print("  \(f)…")
                try HFDatasets.streamDownload(urlString: url, to: dest) { done, total in
                    if total > 0 { fputs("\r    \(done * 100 / total)%", stderr) }
                }
                fputs("\n", stderr)
            }
            let self_ = CommandLine.arguments[0]
            let argv: [String]
            if report.model.formats.contains("gguf") {
                argv = [self_, "gguf-load", destOfGGUF(dir: dir) ?? dir.path]
            } else {
                argv = [self_, "hf-load", dir.path,
                        "--sample", "--prompt", prompt, "--tokens", String(tokens)]
            }
            let r = execCapture(argv, timeout: 600)
            return printOutcome(runner: "native", result: r)
        } catch {
            fputs("native run failed during download: \(error)\n", stderr)
            return false
        }
    }

    private static func chatHint(_ runner: Runner, report: ModelCheckReport) -> String {
        switch runner {
        case .mlxSwift: return "posttrainllm model-run \(report.model.id) --chat"
        case .ollama:
            // If we created a local ollama model from a downloaded GGUF
            // (the hf.co pull path can hit Xet-redirect failures), point
            // at the local name instead.
            if let v = report.model.selectedVariant, v.hasSuffix(".gguf") {
                let name = "posttrainllm-" + v
                    .replacingOccurrences(of: ".gguf", with: "").lowercased()
                return "ollama run \(name)"
            }
            return "ollama run hf.co/\(report.model.id)"
        case .mlxLm:  return "python3 -m mlx_lm chat --model \(report.model.id)"
        case .native:
            return "\(CommandLine.arguments[0]) chat ~/.cache/posttrainllm/models/\(report.model.id)"
        }
    }

    /// Hand the terminal to an interactive session (used by --chat).
    private static func interactive(_ argv: [String]) -> Never {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = argv
        try? p.run()
        p.waitUntilExit()
        exit(p.terminationStatus)
    }

    /// Files needed for a local load: config, tokenizer, and weights
    /// (index + shards, or a single safetensors, or the GGUF variant).
    /// Small files are filtered against the manifest — e.g. Qwen3 ships
    /// tokenizer.json but no tokenizer.model, and a 404 on a guessed
    /// name must not kill the download.
    private static func neededFiles(report: ModelCheckReport) -> [String] {
        var files: [String] = []
        if let info = try? HubModelClient.info(
            id: report.model.id, revision: report.model.revision) {
            let names = Set(info.siblings.map(\.name))
            files += ["config.json", "tokenizer.json", "tokenizer.model",
                      "tokenizer_config.json", "generation_config.json",
                      "model.safetensors.index.json"].filter { names.contains($0) }
            files += info.siblings.map(\.name).filter { $0.hasSuffix(".safetensors") }
            // GGUF repos ship many quant variants — download only the one
            // model-check selected.
            if let v = report.model.selectedVariant, v.hasSuffix(".gguf") {
                files = files.filter { !$0.hasSuffix(".safetensors") } + [v]
            }
        }
        var seen = Set<String>()
        return files.filter { seen.insert($0).inserted }
    }

    private static func destOfGGUF(dir: URL) -> String? {
        try? FileManager.default.contentsOfDirectory(atPath: dir.path)
            .first { $0.hasSuffix(".gguf") }
            .map { dir.appendingPathComponent($0).path }
    }

    private static func modelCacheDir(_ id: String) throws -> URL {
        let home = ProcessInfo.processInfo.environment["HOME"]
            .map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser
        let dir = home.appendingPathComponent(".cache/posttrainllm/models")
            .appendingPathComponent(id)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    // MARK: - subprocess plumbing

    struct Result {
        let status: Int32
        let stdout: String
        let stderr: String
        let timedOut: Bool
    }

    /// Run a subprocess with captured output and a hard timeout. The
    /// process group is killed on timeout so nothing outlives model-run.
    static func execCapture(_ argv: [String], timeout: TimeInterval) -> Result {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = argv
        let out = Pipe(), err = Pipe()
        p.standardOutput = out; p.standardError = err
        do { try p.run() } catch {
            return Result(status: -1, stdout: "",
                          stderr: "spawn failed: \(error)", timedOut: false)
        }
        // Drain pipes on background threads — a child that fills the
        // 64 KB pipe buffer would deadlock against waitUntilExit
        // (ollama's pull progress alone exceeds it).
        final class Box { var d = Data() }
        let ob = Box(), eb = Box()
        let g = DispatchGroup()
        g.enter(); DispatchQueue.global().async {
            ob.d = out.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        g.enter(); DispatchQueue.global().async {
            eb.d = err.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        // Polled watchdog — exits with the process, kills it at timeout.
        var timedOut = false
        let deadline = Date().addingTimeInterval(timeout)
        while p.isRunning {
            if Date() > deadline {
                timedOut = true
                kill(p.processIdentifier, SIGKILL)
                break
            }
            Thread.sleep(forTimeInterval: 0.2)
        }
        p.waitUntilExit()
        g.wait()
        return Result(status: p.terminationStatus,
                      stdout: String(data: ob.d, encoding: .utf8) ?? "",
                      stderr: String(data: eb.d, encoding: .utf8) ?? "",
                      timedOut: timedOut)
    }

    private static func printOutcome(runner: String, result: Result) -> Bool {
        print("── \(runner) output ──────────────────────────────")
        let out = result.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
        let err = result.stderr.trimmingCharacters(in: .whitespacesAndNewlines)
        if !out.isEmpty { print(out) }
        if !err.isEmpty && result.status != 0 { print(err) }
        print("─────────────────────────────────────────────────")
        if result.timedOut {
            print("✗ \(runner) timed out (download or load exceeded the limit)")
            return false
        } else if result.status == 0 {
            return true
        } else {
            print("✗ \(runner) exited \(result.status) — the real error is above")
            return false
        }
    }

    private static func reportSuccess(runner: String, hint: String) -> Never {
        print("✓ ran on \(runner) — verified, not predicted")
        print("keep chatting: \(hint)")
        exit(0)
    }

    private static func usage(_ code: Int32) -> Never {
        fputs("""
        usage: posttrainllm model-run <hf-url> [--chat] [--prompt "…"]
                     [--max-tokens N] [--runtime auto|native|mlx-lm|ollama]
          check → pick installed runtime → download → run → verify
        """, stderr)
        exit(code)
    }
}
