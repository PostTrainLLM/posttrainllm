// B35 (local-agent code-review PoC) — score a reviewer on issue detection:
// given planted issues vs the issues the review reported, compute recall /
// precision / F1. Running the reviewer needs the agent + SWE-bench harness
// (GPU); this pure scorer compares a results file and is unit-testable.
import Foundation

public enum ReviewScoring {

    public struct Report: Equatable, Sendable {
        public let recall: Double      // of planted issues, fraction the review found
        public let precision: Double   // of reported issues, fraction that were planted
        public let f1: Double
        public let n: Int
    }

    /// Pooled (micro) metrics over items, each `(planted, found)` as ID sets.
    public static func score(_ items: [(planted: Set<String>, found: Set<String>)]) -> Report {
        var tp = 0, totalPlanted = 0, totalFound = 0
        for it in items {
            tp += it.planted.intersection(it.found).count
            totalPlanted += it.planted.count
            totalFound += it.found.count
        }
        let recall = totalPlanted > 0 ? Double(tp) / Double(totalPlanted) : 0
        let precision = totalFound > 0 ? Double(tp) / Double(totalFound) : 0
        let f1 = (precision + recall) > 0 ? 2 * precision * recall / (precision + recall) : 0
        return Report(recall: recall, precision: precision, f1: f1, n: items.count)
    }
}
