// B25 (V1) — lexical query→sentence relevance for extractive compression.
//
// The PRD's learned path is a token-level relevance head trained with a
// teacher (needs a GPU). This is the lexical V1 — a BM25-lite sentence scorer
// — so `posttrainllm compress` works today (mirrors how the reranker shipped a
// lexical V1 before the learned one). Pure, no MLX, fully unit-testable.
import Foundation

public enum LexicalRelevance {

    /// Lowercase alphanumeric word tokens (terms < 2 chars dropped — they
    /// carry no retrieval signal and inflate matches).
    public static func tokenize(_ s: String) -> [String] {
        var out: [String] = []
        var cur = ""
        for ch in s.lowercased() {
            if ch.isLetter || ch.isNumber { cur.append(ch) }
            else if !cur.isEmpty { if cur.count >= 2 { out.append(cur) }; cur = "" }
        }
        if cur.count >= 2 { out.append(cur) }
        return out
    }

    /// BM25-lite relevance of each sentence to `query` (idf computed over the
    /// document's own sentences). Higher = more relevant. Length-normalised so
    /// long sentences don't win by mass alone.
    public static func scoreSentences(query: String, sentences: [String],
                                      k1: Double = 1.5, b: Double = 0.75) -> [Double] {
        let qTerms = Set(tokenize(query))
        if qTerms.isEmpty || sentences.isEmpty {
            return Array(repeating: 0, count: sentences.count)
        }
        let toks = sentences.map(tokenize)
        let n = Double(sentences.count)
        let avgdl = max(1.0, Double(toks.reduce(0) { $0 + $1.count }) / n)
        // document frequency per query term
        var df: [String: Int] = [:]
        for t in toks {
            for term in Set(t) where qTerms.contains(term) { df[term, default: 0] += 1 }
        }
        func idf(_ term: String) -> Double { log(1 + n / Double(1 + (df[term] ?? 0))) }
        return toks.map { sentToks in
            var counts: [String: Int] = [:]
            for term in sentToks where qTerms.contains(term) { counts[term, default: 0] += 1 }
            let dl = Double(sentToks.count)
            var s = 0.0
            for (term, f) in counts {
                let ff = Double(f)
                s += idf(term) * (ff * (k1 + 1)) / (ff + k1 * (1 - b + b * dl / avgdl))
            }
            return s
        }
    }

    /// Choose which sentence indices to keep (returned in original order).
    /// Priority: `threshold` (normalised score ≥ T) if set, else a length
    /// budget `keepFrac` (greedily add highest-scored until cumulative chars
    /// reach the fraction). `maxSentences` caps either path.
    public static func selectKeep(scores: [Double], sentences: [String],
                                  keepFrac: Double? = 0.3, threshold: Double? = nil,
                                  maxSentences: Int? = nil) -> [Int] {
        guard !scores.isEmpty else { return [] }
        let order = scores.indices.sorted { scores[$0] > scores[$1] }
        var keep: [Int] = []
        if let t = threshold {
            let mx = scores.max() ?? 0
            let norm = mx > 0 ? mx : 1
            for i in order where scores[i] / norm >= t { keep.append(i) }
        } else {
            let frac = keepFrac ?? 0.3
            let total = max(1, sentences.reduce(0) { $0 + $1.count })
            let budget = Double(total) * frac
            var acc = 0.0
            for i in order {
                if acc >= budget && !keep.isEmpty { break }
                keep.append(i); acc += Double(sentences[i].count)
            }
        }
        if let m = maxSentences, keep.count > m {
            keep = Array(keep.prefix(m))   // already score-ordered
        }
        return keep.sorted()
    }
}
