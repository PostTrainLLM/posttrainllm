// B1 (SQL domain) — execution-accuracy scoring for a text-to-SQL specialist.
//
// The model-generation step needs a GPU, but the EVAL is self-contained: run
// predicted vs gold SQL against a SQLite DB and compare result sets. This file
// is the pure comparison/aggregation (testable); the sqlite3 execution + CLI
// live in `EvalSql.swift`. Execution accuracy (denotation match) is the Spider
// metric; V1 compares result sets order-insensitively (no ORDER-BY detection).
import Foundation

public enum SqlEval {

    /// Order-insensitive (multiset) equality of two result sets. A result set
    /// is rows × cells. Rows are compared as a sorted multiset so query row
    /// order doesn't matter (the standard exec-match without ORDER BY).
    public static func executionMatch(_ a: [[String]], _ b: [[String]]) -> Bool {
        func key(_ rows: [[String]]) -> [String] {
            rows.map { $0.joined(separator: "\u{1f}") }.sorted()
        }
        return key(a) == key(b)
    }

    /// Whitespace/case-normalised SQL string equality (a strict secondary metric).
    public static func exactMatch(_ a: String, _ b: String) -> Bool {
        func norm(_ s: String) -> String {
            s.lowercased().split(whereSeparator: { $0 == " " || $0 == "\n" || $0 == "\t" })
                .joined(separator: " ").trimmingCharacters(in: .whitespaces)
        }
        return norm(a) == norm(b)
    }

    public struct Report: Equatable, Sendable {
        public let execAccuracy: Double
        public let exactMatch: Double
        public let n: Int
    }

    public static func score(execMatches: [Bool], exactMatches: [Bool]) -> Report {
        let n = execMatches.count
        guard n > 0 else { return Report(execAccuracy: 0, exactMatch: 0, n: 0) }
        return Report(
            execAccuracy: Double(execMatches.filter { $0 }.count) / Double(n),
            exactMatch: Double(exactMatches.filter { $0 }.count) / Double(n),
            n: n)
    }
}
