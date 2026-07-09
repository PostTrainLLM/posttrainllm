import Foundation
import TinyGPTModel

/// `posttrainllm eval-scaledown` (E6) — score extractive context compression.
///
/// V1 is **self-contained** (no external harness, no GPU): over a QA set
/// `{question, context, answer}`, compress each context with the lexical
/// compressor (B25 `LexicalRelevance`) and report mean compression ratio +
/// answer-retention (did the gold answer survive the compression?). This gives
/// B25 a runnable ship gate. The official ScaleBench wrapper (for public
/// leaderboard parity) is V2 — `scripts/install-scalebench.sh` fetches it.
enum EvalScaledown {
    static func run(args: [String]) {
        var dataPath: String?, outPath: String?
        var keepFrac = 0.3
        var threshold: Double?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--data":      dataPath = args[i+1]; i += 2
            case "--out":       outPath = args[i+1]; i += 2
            case "--keep-frac": keepFrac = Double(args[i+1]) ?? keepFrac; i += 2
            case "--threshold": threshold = Double(args[i+1]); i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                dataPath = args[i]; i += 1
            }
        }
        guard let dataPath = dataPath else { fputs("missing <qa.jsonl> (or --data)\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: dataPath, encoding: .utf8) else {
            fputs("could not read \(dataPath)\n", stderr); exit(1)
        }

        var ratios: [Double] = [], retained: [Bool] = []
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let q = o["question"] as? String,
                  let ctx = o["context"] as? String,
                  let ans = o["answer"] as? String else { continue }
            let sentences = Compress.splitSentences(ctx)
            guard !sentences.isEmpty else { continue }
            let scores = LexicalRelevance.scoreSentences(query: q, sentences: sentences)
            let keep = LexicalRelevance.selectKeep(scores: scores, sentences: sentences,
                                                   keepFrac: threshold == nil ? keepFrac : nil,
                                                   threshold: threshold)
            let compressed = keep.map { sentences[$0] }.joined(separator: " ")
            let origChars = sentences.reduce(0) { $0 + $1.count }
            ratios.append(origChars > 0 ? Double(compressed.count) / Double(origChars) : 0)
            retained.append(answerRetained(answer: ans, in: compressed))
        }
        guard !ratios.isEmpty else { fputs("no valid QA rows\n", stderr); exit(1) }
        let meanRatio = ratios.reduce(0, +) / Double(ratios.count)
        let retention = Double(retained.filter { $0 }.count) / Double(retained.count)
        print(String(format: "scaledown: compression_ratio=%.3f answer_retention=%.3f (n=%d, keep_frac=%.2f)",
                     meanRatio, retention, ratios.count, keepFrac))
        if let outPath = outPath {
            let rows = [
                ["task": "scaledown", "metric": "compression_ratio", "value": meanRatio, "n": ratios.count],
                ["task": "scaledown", "metric": "answer_retention", "value": retention, "n": ratios.count],
            ]
            let lines = rows.compactMap { try? String(data: JSONSerialization.data(withJSONObject: $0), encoding: .utf8) }
            try? (lines.joined(separator: "\n") + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        }
    }

    /// Answer survives if every significant answer term appears in the
    /// compressed text (case-insensitive) — a lexical proxy for "recoverable".
    static func answerRetained(answer: String, in text: String) -> Bool {
        let terms = LexicalRelevance.tokenize(answer)
        guard !terms.isEmpty else { return true }
        let hay = Set(LexicalRelevance.tokenize(text))
        return terms.allSatisfy { hay.contains($0) }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm eval-scaledown <qa.jsonl> [--keep-frac F | --threshold T] [--out rows.jsonl]

        Self-contained extractive-compression eval (E6 V1). QA rows:
          {question, context, answer}
        Compresses each context (lexical, B25) and reports mean compression
        ratio + answer-retention. Emits EvalCompare-style rows with --out.
        Official ScaleBench leaderboard wrapper is V2 — scripts/install-scalebench.sh.
        """)
        exit(code)
    }
}
