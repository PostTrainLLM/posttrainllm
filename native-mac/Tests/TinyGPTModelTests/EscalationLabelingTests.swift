import XCTest
@testable import TinyGPTModel

/// B5 — defer-to-cloud labeling rule + classifier metrics.
final class EscalationLabelingTests: XCTestCase {

    func test_labelRule() {
        XCTAssertEqual(EscalationLabeling.label(localCorrect: true, cloudCorrect: true), .keepLocal)
        XCTAssertEqual(EscalationLabeling.label(localCorrect: true, cloudCorrect: false), .keepLocal)
        XCTAssertEqual(EscalationLabeling.label(localCorrect: false, cloudCorrect: true), .escalate)
        XCTAssertEqual(EscalationLabeling.label(localCorrect: false, cloudCorrect: false), .drop)
        XCTAssertEqual(EscalationLabeling.label(localCorrect: false, cloudCorrect: nil), .drop)
    }

    func test_metrics_knownConfusion() {
        // predictions (deferred?) vs localWrong (ground truth)
        // i0: defer & wrong  → TP
        // i1: defer & right  → FP (over-escalation)
        // i2: keep  & wrong  → FN
        // i3: keep  & right  → TN
        // i4: defer & wrong  → TP
        let pred  = [true,  true,  false, false, true ]
        let wrong = [true,  false, true,  false, true ]
        let m = EscalationLabeling.metrics(predictions: pred, localWrong: wrong)
        XCTAssertEqual(m.precision, 2.0/3.0, accuracy: 1e-9)   // TP=2, FP=1
        XCTAssertEqual(m.recall, 2.0/3.0, accuracy: 1e-9)      // TP=2, FN=1
        XCTAssertEqual(m.overEscalation, 1.0/2.0, accuracy: 1e-9) // 1 wrong-defer of 2 local-right
        XCTAssertEqual(m.n, 5)
    }

    func test_metrics_emptyAndAllCorrect() {
        let m = EscalationLabeling.metrics(predictions: [false, false], localWrong: [false, false])
        XCTAssertEqual(m.precision, 0)
        XCTAssertEqual(m.recall, 0)
        XCTAssertEqual(m.overEscalation, 0)   // no wrong defers
    }
}
