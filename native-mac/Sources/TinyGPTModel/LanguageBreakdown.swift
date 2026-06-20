// B8 (multilingual) — per-language accuracy breakdown + macro-average, the
// MILU reporting shape (each language weighted equally, not by sample count).
// Training the Indic specialist is the GPU step; this pure aggregator scores a
// per-language results file and is unit-testable.
import Foundation

public enum LanguageBreakdown {

    public struct LangResult: Equatable, Sendable {
        public let language: String
        public let accuracy: Double
        public let n: Int
    }

    /// Per-language accuracy (sorted by language) + macro-average (mean of the
    /// per-language accuracies — MILU weights each language equally).
    public static func score(_ rows: [(language: String, correct: Bool)])
        -> (perLanguage: [LangResult], macroAvg: Double) {
        var by: [String: (correct: Int, total: Int)] = [:]
        for r in rows {
            var e = by[r.language] ?? (0, 0)
            e.total += 1; if r.correct { e.correct += 1 }
            by[r.language] = e
        }
        let per = by.map {
            LangResult(language: $0.key,
                       accuracy: $0.value.total > 0 ? Double($0.value.correct) / Double($0.value.total) : 0,
                       n: $0.value.total)
        }.sorted { $0.language < $1.language }
        let macro = per.isEmpty ? 0 : per.reduce(0) { $0 + $1.accuracy } / Double(per.count)
        return (per, macro)
    }
}
