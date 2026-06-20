// B2–B7 (router family) — the bake-off scorer: compare routing methods
// (e.g. a trained classifier router vs an FSM-only router) on tool-selection
// accuracy. Generating the predictions needs the router models (GPU); this
// pure scorer compares a predictions file and is fully unit-testable.
import Foundation

public enum RouterBakeoff {

    public struct MethodResult: Equatable, Sendable {
        public let method: String
        public let accuracy: Double
        public let n: Int
    }

    /// Per-method accuracy from (method, correct) observations, best first.
    public static func score(_ rows: [(method: String, correct: Bool)]) -> [MethodResult] {
        var by: [String: (correct: Int, total: Int)] = [:]
        for r in rows {
            var e = by[r.method] ?? (0, 0)
            e.total += 1; if r.correct { e.correct += 1 }
            by[r.method] = e
        }
        return by.map {
            MethodResult(method: $0.key,
                         accuracy: $0.value.total > 0 ? Double($0.value.correct) / Double($0.value.total) : 0,
                         n: $0.value.total)
        }
        // deterministic order: accuracy desc, then method name for ties
        .sorted { $0.accuracy != $1.accuracy ? $0.accuracy > $1.accuracy : $0.method < $1.method }
    }

    /// Winner + its lead (in percentage points) over the runner-up.
    public static func winner(_ results: [MethodResult]) -> (best: MethodResult, deltaPP: Double)? {
        guard let best = results.first else { return nil }
        let delta = results.dropFirst().first.map { (best.accuracy - $0.accuracy) * 100 } ?? 0
        return (best, delta)
    }
}
