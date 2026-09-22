import Foundation
import TinyGPTCheck
import TinyGPTData

/// `posttrainllm model-run <url>` — check → pick installed runtime →
/// download → run → verify. Closes the loop that `model-check` opens:
/// the checker's verdict is a prediction; model-run executes the best
/// *installed* runtime and reports measured success or failure.
///
///   GGUF repo              → ollama (`ollama run hf.co/<id>`), then
///                            lms (`get` + `load` + `chat -p`), then
///                            llama-cli (`-hf <id>:<quant>`)
///   safetensors, checked OK→ native posttrainllm (download → hf-load sample)
///   safetensors, other     → mlx-swift (`posttrainllm-mlxrun` sibling —
///                            Apple's MLX-Swift-LM impls, no python dep),
///                            then mlx-lm (`python3 -m mlx_lm generate`)
///   gated without HF_TOKEN → named blocker, nothing attempted
///
/// Every runner is a bounded subprocess (timeout, captured output, killed
/// on expiry). Failures surface the runtime's real error and fall through
/// to the next candidate — a runtime that probes as installed can still
/// be broken. `--chat` hands the terminal to the runtime's interactive
/// session instead of the bounded sample. Daemons spawned by model-run
/// are terminated before exit; nothing is left running.
public enum ModelRunner {

    public struct Options: Sendable {
        public var chat = false
        public var maxTokens = 32
        public var prompt = "Say hello in one sentence."
        public var forcedRunner: Runner? = nil
        public init() {}
    }

    private struct RunOutcome {
        let succeeded: Bool
        let result: Subprocess.Result
        let failureStage: ModelCheckReport.ExecutionStageName
        let promptTokens: Int?
        let generatedTokens: Int?

        init(
            succeeded: Bool, result: Subprocess.Result,
            failureStage: ModelCheckReport.ExecutionStageName = .load,
            promptTokens: Int? = nil, generatedTokens: Int? = nil
        ) {
            self.succeeded = succeeded
            self.result = result
            self.failureStage = failureStage
            self.promptTokens = promptTokens
            self.generatedTokens = generatedTokens
        }

    }

    /// Exit-code contract: 0 ran, 2 bad input, 3 blocked (gated / no
    /// runnable path), 6 every candidate failed.
    public static func run(input: String, options: Options) -> Int32 {
        // 1. Check — reuse the full machinery, verdicts and all.
        fputs("… checking \(input)\n", stderr)
        let report: ModelCheckReport
        do {
            report = try ModelCheckService.check(input: input) { stage in
                fputs("… \(stage.rawValue)\n", stderr)
            }
        } catch let e as ModelCheckService.CheckError {
            fputs("model-run: \(e)\n", stderr)
            return 2
        } catch {
            fputs("model-run: check failed: \(error)\n", stderr)
            return 1
        }
        emit("verdict: \(report.verdict.rawValue) — \(report.verdictSummary)\n")

        // 2. Access gate first — nothing runs gated without a token.
        if report.model.gated,
           (ProcessInfo.processInfo.environment["HF_TOKEN"] ?? "").isEmpty {
            persistReceipt(
                report: report, status: .blocked, runtime: nil,
                failureStage: .download, attempts: [])
            fputs("""
            blocked: \(report.model.id) is gated — accept the license at
              https://huggingface.co/\(report.model.id)
            and set HF_TOKEN, then re-run.

            """, stderr)
            return 3
        }

        // 3. Ordered candidates. Failure falls through to the next —
        // detected ≠ working (a partial install probes fine and then
        // dies on launch; the real stderr is the evidence).
        let plans = RunnerPlanner.plans(for: report, forced: options.forcedRunner)
        guard !plans.isEmpty else {
            persistReceipt(
                report: report, status: .blocked, runtime: nil,
                failureStage: .validate, attempts: [])
            fputs(RunnerPlanner.blocker(for: report, forced: options.forcedRunner) + "\n", stderr)
            return 3
        }
        var attempts: [ModelCheckReport.VerificationAttempt] = []
        for (index, plan) in plans.enumerated() {
            if index > 0 { fputs("… falling back to \(plan.runner.rawValue)\n", stderr) }
            emit("runner: \(plan.runner.rawValue) — \(plan.why)")
            let outcome: RunOutcome
            switch plan.runner {
            case .native:
                outcome = runNative(report: report, options: options)
            case .mlxSwift:
                outcome = runMlxSwift(
                    id: report.model.id, revision: artifactRevision(report),
                    options: options)
            case .mlxLm:
                outcome = runMlxLm(id: report.model.id, options: options)
            case .ollama:
                outcome = runOllama(report: report, options: options)
            case .lms:
                outcome = runLms(report: report, options: options)
            case .llamaCpp:
                outcome = runLlamaCpp(report: report, options: options)
            }
            attempts.append(receiptAttempt(
                outcome: outcome, runner: plan.runner, report: report,
                requestedTokens: options.maxTokens))
            if outcome.succeeded {
                persistReceipt(
                    report: report, status: .verified,
                    runtime: plan.runner.rawValue, failureStage: nil,
                    attempts: attempts)
                emit("\n✓ ran on \(plan.runner.rawValue) — verified, not predicted")
                emit("keep chatting: \(chatHint(plan.runner, report: report))")
                return 0
            }
            fputs("  \(plan.runner.rawValue) failed — trying next runner if any\n", stderr)
        }
        persistReceipt(
            report: report, status: .failed,
            runtime: attempts.last?.runtime,
            failureStage: deepestFailureStage(attempts),
            attempts: attempts)
        fputs("all runnable paths failed — the real errors are above.\n", stderr)
        return 6
    }

    private static func receiptAttempt(
        outcome: RunOutcome, runner: Runner, report: ModelCheckReport,
        requestedTokens: Int
    ) -> ModelCheckReport.VerificationAttempt {
        return ModelCheckReport.VerificationAttempt(
            runtime: runner.rawValue,
            runtimeVersion: runtimeVersion(runner, report: report),
            status: outcome.succeeded ? .verified : .failed,
            failureStage: outcome.succeeded ? nil : outcome.failureStage,
            stderr: outcome.succeeded ? nil : stderrWithoutStats(outcome.result.stderr),
            measurement: ModelCheckReport.SampleMeasurement(
                durationMS: outcome.result.durationMS,
                requestedTokens: requestedTokens,
                promptTokens: outcome.promptTokens,
                generatedTokens: outcome.generatedTokens,
                outputCharacters: outcome.result.stdout.count))
    }

    // MARK: - native (posttrainllm hf-load)

    /// Download the loadable file set to the posttrainllm cache, then
    /// smoke it with `hf-load --sample` as a captured subprocess — a
    /// load crash is a bounded, reported result rather than a kill of
    /// the model-run process.
    private static func runNative(report: ModelCheckReport,
                                  options: Options) -> RunOutcome {
        let id = report.model.id
        do {
            let dir = try cacheDir(for: id, revision: artifactRevision(report))
            try downloadLoadSet(report: report, into: dir)
            let selfPath = CommandLine.arguments[0]
            if options.chat {
                // The native interactive path is the OpenAI-compatible
                // endpoint — it owns the terminal until Ctrl-C.
                emit("starting native server — Ctrl-C to stop")
                return attachedOutcome(
                    status: Subprocess.attached([selfPath, "serve", dir.path]))
            }
            let r = Subprocess.capture(
                [selfPath, "hf-load", dir.path, "--sample",
                 "--prompt", options.prompt,
                 "--tokens", String(options.maxTokens)],
                timeout: 600)
            return capturedOutcome(runner: "native", result: r)
        } catch {
            return failedOutcome(
                "native run failed during download: \(error)", stage: .download)
        }
    }

    /// Files hf-load needs: config + tokenizer + every safetensors
    /// shard. Filtered against the live manifest — e.g. Qwen3 ships
    /// tokenizer.json but no tokenizer.model, and a 404 on a guessed
    /// name must not kill the download.
    private static func downloadLoadSet(report: ModelCheckReport,
                                        into dir: URL) throws {
        let id = report.model.id
        let revision = artifactRevision(report)
        let info = try HubModelClient.info(id: id, revision: revision)
        let names = Set(info.siblings.map(\.name))
        var wanted = ["config.json", "tokenizer.json", "tokenizer.model",
                      "tokenizer_config.json", "generation_config.json",
                      "special_tokens_map.json", "vocab.json", "merges.txt",
                      "model.safetensors.index.json"].filter { names.contains($0) }
        wanted += names.filter { $0.hasSuffix(".safetensors") }
        var seen = Set<String>()
        let files = wanted.filter { seen.insert($0).inserted }
        fputs("… downloading \(files.count) files → \(dir.path)\n", stderr)
        for file in files {
            let dest = dir.appendingPathComponent(file)
            let expectedSize = info.sibling(named: file)?.size
            if cachedFileMatches(dest, expectedSize: expectedSize) {
                fputs("  \(file) (cached)\n", stderr)
                continue
            }
            let url = "https://huggingface.co/\(id)/resolve/\(revision)/\(file)"
            try downloadArtifact(url: url, to: dest, expectedSize: expectedSize, label: file)
        }
    }

    private static func downloadArtifact(
        url: String, to destination: URL, expectedSize: Int64?, label: String
    ) throws {
        try FileManager.default.createDirectory(
            at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
        fputs("  \(label)…\n", stderr)
        try HFDatasets.streamDownload(urlString: url, to: destination) { done, total in
            if total > 0 { fputs("\r    \(done * 100 / total)%", stderr) }
        }
        guard expectedSize == nil || cachedFileMatches(destination, expectedSize: expectedSize) else {
            throw invalidDownload(label)
        }
        fputs("\n", stderr)
    }

    private static func invalidDownload(_ label: String) -> NSError {
        NSError(domain: "PostTrainLLM.ModelRunner", code: 1,
                userInfo: [NSLocalizedDescriptionKey:
                    "downloaded \(label) does not match the Hub manifest size"])
    }

    /// The Hub API resolves mutable refs (`main`, branches, tags) to a commit.
    /// Downloads and cache directories must use that immutable commit so the
    /// bytes executed are the same snapshot the checker inspected.
    static func artifactRevision(_ report: ModelCheckReport) -> String {
        report.model.resolvedRevision ?? report.model.revision
    }

    /// Existing files are reusable only when the Hub manifest supplied a size
    /// and the on-disk file matches it. Unknown-size entries are re-downloaded
    /// atomically instead of trusting arbitrary pre-existing bytes.
    static func cachedFileMatches(_ file: URL, expectedSize: Int64?) -> Bool {
        guard let expectedSize, expectedSize >= 0,
              let attributes = try? FileManager.default.attributesOfItem(atPath: file.path),
              let actual = (attributes[.size] as? NSNumber)?.int64Value else {
            return false
        }
        return actual == expectedSize
    }

    private static func cacheDir(for id: String, revision: String = "main") throws -> URL {
        let home = ProcessInfo.processInfo.environment["HOME"]
            .map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser
        let revisionKey = Data(revision.utf8).base64EncodedString()
            .replacingOccurrences(of: "/", with: "_")
        let dir = home.appendingPathComponent(".cache/posttrainllm/models")
            .appendingPathComponent(id).appendingPathComponent(revisionKey)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    // MARK: - ollama

    /// The local ollama model name when the Modelfile fallback created
    /// one — the chat hint points here instead of the hf.co ref that
    /// failed. Set only by runOllama; read only by chatHint.
    private static var ollamaLocalModel: String? = nil

    /// `ollama run hf.co/<id>[:quant] "<prompt>"` — one-shot mode prints
    /// the generation and exits; the GGUF pull happens inside the same
    /// call on first use. When the checker picked a variant, its quant
    /// tag pins the pull; a rejected tag retries the bare ref once, then
    /// a direct-download + `ollama create` Modelfile fallback runs.
    private static func runOllama(report: ModelCheckReport,
                                  options: Options) -> RunOutcome {
        let base = "hf.co/\(report.model.id)"
        let tagged = ggufQuantTag(report: report).map { "\(base):\($0)" } ?? base
        ollamaLocalModel = nil

        // Installed ≠ serving. Start `ollama serve` ourselves when the
        // daemon doesn't answer — and terminate only the one we spawned.
        var spawned: Process? = nil
        if !ollamaDaemonUp() {
            spawned = Subprocess.daemon(["ollama", "serve"])
            if spawned == nil || !waitForOllama(spawned!) {
                spawned?.terminate()
                return failedOutcome("ollama daemon did not come up", stage: .load)
            }
        }
        defer { spawned?.terminate() }

        if options.chat {
            return attachedOutcome(
                status: Subprocess.attached(["ollama", "run", tagged]))
        }
        var r = Subprocess.capture(["ollama", "run", tagged, options.prompt],
                                   timeout: 1800)  // first run may pull GBs
        if r.status != 0 && tagged != base {
            fputs("  tagged ref failed — retrying bare \(base)\n", stderr)
            r = Subprocess.capture(["ollama", "run", base, options.prompt],
                                   timeout: 1800)
        }
        // ollama's hf.co pull chokes on HF's Xet CDN cross-host redirects.
        // Robust fallback: download the selected GGUF ourselves (our
        // downloader follows redirects), `ollama create` from a
        // Modelfile, then run the local model.
        if r.status != 0,
           let variant = report.model.selectedVariant,
           variant.lowercased().hasSuffix(".gguf") {
            fputs("  ollama hf.co pull failed — downloading the GGUF directly\n", stderr)
            if let local = try? downloadGGUFVariant(report: report, variant: variant) {
                let name = "posttrainllm-"
                    + variant.replacingOccurrences(of: ".gguf", with: "")
                        .lowercased()
                let modelfile = local.deletingLastPathComponent()
                    .appendingPathComponent("Modelfile")
                try? "FROM \"\(local.path)\"\n".write(
                    to: modelfile, atomically: true, encoding: .utf8)
                let c = Subprocess.capture(
                    ["ollama", "create", name, "-f", modelfile.path],
                    timeout: 300)
                if c.status == 0 {
                    ollamaLocalModel = name
                    r = Subprocess.capture(["ollama", "run", name, options.prompt],
                                           timeout: 600)
                }
            }
        }
        return capturedOutcome(runner: "ollama", result: r)
    }

    /// Download the checker's selected GGUF variant into the model cache
    /// — the fallback for runtimes whose own Hub pull fails.
    private static func downloadGGUFVariant(report: ModelCheckReport,
                                            variant: String) throws -> URL {
        let revision = artifactRevision(report)
        let dir = try cacheDir(
            for: report.model.id, revision: revision)
        let dest = dir.appendingPathComponent(variant)
        let info = try HubModelClient.info(id: report.model.id, revision: revision)
        let expectedSize = info.sibling(named: variant)?.size
        if !cachedFileMatches(dest, expectedSize: expectedSize) {
            let url = "https://huggingface.co/\(report.model.id)/resolve/\(revision)/\(variant)"
            try downloadArtifact(
                url: url, to: dest, expectedSize: expectedSize, label: variant)
        }
        return dest
    }

    /// A quant tag (`Q4_K_M`, `Q8_0`, `F16`, …) recovered from the
    /// checker's selected GGUF filename — understood by both
    /// `ollama run hf.co/id:<tag>` and `llama-cli -hf id:<tag>`.
    /// Filenames conventionally end `…-<QUANT>.gguf`; take the last
    /// `-`-separated component matching a known quant pattern. None →
    /// nil, and callers use the bare ref so the runtime picks.
    static func ggufQuantTag(report: ModelCheckReport) -> String? {
        guard let variant = report.model.selectedVariant,
              variant.lowercased().hasSuffix(".gguf") else { return nil }
        let stem = String(variant.dropLast(".gguf".count))
        let pattern = #"^(IQ\d_[A-Z0-9]+|Q\d(_[A-Z0-9]+)*|F16|F32|BF16)$"#
        for part in stem.split(separator: "-").reversed() {
            if part.range(of: pattern, options: [.regularExpression,
                                                 .caseInsensitive]) != nil {
                return String(part).uppercased()
            }
        }
        return nil
    }

    private static func ollamaDaemonUp() -> Bool {
        Subprocess.capture(["ollama", "list"], timeout: 5).status == 0
    }

    /// Poll `ollama list` until a spawned `serve` answers (≤10 s).
    private static func waitForOllama(_ daemon: Process) -> Bool {
        for _ in 0..<50 where daemon.isRunning {
            if ollamaDaemonUp() { return true }
            Thread.sleep(forTimeInterval: 0.2)
        }
        return false
    }

    // MARK: - mlx-swift (posttrainllm-mlxrun sibling)

    /// MLX-Swift-LM via the `posttrainllm-mlxrun` sibling executable —
    /// Apple's maintained HF model impls (LLM + VLM + embedders) running
    /// in their own process, so a load failure is a captured result, not
    /// a crash here. Honors HF_TOKEN via the HubClient env auto-detect.
    private static func runMlxSwift(
        id: String, revision: String, options: Options
    ) -> RunOutcome {
        guard let bin = mlxrunBinary() else {
            return failedOutcome(
                "posttrainllm-mlxrun not built — run `swift build --product posttrainllm-mlxrun`",
                stage: .validate)
        }
        if options.chat {
            return attachedOutcome(status: Subprocess.attached(
                [bin, id, "--revision", revision, "--chat"]))
        }
        let r = Subprocess.capture(
            [bin, id, "--revision", revision, "--prompt", options.prompt,
             "--max-tokens", String(options.maxTokens)],
            timeout: 1800)
        let stats = sampleStats(from: r.stderr)
        return capturedOutcome(
            runner: "mlx-swift", result: r,
            promptTokens: stats?.promptTokens,
            generatedTokens: stats?.generatedTokens)
    }

    /// Locate the sibling `posttrainllm-mlxrun` next to this binary,
    /// else on PATH.
    static func mlxrunBinary() -> String? {
        let dir = (CommandLine.arguments[0] as NSString).deletingLastPathComponent
        let sibling = dir + "/posttrainllm-mlxrun"
        if FileManager.default.isExecutableFile(atPath: sibling) { return sibling }
        let which = Subprocess.capture(["which", "posttrainllm-mlxrun"], timeout: 5)
        let path = which.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
        return which.status == 0 && !path.isEmpty ? path : nil
    }

    // MARK: - mlx-lm

    /// `python3 -m mlx_lm generate` — auto-downloads to the HF cache and
    /// covers MoE/VLM/quantized archs the native loader doesn't.
    private static func runMlxLm(id: String, options: Options) -> RunOutcome {
        if options.chat {
            return attachedOutcome(status: Subprocess.attached(
                ["python3", "-m", "mlx_lm", "chat", "--model", id]))
        }
        let r = Subprocess.capture(
            ["python3", "-m", "mlx_lm", "generate",
             "--model", id, "--prompt", options.prompt,
             "--max-tokens", String(options.maxTokens)],
            timeout: 1800)
        return capturedOutcome(runner: "mlx-lm", result: r)
    }

    // MARK: - lms (LM Studio)

    /// `lms get <hf-url> --gguf -y` downloads into LM Studio's store;
    /// `lms chat <key> -p <prompt>` is the bounded one-shot (prints the
    /// response and quits). The model key isn't the HF id — resolve it
    /// from `lms ls` after the download. `lms unload` frees the loaded
    /// weights afterwards so nothing is held resident.
    private static func runLms(report: ModelCheckReport,
                               options: Options) -> RunOutcome {
        let id = report.model.id
        // A selected GGUF variant resolves to its blob URL; otherwise
        // the repo URL lets `lms get -y` pick for this hardware.
        var source = "https://huggingface.co/\(id)"
        if let v = report.model.selectedVariant, v.hasSuffix(".gguf") {
            source = "\(source)/blob/\(artifactRevision(report))/\(v)"
        }
        var r = Subprocess.capture(["lms", "get", source, "--gguf", "-y"],
                                   timeout: 1800)
        if r.status != 0, report.model.filePath == nil,
           source != "https://huggingface.co/\(id)" {
            fputs("  variant download rejected — retrying repo URL\n", stderr)
            source = "https://huggingface.co/\(id)"
            r = Subprocess.capture(["lms", "get", source, "--gguf", "-y"],
                                   timeout: 1800)
        }
        let download = capturedOutcome(
            runner: "lms get", result: r, failureStage: .download)
        guard download.succeeded else { return download }

        guard let key = lmsModelKey(report: report, getOutput: r.stdout) else {
            return failedOutcome(
                "downloaded but could not resolve the lms model key — try `lms ls`",
                stage: .load)
        }
        // `lms chat` requires a *loaded* model — get only downloads.
        // --ttl bounds residency; the explicit unload afterwards is the
        // real cleanup so nothing stays resident.
        let load = Subprocess.capture(["lms", "load", key, "--ttl", "300", "-y"],
                                      timeout: 600)
        let loaded = capturedOutcome(
            runner: "lms load", result: load, failureStage: .load)
        guard loaded.succeeded else { return loaded }
        defer { _ = Subprocess.capture(["lms", "unload", key], timeout: 30) }

        if options.chat {
            return attachedOutcome(
                status: Subprocess.attached(["lms", "chat", key]))
        }
        let sample = Subprocess.capture(
            ["lms", "chat", key, "-p", options.prompt, "-y"],
            timeout: 600)
        return capturedOutcome(
            runner: "lms", result: sample, failureStage: .smokeTest)
    }

    /// Resolve the LM Studio model key for a just-downloaded repo.
    /// `lms ls --json` is searched for an entry mentioning the repo name
    /// or the selected filename; the `lms get` output and the plain-text
    /// table are fallbacks. Returns nil when nothing matches — guessing
    /// a key would produce a misleading error.
    static func lmsModelKey(report: ModelCheckReport,
                            getOutput: String) -> String? {
        let id = report.model.id.lowercased()
        let repo = id.split(separator: "/").last.map { String($0) } ?? id
        let variant = report.model.selectedVariant?.lowercased()

        // `lms get` prints the identifier it fetched — prefer that.
        for line in getOutput.split(separator: "\n").map({ String($0) }) {
            if let m = line.range(of: #"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"#,
                                  options: .regularExpression),
               lmsTargetMatches(String(line[m]), id: id, repo: repo, variant: variant) {
                return String(line[m])
            }
        }

        // `lms ls --json` — schema isn't published; scan every entry's
        // serialized form for a mention, then take its key-ish field.
        let ls = Subprocess.capture(["lms", "ls", "--json"], timeout: 30)
        if ls.status == 0,
           let parsed = try? JSONSerialization.jsonObject(
               with: Data(ls.stdout.utf8)) as? [[String: Any]] {
            for entry in parsed {
                guard let blob = try? JSONSerialization.data(withJSONObject: entry),
                      let text = String(data: blob, encoding: .utf8),
                      lmsTargetMatches(text, id: id, repo: repo, variant: variant) else { continue }
                for field in ["modelKey", "key", "path", "name", "id"] {
                    if let v = entry[field] as? String { return v }
                }
            }
        }

        // Last resort: first column of a matching `lms ls` table row.
        let plain = Subprocess.capture(["lms", "ls"], timeout: 30)
        for line in plain.stdout.split(separator: "\n").map({ String($0) })
        where lmsTargetMatches(line, id: id, repo: repo, variant: variant) {
            if let key = line.split(separator: " ",
                                    omittingEmptySubsequences: true).first {
                return String(key)
            }
        }
        return nil
    }

    private static func lmsTargetMatches(
        _ candidate: String, id: String, repo: String, variant: String?
    ) -> Bool {
        let text = candidate.lowercased()
        return text.contains(id) || text.contains(repo)
            || (variant.map { text.contains($0) } ?? false)
    }

    // MARK: - llama.cpp

    /// `llama-cli -hf <id>:<quant>` — llama.cpp's own Hub download +
    /// generate in one binary; `--single-turn` makes it exit after the
    /// sample, `-n` bounds it. The last-resort GGUF runner when ollama's
    /// downloader and LM Studio's runtime plugin both fall short.
    private static func runLlamaCpp(report: ModelCheckReport,
                                    options: Options) -> RunOutcome {
        let base = report.model.id
        let tagged = ggufQuantTag(report: report)
            .map { "\(base):\($0)" } ?? base
        if options.chat {
            // No flag needed — llama-cli is conversational on a tty.
            return attachedOutcome(
                status: Subprocess.attached(["llama-cli", "-hf", tagged]))
        }
        var r = Subprocess.capture(
            ["llama-cli", "-hf", tagged,
             "-p", options.prompt, "-n", String(options.maxTokens),
             "--single-turn", "--no-warmup"],
            timeout: 1800)
        if r.status != 0 && tagged != base {
            fputs("  tagged ref failed — retrying bare \(base)\n", stderr)
            r = Subprocess.capture(
                ["llama-cli", "-hf", base,
                 "-p", options.prompt, "-n", String(options.maxTokens),
                 "--single-turn", "--no-warmup"],
                timeout: 1800)
        }
        return capturedOutcome(runner: "llama-cli", result: r)
    }

    // MARK: - reporting

    private struct SampleStats: Decodable {
        let promptTokens: Int?
        let generatedTokens: Int?

        enum CodingKeys: String, CodingKey {
            case promptTokens = "prompt_tokens"
            case generatedTokens = "generated_tokens"
        }
    }

    private static let sampleStatsPrefix = "__POSTTRAINLLM_SAMPLE_STATS__"

    private static func sampleStats(from stderr: String) -> SampleStats? {
        for line in stderr.split(separator: "\n").reversed() {
            let value = String(line)
            guard value.hasPrefix(sampleStatsPrefix) else { continue }
            return try? JSONDecoder().decode(
                SampleStats.self,
                from: Data(value.dropFirst(sampleStatsPrefix.count).utf8))
        }
        return nil
    }

    private static func stderrWithoutStats(_ stderr: String) -> String {
        stderr.split(separator: "\n", omittingEmptySubsequences: false)
            .filter { !String($0).hasPrefix(sampleStatsPrefix) }
            .joined(separator: "\n")
    }

    private static func inferredFailureStage(
        _ result: Subprocess.Result
    ) -> ModelCheckReport.ExecutionStageName {
        let text = (result.stderr + "\n" + result.stdout).lowercased()
        if text.contains("401") || text.contains("403") || text.contains("download")
            || text.contains("resolve/") || text.contains("not found") {
            return .download
        }
        if text.contains("warm up") || text.contains("warmup") { return .warmUp }
        if text.contains("generate") || text.contains("sampling") || text.contains("decode") {
            return .smokeTest
        }
        return .load
    }

    private static func capturedOutcome(
        runner: String, result: Subprocess.Result,
        failureStage: ModelCheckReport.ExecutionStageName? = nil,
        promptTokens: Int? = nil, generatedTokens: Int? = nil
    ) -> RunOutcome {
        RunOutcome(
            succeeded: printOutcome(runner: runner, result: result),
            result: result,
            failureStage: failureStage ?? inferredFailureStage(result),
            promptTokens: promptTokens,
            generatedTokens: generatedTokens)
    }

    private static func attachedOutcome(status: Int32) -> RunOutcome {
        RunOutcome(
            succeeded: status == 0,
            result: Subprocess.Result(
                status: status, stdout: "",
                stderr: status == 0 ? "" : "interactive runtime exited \(status)",
                timedOut: false, durationMS: 0),
            failureStage: .smokeTest)
    }

    private static func failedOutcome(
        _ message: String, stage: ModelCheckReport.ExecutionStageName
    ) -> RunOutcome {
        RunOutcome(
            succeeded: false,
            result: Subprocess.Result(
                status: -1, stdout: "", stderr: message,
                timedOut: false, durationMS: 0),
            failureStage: stage)
    }

    private static func runtimeVersion(
        _ runner: Runner, report: ModelCheckReport
    ) -> String? {
        let probeName: String
        switch runner {
        case .native: probeName = "posttrainllm"
        case .ollama: probeName = "ollama"
        case .mlxLm: probeName = "python3 ML stack"
        case .mlxSwift: return "bundled MLX-Swift-LM"
        case .lms: probeName = "lms (LM Studio)"
        case .llamaCpp: probeName = "llama.cpp"
        }
        return report.environment.runtimes.first { $0.name == probeName }?.version
    }

    private static func deepestFailureStage(
        _ attempts: [ModelCheckReport.VerificationAttempt]
    ) -> ModelCheckReport.ExecutionStageName {
        let order = ModelCheckReport.ExecutionStageName.allCases
        return attempts.compactMap(\.failureStage).max { lhs, rhs in
            (order.firstIndex(of: lhs) ?? 0) < (order.firstIndex(of: rhs) ?? 0)
        } ?? .load
    }

    private static func persistReceipt(
        report: ModelCheckReport,
        status: ModelCheckReport.VerificationStatus,
        runtime: String?,
        failureStage: ModelCheckReport.ExecutionStageName?,
        attempts: [ModelCheckReport.VerificationAttempt]
    ) {
        let receipt = ModelCheckReport.VerificationReceipt(
            identity: .init(
                modelID: report.model.id,
                revision: ModelCompatibilityContract.receiptRevision(for: report.model),
                environmentFingerprint: ModelCompatibilityContract.environmentFingerprint(
                    report.environment)),
            verifiedAt: ISO8601DateFormatter().string(from: Date()),
            outcome: .init(
                status: status,
                runtime: runtime,
                runtimeVersion: runtime.flatMap { name in
                    attempts.last { $0.runtime == name }?.runtimeVersion
                },
                failureStage: failureStage),
            attempts: attempts)
        do {
            let url = try ModelVerificationStore().write(receipt)
            emit("receipt: \(url.path)")
        } catch {
            fputs("warning: could not write model verification receipt: \(error)\n", stderr)
        }
    }

    /// The command that continues the session after a verified run.
    static func chatHint(_ runner: Runner, report: ModelCheckReport) -> String {
        switch runner {
        case .ollama:
            // When the Modelfile fallback created a local model, point at
            // it — the hf.co pull is the path that failed.
            if let local = ollamaLocalModel { return "ollama run \(local)" }
            let base = "hf.co/\(report.model.id)"
            return "ollama run \(ggufQuantTag(report: report).map { "\(base):\($0)" } ?? base)"
        case .mlxSwift:
            let target = report.model.revision == "main"
                ? report.model.id
                : "https://huggingface.co/\(report.model.id)/tree/\(report.model.revision)"
            return "\(CommandLine.arguments[0]) model-run \(target) --runtime mlx-swift --chat"
        case .mlxLm:
            return "python3 -m mlx_lm chat --model \(report.model.id)"
        case .lms:
            return "lms chat (resolve the key with `lms ls`)"
        case .llamaCpp:
            let base = report.model.id
            return "llama-cli -hf \(ggufQuantTag(report: report).map { "\(base):\($0)" } ?? base)"
        case .native:
            let revisionKey = Data(artifactRevision(report).utf8).base64EncodedString()
                .replacingOccurrences(of: "/", with: "_")
            let dir = "~/.cache/posttrainllm/models/\(report.model.id)/\(revisionKey)"
            return "\(CommandLine.arguments[0]) serve \(dir)  # OpenAI-compatible endpoint"
        }
    }

    /// Print a runner's captured output and classify the outcome.
    /// Stderr is shown only on failure — ollama in particular streams
    /// pull progress to stderr even on success.
    static func printOutcome(runner: String, result: Subprocess.Result) -> Bool {
        emit("── \(runner) output " + String(repeating: "─", count: 44))
        let out = sanitize(result.stdout)
        let err = sanitize(result.stderr)
        if !out.isEmpty { emit(out) }
        if !err.isEmpty && result.status != 0 { emit(err) }
        emit(String(repeating: "─", count: 60))
        if result.timedOut {
            emit("✗ \(runner) timed out (download or load exceeded the limit)")
            return false
        }
        if result.status != 0 {
            emit("✗ \(runner) exited \(result.status) — the real error is above")
            return false
        }
        return true
    }

    /// print + flush — piped stdout is block-buffered while stderr is
    /// not, and unflushed prints reorder behind stderr diagnostics.
    private static func emit(_ s: String) {
        print(s)
        fflush(stdout)
    }

    /// Make captured subprocess output printable: strip ANSI escapes,
    /// honour carriage-return overwrites (progress bars render as one
    /// logical line — `lms get` alone emits ~2 MB of spinner frames), and
    /// cap at the last 200 lines so a log dump can't bury the verdict.
    static func sanitize(_ raw: String) -> String {
        let noAnsi = raw.replacingOccurrences(
            of: #"\x1B\[[0-9;?]*[A-Za-z]|\x1B\][^\x07]*\x07"#,
            with: "", options: .regularExpression)
        var lines: [String] = []
        for chunk in noAnsi.components(separatedBy: "\n") {
            // \r-separated fragments are overwrite frames — keep the last.
            let line = chunk.components(separatedBy: "\r").last ?? chunk
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if !trimmed.isEmpty { lines.append(trimmed) }
        }
        if lines.count > 200 {
            lines = ["(… \(lines.count - 200) earlier lines omitted …)"]
                + lines.suffix(200)
        }
        return lines.joined(separator: "\n")
    }
}
