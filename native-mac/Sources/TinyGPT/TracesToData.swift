import Foundation
import TinyGPTModel

/// B29 — `tinygpt traces-to-data <atraj-dir> --task <t> --out <jsonl>`.
///
/// Reads every `.atraj` file in `<atraj-dir>` (recursively), extracts
/// per-turn (user → assistant) pairs, applies cheap filters, and emits
/// ChatML-style SFT JSONL ready to feed `tinygpt sft --data`.
///
/// Filters applied in order:
///   1. **Tool-echo drop** — assistant turn that just echoes the prior
///      tool_result is useless training signal; drop.
///   2. **Exact dedup** — identical (prompt, response) pairs collapse
///      to one row.
///   3. **MinHash near-dedup** on the user prompt — Jaccard ≥
///      `--minhash-threshold` (default 0.85) → keep first occurrence.
///
/// Out-of-scope for V1 (Castform's pivot-judge filter): `--judge-model`
/// is reserved but rejected with a "deferred" message — wiring it would
/// need a live LLM, and the user explicitly excluded compute work.
/// Same for `--mode dpo` — V1 ships only `--mode sft`.
///
/// PRD: docs/prds/B29-trace-to-training-data.md
enum TracesToData {

    static func run(args: [String]) {
        var inDir: String? = nil
        var outPath: String? = nil
        var task: String? = nil
        var mode: String = "sft"
        var dropToolEcho: Bool = true
        var minhashThreshold: Double = 0.85
        var minhashShingleK: Int = 5
        var minhashNumPerms: Int = 64
        var judgeModel: String? = nil
        var dryRun: Bool = false

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--out":
                guard i + 1 < args.count else { exitUsage() }
                outPath = args[i+1]; i += 2
            case "--task":
                guard i + 1 < args.count else { exitUsage() }
                task = args[i+1]; i += 2
            case "--mode":
                guard i + 1 < args.count else { exitUsage() }
                mode = args[i+1]; i += 2
            case "--no-tool-echo-drop":
                dropToolEcho = false; i += 1
            case "--minhash-threshold":
                guard i + 1 < args.count else { exitUsage() }
                minhashThreshold = Double(args[i+1]) ?? minhashThreshold; i += 2
            case "--minhash-shingle":
                guard i + 1 < args.count else { exitUsage() }
                minhashShingleK = Int(args[i+1]) ?? minhashShingleK; i += 2
            case "--minhash-perms":
                guard i + 1 < args.count else { exitUsage() }
                minhashNumPerms = Int(args[i+1]) ?? minhashNumPerms; i += 2
            case "--judge-model":
                guard i + 1 < args.count else { exitUsage() }
                judgeModel = args[i+1]; i += 2
            case "--dry-run":
                dryRun = true; i += 1
            case "-h", "--help":
                exitUsage(0)
            default:
                if args[i].hasPrefix("-") {
                    fputs("traces-to-data: unknown flag \(args[i])\n", stderr); exitUsage()
                }
                if inDir == nil { inDir = args[i]; i += 1 }
                else { fputs("traces-to-data: multiple input dirs not supported\n", stderr); exitUsage() }
            }
        }

        guard let inDir = inDir else { fputs("traces-to-data: missing <atraj-dir>\n", stderr); exitUsage() }
        guard let outPath = outPath else { fputs("traces-to-data: --out required\n", stderr); exitUsage() }
        guard mode == "sft" else {
            fputs("traces-to-data: --mode \(mode) not yet supported (V1 ships --mode sft only). Follow-up: docs/prds/B29-trace-to-training-data.md.\n", stderr)
            exit(2)
        }
        if judgeModel != nil {
            fputs("traces-to-data: --judge-model is reserved but deferred — V1 has no LLM-pivot judge step. Ship-then-judge per docs/prds/B29-trace-to-training-data.md.\n", stderr)
            exit(2)
        }

        let inURL = URL(fileURLWithPath: inDir)
        let atrajURLs = enumerateAtraj(under: inURL)
        if atrajURLs.isEmpty {
            fputs("traces-to-data: no .atraj files found under \(inDir)\n", stderr); exit(1)
        }

        print("""

        TinyGPT — traces-to-data
        ------------------------
        in:                 \(inDir) (\(atrajURLs.count) trajectories)
        out:                \(outPath)
        task:               \(task ?? "(none)")
        mode:               \(mode)
        tool-echo drop:     \(dropToolEcho ? "on" : "off")
        minhash threshold:  \(minhashThreshold) (k=\(minhashShingleK), perms=\(minhashNumPerms))
        dry run:            \(dryRun ? "yes — counts only, no write" : "no")
        """)

        // First pass: harvest raw (prompt, response, source) triples.
        var raws: [Sample] = []
        var loadFailures = 0
        for url in atrajURLs {
            guard let traj = try? AgentTrajectory.load(from: url) else {
                loadFailures += 1; continue
            }
            raws.append(contentsOf: extractSamples(
                from: traj, sourcePath: url.lastPathComponent,
                task: task,
                dropToolEcho: dropToolEcho))
        }

        var stats = FilterStats()
        stats.trajectoriesScanned = atrajURLs.count
        stats.trajectoriesFailed = loadFailures
        stats.harvested = raws.count

        // Filter 1: tool-echo drop already applied at harvest time
        // (extractSamples honors `dropToolEcho`). Stats account for it
        // post-hoc on the raws array.

        // Filter 2: exact dedup on (prompt, response) pair.
        var exactSeen = Set<String>()
        var afterExact: [Sample] = []
        afterExact.reserveCapacity(raws.count)
        for s in raws {
            let key = s.prompt + "\u{1F}" + s.response  // unit separator
            if exactSeen.insert(key).inserted { afterExact.append(s) }
        }
        stats.exactDeduped = raws.count - afterExact.count

        // Filter 3: MinHash near-dedup on prompts. The shipped
        // `Dedupe.minHashSketch` takes pre-generated linear-hash
        // coefficients; we mirror the seed scheme `tinygpt dedupe`
        // uses so two runs with the same --minhash-perms produce
        // identical sketches (and identical dedup decisions).
        let prime: UInt64 = (1 << 61) - 1
        var aCoefs = [UInt64](); aCoefs.reserveCapacity(minhashNumPerms)
        var bCoefs = [UInt64](); bCoefs.reserveCapacity(minhashNumPerms)
        var seed: UInt64 = 0xc0ffee_1234_abcd_ef
        for _ in 0..<minhashNumPerms {
            seed = seed &* 6364136223846793005 &+ 1442695040888963407
            aCoefs.append((seed | 1) % prime)
            seed = seed &* 6364136223846793005 &+ 1442695040888963407
            bCoefs.append(seed % prime)
        }

        var afterMinhash: [Sample] = []
        var sketches: [[UInt64]] = []
        for s in afterExact {
            let sk = Dedupe.minHashSketch(
                of: s.prompt, shingle: minhashShingleK,
                aCoefs: aCoefs, bCoefs: bCoefs, prime: prime)
            var dup = false
            for prev in sketches {
                if jaccard(sk, prev) >= minhashThreshold { dup = true; break }
            }
            if !dup {
                afterMinhash.append(s); sketches.append(sk)
            }
        }
        stats.minhashDeduped = afterExact.count - afterMinhash.count
        stats.emitted = afterMinhash.count

        // Render + write.
        if dryRun {
            print("""

            (dry-run) would emit \(stats.emitted) rows to \(outPath)
            """)
            stats.print()
            return
        }
        let outURL = URL(fileURLWithPath: outPath)
        try? FileManager.default.removeItem(at: outURL)
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        guard let fh = try? FileHandle(forWritingTo: outURL) else {
            fputs("traces-to-data: could not open \(outPath) for write\n", stderr); exit(1)
        }
        defer { try? fh.close() }

        for s in afterMinhash {
            let row: [String: Any] = [
                "messages": [
                    ["role": "user", "content": s.prompt],
                    ["role": "assistant", "content": s.response],
                ],
                "task": s.task ?? NSNull(),
                "source_atraj": s.sourceAtraj,
            ]
            if let data = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]) {
                try? fh.write(contentsOf: data)
                try? fh.write(contentsOf: Data([0x0A]))
            }
        }

        print("""

        wrote \(stats.emitted) rows → \(outPath)
        """)
        stats.print()
    }

    // MARK: - Harvest

    private struct Sample {
        let prompt: String
        let response: String
        let task: String?
        let sourceAtraj: String
    }

    /// Pull (user → assistant) pairs out of a trajectory. A tool-using
    /// turn folds the tool result back into the same prompt context the
    /// final assistant answer landed on; we emit one (prompt, response)
    /// pair per user turn whose assistant FINAL answer was reached.
    /// Intermediate "tool" assistant turns (the ones that just emitted
    /// the JSON tool-call) are not training-data on their own.
    private static func extractSamples(
        from traj: AgentTrajectory,
        sourcePath: String,
        task: String?,
        dropToolEcho: Bool) -> [Sample]
    {
        var out: [Sample] = []
        var pendingUser: String? = nil
        var pendingFinalAssistant: String? = nil
        for step in traj.steps {
            switch step.role {
            case "user":
                // Flush any pending pair before starting a new turn.
                if let u = pendingUser, let a = pendingFinalAssistant {
                    if !dropToolEcho || !looksLikeToolEcho(assistant: a) {
                        out.append(Sample(prompt: u, response: a,
                                          task: task ?? traj.task,
                                          sourceAtraj: sourcePath))
                    }
                }
                pendingUser = step.content
                pendingFinalAssistant = nil
            case "assistant":
                // The final assistant turn in a turn-group is whichever
                // one carries an `{"answer": ...}` JSON OR is the last
                // before the next user turn. The recorder appends every
                // assistant turn; we keep updating, so the LAST wins.
                pendingFinalAssistant = step.content
            case "tool", "system":
                continue
            default:
                continue
            }
        }
        if let u = pendingUser, let a = pendingFinalAssistant {
            if !dropToolEcho || !looksLikeToolEcho(assistant: a) {
                out.append(Sample(prompt: u, response: a,
                                  task: task ?? traj.task,
                                  sourceAtraj: sourcePath))
            }
        }
        return out
    }

    /// Heuristic: an assistant answer is a tool-echo if its content,
    /// stripped of whitespace and JSON delimiters, is contained in the
    /// most recent tool_result. We don't have the tool result on hand
    /// here (extract pass is single-loop), so this lighter heuristic
    /// fires on assistant text that's a single tool-call JSON object
    /// with no `answer` key — i.e., the agent never produced a
    /// human-facing answer. That's the most common echo shape we see.
    private static func looksLikeToolEcho(assistant: String) -> Bool {
        let trimmed = assistant.trimmingCharacters(in: .whitespacesAndNewlines)
        // A bare tool-call JSON is signal we never reached an answer.
        if trimmed.hasPrefix("{") && trimmed.contains("\"tool\":") && !trimmed.contains("\"answer\":") {
            return true
        }
        return false
    }

    // MARK: - .atraj discovery

    private static func enumerateAtraj(under url: URL) -> [URL] {
        guard let e = FileManager.default.enumerator(
            at: url,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles])
        else { return [] }
        var out: [URL] = []
        for case let u as URL in e where u.pathExtension == "atraj" {
            out.append(u)
        }
        return out.sorted { $0.path < $1.path }
    }

    // MARK: - MinHash Jaccard

    /// Estimated Jaccard similarity from two MinHash sketches: the
    /// fraction of permutation positions at which the two sketches
    /// agree. Equal-length sketches assumed (`Dedupe.minHashSketch`
    /// always returns `numPerms` entries).
    private static func jaccard(_ a: [UInt64], _ b: [UInt64]) -> Double {
        guard !a.isEmpty, a.count == b.count else { return 0 }
        var matches = 0
        for i in 0..<a.count where a[i] == b[i] { matches += 1 }
        return Double(matches) / Double(a.count)
    }

    // MARK: - Stats

    private struct FilterStats {
        var trajectoriesScanned: Int = 0
        var trajectoriesFailed: Int = 0
        var harvested: Int = 0
        var exactDeduped: Int = 0
        var minhashDeduped: Int = 0
        var emitted: Int = 0

        func print() {
            Swift.print("""

            filter summary
              trajectories scanned:  \(trajectoriesScanned)
              trajectories failed:   \(trajectoriesFailed)
              raw (user→assistant) samples harvested: \(harvested)
              exact-duplicates dropped:               \(exactDeduped)
              minhash near-duplicates dropped:        \(minhashDeduped)
              emitted:                                \(emitted)
            """)
        }
    }

    // MARK: - Usage

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        Swift.print("""
        usage: tinygpt traces-to-data <atraj-dir> --out <data.jsonl> [options]

        Convert a directory of B22 `.atraj` rollouts into ChatML-style SFT JSONL.
        One row per (user → assistant final-answer) pair, deduped exactly +
        near-duplicates dropped via MinHash on the prompt.

        --out <path>              Output JSONL (required)
        --task <name>             Free-form task label written into each row
                                  (falls back to .atraj's `task` field if unset)
        --mode {sft|dpo}          V1 ships --mode sft only; --mode dpo is a
                                  follow-up (PRD B29 §"Open questions")
        --no-tool-echo-drop       Disable the heuristic that drops assistant
                                  turns that emitted a tool-call but never
                                  reached a final answer
        --minhash-threshold F     Jaccard threshold for near-dup drop (default 0.85)
        --minhash-shingle K       Shingle length for MinHash (default 5)
        --minhash-perms N         Permutations / sketch length (default 64)
        --judge-model <id>        Reserved; the LLM-pivot judge step is deferred
                                  (V1 has no live LLM dependency)
        --dry-run                 Compute filter counts; don't write the output

        Examples:
          tinygpt traces-to-data /tmp/atrajs --task tool-call --out tool-call-sft.jsonl
          tinygpt traces-to-data /tmp/atrajs --task tool-call --out /dev/null --dry-run
        """)
        exit(code)
    }
}
