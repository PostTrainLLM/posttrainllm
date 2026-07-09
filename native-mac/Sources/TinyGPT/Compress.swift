import Foundation
import TinyGPTModel

/// `posttrainllm compress <query> --doc <doc.txt>` (B25 V1) — extractive context
/// compression: keep the document sentences most relevant to the query, drop
/// the rest. V1 scores sentences with a lexical BM25-lite relevance
/// (`LexicalRelevance`); the learned token-level relevance head + LoRA recipe
/// (and the ScaleDown leaderboard submission) are V2 and need a GPU.
enum Compress {
    static func run(args: [String]) {
        var query: String? = nil
        var docPath: String? = nil
        var outPath: String? = nil
        var threshold: Double? = nil
        var keepFrac = 0.3
        var maxSentences: Int? = nil

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--doc":           docPath = args[i+1]; i += 2
            case "--out":           outPath = args[i+1]; i += 2
            case "--threshold":     threshold = Double(args[i+1]); i += 2
            case "--keep-frac":     keepFrac = Double(args[i+1]) ?? keepFrac; i += 2
            case "--max-sentences": maxSentences = Int(args[i+1]); i += 2
            case "--model", "--adapter":
                fputs("note: --\(args[i].dropFirst(2)) is reserved for the learned relevance head (V2); V1 uses lexical scoring\n", stderr)
                i += 2
            case "-h", "--help":    exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                if query == nil { query = args[i] } else { fputs("unexpected arg: \(args[i])\n", stderr); exitUsage() }
                i += 1
            }
        }
        guard let query = query else { fputs("missing <query>\n", stderr); exitUsage() }
        guard let docPath = docPath else { fputs("--doc <doc.txt> required\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: docPath, encoding: .utf8) else {
            fputs("could not read \(docPath)\n", stderr); exit(1)
        }

        let sentences = splitSentences(raw)
        guard !sentences.isEmpty else { fputs("no sentences in \(docPath)\n", stderr); exit(1) }
        let scores = LexicalRelevance.scoreSentences(query: query, sentences: sentences)
        let keep = LexicalRelevance.selectKeep(scores: scores, sentences: sentences,
                                               keepFrac: threshold == nil ? keepFrac : nil,
                                               threshold: threshold, maxSentences: maxSentences)
        let kept = keep.map { sentences[$0] }
        let compressed = kept.joined(separator: " ")

        if let outPath = outPath {
            try? compressed.write(toFile: outPath, atomically: true, encoding: .utf8)
        } else {
            print(compressed)
        }

        let origChars = sentences.reduce(0) { $0 + $1.count }
        let keptChars = compressed.count
        let ratio = origChars > 0 ? 100.0 * Double(keptChars) / Double(origChars) : 0
        fputs(String(format: "\ncompressed: %d→%d sentences, %d→%d chars (%.0f%% of original)\n",
                     sentences.count, kept.count, origChars, keptChars, ratio), stderr)
    }

    /// Split on sentence terminators (.!?) and newlines; trim, drop empties.
    static func splitSentences(_ text: String) -> [String] {
        var out: [String] = []
        var cur = ""
        for ch in text {
            cur.append(ch)
            if ch == "." || ch == "!" || ch == "?" || ch == "\n" {
                let t = cur.trimmingCharacters(in: .whitespacesAndNewlines)
                if !t.isEmpty { out.append(t) }
                cur = ""
            }
        }
        let t = cur.trimmingCharacters(in: .whitespacesAndNewlines)
        if !t.isEmpty { out.append(t) }
        return out
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm compress <query> --doc <doc.txt> [options]

        Extractive context compression (B25 V1, lexical): keep the document
        sentences most relevant to <query>, drop the rest.

        --doc <path>           document to compress (required)
        --out <path>           write compressed text here (default: stdout)
        --keep-frac F          keep ~F of the original length, highest-scored
                               (default 0.3); ignored if --threshold is set
        --threshold T          keep sentences with normalised score >= T (0..1)
        --max-sentences N      cap the number of kept sentences

        V2 (needs a GPU): a trained token-level relevance head replaces the
        lexical scorer — see docs/recipes/b25-scaledown.md. --model/--adapter
        are reserved for it.
        """)
        exit(code)
    }
}
