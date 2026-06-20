import XCTest
@testable import TinyGPTModel

/// B2–B7 — router bake-off scorer.
final class RouterBakeoffTests: XCTestCase {
    func test_perMethodAccuracy_sortedBestFirst() {
        let rows: [(String, Bool)] = [
            ("classifier", true), ("classifier", true), ("classifier", true), ("classifier", false),
            ("fsm", true), ("fsm", false),
        ]
        let r = RouterBakeoff.score(rows)
        XCTAssertEqual(r.count, 2)
        XCTAssertEqual(r[0].method, "classifier")
        XCTAssertEqual(r[0].accuracy, 0.75, accuracy: 1e-9)
        XCTAssertEqual(r[0].n, 4)
        XCTAssertEqual(r[1].method, "fsm")
        XCTAssertEqual(r[1].accuracy, 0.5, accuracy: 1e-9)
    }

    func test_winnerAndDelta() {
        let r = RouterBakeoff.score([("a", true), ("a", true), ("b", true), ("b", false)])
        let w = RouterBakeoff.winner(r)!
        XCTAssertEqual(w.best.method, "a")            // 1.0 vs 0.5
        XCTAssertEqual(w.deltaPP, 50.0, accuracy: 1e-9)
    }

    func test_tieBreaksByName() {
        let r = RouterBakeoff.score([("zeta", true), ("alpha", true)])  // both 1.0
        XCTAssertEqual(r[0].method, "alpha")
        XCTAssertEqual(RouterBakeoff.winner(r)!.deltaPP, 0.0, accuracy: 1e-9)
    }
}
