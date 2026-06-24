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

    func test_curate_sft_isSFTReaderCompatibleAndSkips() {
        let events = [
            CorrectionEvent(intentKind: "dictation", input: "in1", original: "o1", corrected: "c1"),
            CorrectionEvent(intentKind: "dictation", original: "o2", corrected: "c2"), // no input → skip
        ]
        let r = CorrectionCurator.curate(events, format: .sft)
        XCTAssertEqual(r.emitted, 1)
        XCTAssertEqual(r.skipped, 1)
        let row = decode(r.lines[0])
        // Mirror SFTReader's exact contract (SFTCorpus.swift): instruction|prompt
        // and response|completion, and it drops rows where BOTH are empty. This
        // is the guard for the bug where a {messages:[…]} row loaded as 0 records.
        let instruction = (row["instruction"] as? String) ?? (row["prompt"] as? String) ?? ""
        let response = (row["response"] as? String) ?? (row["completion"] as? String) ?? ""
        XCTAssertEqual(instruction, "in1", "user prompt must map to instruction")
        XCTAssertEqual(response, "c1", "corrected must map to response")
        XCTAssertFalse(instruction.isEmpty && response.isEmpty, "SFTReader would skip this row")
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
