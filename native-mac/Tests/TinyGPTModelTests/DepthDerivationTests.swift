import XCTest
@testable import TinyGPTModel

/// B18 — `--depth N` single-knob HP derivation. Pins the scaling-law
/// formula against a hand-computed table at depth ∈ {4, 12, 24, 36}
/// (seqLen 1024, chinchilla regime) so the curve can't drift silently.
final class DepthDerivationTests: XCTestCase {

    func test_depth4() {
        let h = deriveHP(depth: 4, regime: .chinchilla, seqLen: 1024)
        XCTAssertEqual(h.nLayers, 4)
        XCTAssertEqual(h.dModel, 256)
        XCTAssertEqual(h.nHeads, 4)
        XCTAssertEqual(h.dMlp, 1024)
        XCTAssertEqual(h.approxParams, 3_145_728)
        XCTAssertEqual(h.approxTokens, 62_914_560)
        XCTAssertEqual(h.peakLR, 4.2426e-3, accuracy: 1e-6)   // 3e-3·√2
        XCTAssertEqual(h.batchSize, 8)
        XCTAssertEqual(h.totalSteps, 7_680)
    }

    func test_depth12() {
        let h = deriveHP(depth: 12, regime: .chinchilla, seqLen: 1024)
        XCTAssertEqual(h.dModel, 768)
        XCTAssertEqual(h.dMlp, 3072)
        XCTAssertEqual(h.approxParams, 84_934_656)
        XCTAssertEqual(h.peakLR, 2.4495e-3, accuracy: 1e-6)
        XCTAssertEqual(h.batchSize, 24)
        XCTAssertEqual(h.totalSteps, 69_120)
    }

    func test_depth24() {
        let h = deriveHP(depth: 24, regime: .chinchilla, seqLen: 1024)
        XCTAssertEqual(h.dModel, 1536)
        XCTAssertEqual(h.approxParams, 679_477_248)
        XCTAssertEqual(h.peakLR, 1.7320e-3, accuracy: 1e-6)
        XCTAssertEqual(h.batchSize, 48)
        XCTAssertEqual(h.totalSteps, 276_480)
    }

    func test_depth36() {
        let h = deriveHP(depth: 36, regime: .chinchilla, seqLen: 1024)
        XCTAssertEqual(h.dModel, 2304)
        XCTAssertEqual(h.approxParams, 2_293_235_712)
        XCTAssertEqual(h.peakLR, 1.4142e-3, accuracy: 1e-6)
        XCTAssertEqual(h.batchSize, 72)
        XCTAssertEqual(h.totalSteps, 622_080)
    }

    /// Overtrained regime doubles the token budget (and thus steps).
    func test_overtrained_doublesTokens() {
        let c = deriveHP(depth: 4, regime: .chinchilla, seqLen: 1024)
        let o = deriveHP(depth: 4, regime: .overtrained, seqLen: 1024)
        XCTAssertEqual(o.approxTokens, 2 * c.approxTokens)
        XCTAssertEqual(o.totalSteps, 2 * c.totalSteps)
        XCTAssertEqual(o.dModel, c.dModel)        // architecture unchanged
        XCTAssertEqual(o.peakLR, c.peakLR, accuracy: 1e-9)
    }

    /// Peak LR is monotone-decreasing in width (smaller nets → higher LR).
    func test_peakLR_monotoneDecreasing() {
        let lrs = [4, 12, 24, 36].map { deriveHP(depth: $0).peakLR }
        for i in 1..<lrs.count { XCTAssertLessThan(lrs[i], lrs[i-1]) }
    }
}
