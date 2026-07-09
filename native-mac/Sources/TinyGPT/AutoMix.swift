import Foundation
import TinyGPTModel

/// `posttrainllm automix` (B21) — micro-AutoMixer for specialist pretrain ratios.
///
/// Replaces "hand-wave a 50/30/20 split" with a small ratio search: sample
/// candidate mixes (Dirichlet), score each with a short proxy run, fit a
/// quadratic surrogate, and propose the next mix by predicted improvement
/// until gains fall below a threshold. Scaled down from Poolside's Laguna
/// recipe to one Mac. The sampler + surrogate live in TinyGPTModel
/// (`MixSampler`, `SurrogateFit`); this file is the orchestration.
///
/// `--dry-run` swaps the train+eval proxy for a deterministic synthetic
/// scorer with a known optimum, so the whole search loop (sample → score →
/// fit → propose → stop) is exercisable in CI without a GPU.
enum AutoMix {
    struct Corpus { let name: String; let path: String }

    static func run(args: [String]) {
        var corpora: [Corpus] = []
        var tasks: [String] = []
        var proxyRuns = 6
        var proxySteps = 2000
        var outPath = "automix-report.jsonl"
        var seed: UInt64 = 42
        var dryRun = false
        var eiThreshold = 0.0
        var maxIters = 4

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--corpus":
                let kv = args[i+1].split(separator: "=", maxSplits: 1)
                guard kv.count == 2 else { fputs("--corpus expects name=path\n", stderr); exit(2) }
                corpora.append(Corpus(name: String(kv[0]), path: String(kv[1]))); i += 2
            case "--task":         tasks.append(args[i+1]); i += 2
            case "--proxy-runs":   proxyRuns = max(2, Int(args[i+1]) ?? proxyRuns); i += 2
            case "--proxy-steps":  proxySteps = max(1, Int(args[i+1]) ?? proxySteps); i += 2
            case "--out":          outPath = args[i+1]; i += 2
            case "--seed":         seed = UInt64(args[i+1]) ?? seed; i += 2
            case "--dry-run":      dryRun = true; i += 1
            case "--ei-threshold": eiThreshold = Double(args[i+1]) ?? eiThreshold; i += 2
            case "--max-iters":    maxIters = max(0, Int(args[i+1]) ?? maxIters); i += 2
            case "-h", "--help":   exitUsage(0)
            default:
                fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }
        guard corpora.count >= 2 else {
            fputs("automix needs >= 2 --corpus name=path entries\n", stderr); exitUsage()
        }
        let k = corpora.count
        let names = corpora.map(\.name)

        // Report sink.
        let outURL = URL(fileURLWithPath: outPath)
        try? FileManager.default.removeItem(at: outURL)
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        let reportFH = try? FileHandle(forWritingTo: outURL)
        defer { try? reportFH?.close() }

        var mixes: [[Float]] = []
        var scores: [Float] = []

        func record(iter: Int, source: String, mix: [Float], score: Float, predicted: Double?) {
            let ratio = Dictionary(uniqueKeysWithValues: zip(names, mix.map { Double($0) }))
            var row: [String: Any] = ["iter": iter, "source": source, "score": Double(score), "ratio": ratio]
            if let p = predicted { row["predicted"] = p }
            if let d = try? JSONSerialization.data(withJSONObject: row),
               let line = String(data: d, encoding: .utf8) {
                reportFH?.write(Data((line + "\n").utf8))
            }
            let pretty = zip(names, mix).map { "\($0)=\(String(format: "%.2f", $1))" }.joined(separator: " ")
            print(String(format: "[automix] %@ #%d  score=%.4f  %@", source, iter, score, pretty))
        }

        func scoreMix(_ mix: [Float]) -> Float {
            dryRun ? syntheticScore(mix) : realScore(mix, corpora: corpora, steps: proxySteps, seed: seed)
        }

        // Phase 1 — initial Dirichlet mixes (incl. uniform anchor).
        print("automix: \(k) corpora \(names), \(proxyRuns) initial proxy runs, dry-run=\(dryRun)")
        for (n, mix) in MixSampler.sampleMixes(k: k, count: proxyRuns, seed: seed).enumerated() {
            let s = scoreMix(mix); mixes.append(mix); scores.append(s)
            record(iter: n, source: "sample", mix: mix, score: s, predicted: nil)
        }

        // Phase 2 — surrogate-guided proposals.
        for iter in 0..<maxIters {
            let surrogate = QuadraticSurrogate.fit(mixes: mixes, scores: scores)
            let cands = MixSampler.sampleMixes(k: k, count: 256, seed: seed &+ UInt64(iter) &+ 1,
                                               includeUniform: false)
            let best = scores.max() ?? 0
            let prop = SurrogateProposer.propose(surrogate: surrogate, candidates: cands, bestObserved: best)
            if prop.improvement < eiThreshold {
                print(String(format: "automix: stop — predicted improvement %.4g < threshold %.4g",
                             prop.improvement, eiThreshold))
                break
            }
            let s = scoreMix(prop.mix); mixes.append(prop.mix); scores.append(s)
            record(iter: proxyRuns + iter, source: "propose", mix: prop.mix, score: s, predicted: prop.predicted)
        }

        // Phase 3 — recommendation.
        let bestIdx = scores.indices.max(by: { scores[$0] < scores[$1] })!
        let bestMix = mixes[bestIdx]
        let rec: [String: Any] = [
            "best_score": Double(scores[bestIdx]),
            "ratio": Dictionary(uniqueKeysWithValues: zip(names, bestMix.map { Double($0) })),
            "proxy_steps": proxySteps,
            "runs": scores.count,
            "dry_run": dryRun,
        ]
        let recURL = outURL.deletingLastPathComponent()
            .appendingPathComponent("automix-recommendation.json")
        if let d = try? JSONSerialization.data(withJSONObject: rec, options: [.prettyPrinted, .sortedKeys]) {
            try? d.write(to: recURL)
        }
        let pretty = zip(names, bestMix).map { "\($0)=\(String(format: "%.3f", $1))" }.joined(separator: " ")
        print("\nautomix recommendation: \(pretty)  (score \(String(format: "%.4f", scores[bestIdx])))")
        print("wrote \(outPath) + \(recURL.lastPathComponent)")
    }

    // MARK: scoring

    /// Deterministic concave scorer with a known optimum (geometric-decaying
    /// target over corpora). Lets the search loop be tested without training.
    static func syntheticScore(_ mix: [Float]) -> Float {
        let target = syntheticTarget(k: mix.count)
        return -zip(mix, target).reduce(Float(0)) { $0 + ($1.0 - $1.1) * ($1.0 - $1.1) }
    }

    static func syntheticTarget(k: Int) -> [Float] {
        let w = (0..<k).map { Float(pow(0.5, Double($0))) }
        let s = w.reduce(0, +)
        return w.map { $0 / s }
    }

    /// Real proxy score: build a mixed corpus at this ratio, run a short
    /// `posttrainllm train`, and use the negated final loss as the capability
    /// proxy. (Task-eval scoring — BFCL/GSM8K via run-lm-eval — is the V2
    /// extension noted in the recipe.) Needs a GPU; covered structurally only.
    static func realScore(_ mix: [Float], corpora: [Corpus], steps: Int, seed: UInt64) -> Float {
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("automix-\(UInt64.random(in: 0..<UInt64.max)).txt")
        guard buildMixedCorpus(mix: mix, corpora: corpora, to: tmp) else { return -Float.greatestFiniteMagnitude }
        defer { try? FileManager.default.removeItem(at: tmp) }
        let logURL = tmp.appendingPathExtension("jsonl")
        let outCkpt = tmp.appendingPathExtension("tinygpt")
        let selfBin = CommandLine.arguments.first.map { URL(fileURLWithPath: $0) } ?? Bundle.main.executableURL
        guard let bin = selfBin else { return -Float.greatestFiniteMagnitude }
        let p = Process()
        p.executableURL = bin
        p.arguments = ["train", "--preset", "tiny", "--corpus", tmp.path,
                       "--steps", "\(steps)", "--seed", "\(seed)",
                       "--log-jsonl", logURL.path, "--out", outCkpt.path, "--no-spike-detect"]
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run(); p.waitUntilExit() } catch { return -Float.greatestFiniteMagnitude }
        defer { try? FileManager.default.removeItem(at: logURL); try? FileManager.default.removeItem(at: outCkpt) }
        // last loss from the training log
        guard let log = try? String(contentsOf: logURL, encoding: .utf8) else { return -Float.greatestFiniteMagnitude }
        var last: Float? = nil
        for line in log.split(separator: "\n").reversed() {
            if let d = line.data(using: .utf8),
               let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
               let l = o["loss"] as? Double { last = Float(l); break }
        }
        return last.map { -$0 } ?? -Float.greatestFiniteMagnitude
    }

    /// Concatenate lines from each corpus in proportion to `mix` into one file.
    static func buildMixedCorpus(mix: [Float], corpora: [Corpus], to dest: URL,
                                 targetLines: Int = 4000) -> Bool {
        var out: [String] = []
        for (w, c) in zip(mix, corpora) {
            guard let raw = try? String(contentsOfFile: c.path, encoding: .utf8) else { return false }
            let lines = raw.split(separator: "\n").map(String.init)
            guard !lines.isEmpty else { continue }
            let take = max(1, Int((Float(targetLines) * w).rounded()))
            for j in 0..<take { out.append(lines[j % lines.count]) }
        }
        out.shuffle()
        return (try? out.joined(separator: "\n").write(to: dest, atomically: true, encoding: .utf8)) != nil
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm automix --corpus name=path --corpus name=path [...] [options]

        Search data-mix ratios across corpora: sample mixes (Dirichlet), score
        each with a short proxy train run, fit a quadratic surrogate, propose
        the next mix by predicted improvement until gains drop below a threshold.

        --corpus name=path     a corpus to ratio (repeat; >= 2 required)
        --task NAME            eval task for scoring (repeat; reserved for V2 —
                               V1 scores by negated proxy-train loss)
        --proxy-runs N         initial Dirichlet samples (default 6)
        --proxy-steps S        train steps per proxy run (default 2000)
        --max-iters N          surrogate-guided proposal rounds (default 4)
        --ei-threshold F       stop when predicted improvement < F (default 0)
        --seed N               deterministic search (default 42)
        --dry-run              use a synthetic scorer (known optimum) — no GPU;
                               exercises the full search loop for CI
        --out path.jsonl       per-run report (default automix-report.jsonl);
                               automix-recommendation.json is written alongside
        """)
        exit(code)
    }
}
