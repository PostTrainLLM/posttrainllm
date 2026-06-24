import Foundation
import XCTest
@testable import TinyGPTIO

final class CorrectionCurationTests: XCTestCase {

    private func decode(_ line: String) -> [String: Any] {
        (try? JSONSerialization.jsonObject(with: Data(line.utf8))) as? [String: Any] ?? [:]
    }

    func test_sftPair_requiresInput() {
        let withInput = CorrectionEvent(intentKind: "dictation", input: "raw text",
                                        original: "their", corrected: "they're")
        let noInput = CorrectionEvent(intentKind: "dictation",
                                      original: "their", corrected: "they're")
        XCTAssertNotNil(withInput.sftPair())
        XCTAssertEqual(withInput.sftPair()?.user, "raw text")
        XCTAssertEqual(withInput.sftPair()?.assistant, "they're")
        XCTAssertNil(noInput.sftPair())
    }

    func test_dpoTriple_requiresInputAndSignal() {
        let good = CorrectionEvent(intentKind: "tool", input: "open it",
                                   original: "{\"n\":\"opn\"}", corrected: "{\"n\":\"open\"}")
        let noChange = CorrectionEvent(intentKind: "tool", input: "open it",
                                       original: "same", corrected: "same")
        XCTAssertNotNil(good.dpoTriple())
        XCTAssertEqual(good.dpoTriple()?.rejected, "{\"n\":\"opn\"}")
        XCTAssertNil(noChange.dpoTriple(), "no preference signal when corrected == original")
    }

    func test_curate_sft_emitsChatMLAndSkips() {
        let events = [
            CorrectionEvent(intentKind: "dictation", input: "in1", original: "o1", corrected: "c1"),
            CorrectionEvent(intentKind: "dictation", original: "o2", corrected: "c2"), // no input → skip
        ]
        let r = CorrectionCurator.curate(events, format: .sft)
        XCTAssertEqual(r.emitted, 1)
        XCTAssertEqual(r.skipped, 1)
        let row = decode(r.lines[0])
        let msgs = row["messages"] as? [[String: String]]
        XCTAssertEqual(msgs?.count, 2)
        XCTAssertEqual(msgs?[0]["role"], "user")
        XCTAssertEqual(msgs?[0]["content"], "in1")
        XCTAssertEqual(msgs?[1]["role"], "assistant")
        XCTAssertEqual(msgs?[1]["content"], "c1")
        XCTAssertEqual(row["task"] as? String, "dictation")
    }

    func test_curate_dpo_emitsTriple() {
        let events = [
            CorrectionEvent(intentKind: "tool", input: "p", original: "bad", corrected: "good"),
        ]
        let r = CorrectionCurator.curate(events, format: .dpo)
        XCTAssertEqual(r.emitted, 1)
        let row = decode(r.lines[0])
        XCTAssertEqual(row["prompt"] as? String, "p")
        XCTAssertEqual(row["chosen"] as? String, "good")
        XCTAssertEqual(row["rejected"] as? String, "bad")
    }
}
