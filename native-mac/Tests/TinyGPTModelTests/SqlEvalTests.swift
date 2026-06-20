import XCTest
@testable import TinyGPTModel

/// B1 — text-to-SQL execution-accuracy scoring.
final class SqlEvalTests: XCTestCase {

    func test_executionMatch_orderInsensitive() {
        XCTAssertTrue(SqlEval.executionMatch([["1","a"],["2","b"]], [["2","b"],["1","a"]]))
        XCTAssertTrue(SqlEval.executionMatch([], []))
    }

    func test_executionMatch_detectsDifference() {
        XCTAssertFalse(SqlEval.executionMatch([["1"]], [["2"]]))
        XCTAssertFalse(SqlEval.executionMatch([["1"],["1"]], [["1"]]))  // multiset cardinality
    }

    func test_exactMatch_normalizesWhitespaceAndCase() {
        XCTAssertTrue(SqlEval.exactMatch("SELECT  *\nFROM t", "select * from t"))
        XCTAssertFalse(SqlEval.exactMatch("select a from t", "select b from t"))
    }

    func test_score_aggregates() {
        let r = SqlEval.score(execMatches: [true, true, false, true],
                              exactMatches: [true, false, false, false])
        XCTAssertEqual(r.execAccuracy, 0.75, accuracy: 1e-9)
        XCTAssertEqual(r.exactMatch, 0.25, accuracy: 1e-9)
        XCTAssertEqual(r.n, 4)
    }
}
