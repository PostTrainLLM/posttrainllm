import XCTest
@testable import TinyGPTModel

/// B35 — code-review issue-detection scoring.
final class ReviewScoringTests: XCTestCase {
    func test_pooledMetrics() {
        // item1: planted {a,b}, found {a,c} → tp 1
        // item2: planted {d},   found {d}   → tp 1
        // totals: tp 2, planted 3, found 3 → recall 2/3, precision 2/3, f1 2/3
        let items: [(Set<String>, Set<String>)] = [
            (["a", "b"], ["a", "c"]),
            (["d"], ["d"]),
        ]
        let r = ReviewScoring.score(items)
        XCTAssertEqual(r.recall, 2.0/3.0, accuracy: 1e-9)
        XCTAssertEqual(r.precision, 2.0/3.0, accuracy: 1e-9)
        XCTAssertEqual(r.f1, 2.0/3.0, accuracy: 1e-9)
        XCTAssertEqual(r.n, 2)
    }

    func test_perfectAndEmpty() {
        let perfect = ReviewScoring.score([(["x"], ["x"])])
        XCTAssertEqual(perfect.recall, 1.0); XCTAssertEqual(perfect.precision, 1.0); XCTAssertEqual(perfect.f1, 1.0)
        let noFindings = ReviewScoring.score([(["x"], [])])
        XCTAssertEqual(noFindings.recall, 0.0); XCTAssertEqual(noFindings.precision, 0.0); XCTAssertEqual(noFindings.f1, 0.0)
    }
}
