import XCTest
@testable import TinyGPTModel

/// B8 — per-language breakdown + macro-average.
final class LanguageBreakdownTests: XCTestCase {
    func test_perLanguageAndMacro() {
        // hi: 1/2 = 0.5 ; ta: 2/2 = 1.0 ; macro = 0.75
        let rows: [(String, Bool)] = [("hi", true), ("hi", false), ("ta", true), ("ta", true)]
        let (per, macro) = LanguageBreakdown.score(rows)
        XCTAssertEqual(per.map(\.language), ["hi", "ta"])   // sorted
        XCTAssertEqual(per[0].accuracy, 0.5, accuracy: 1e-9)
        XCTAssertEqual(per[1].accuracy, 1.0, accuracy: 1e-9)
        XCTAssertEqual(macro, 0.75, accuracy: 1e-9)
    }

    func test_macroIgnoresSampleCount() {
        // en: 0/100 ; fr: 1/1 → macro = 0.5 (equal weight), not ~0.01 (micro)
        var rows: [(String, Bool)] = Array(repeating: ("en", false), count: 100)
        rows.append(("fr", true))
        let (_, macro) = LanguageBreakdown.score(rows)
        XCTAssertEqual(macro, 0.5, accuracy: 1e-9)
    }
}
