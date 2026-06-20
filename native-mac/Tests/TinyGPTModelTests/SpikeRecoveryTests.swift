import XCTest
@testable import TinyGPTModel

/// B12 — loss-spike recovery controller. Pins the policy: `off`/`warn` never
/// touch the LR, `on` cuts the LR by `lrDropFactor` per spike and aborts once
/// the spike budget is exhausted.
final class SpikeRecoveryTests: XCTestCase {

    func test_off_isNoOp() {
        var c = SpikeController(mode: .off)
        XCTAssertEqual(c.onSpike(ma: 1.0), .none)
        XCTAssertEqual(c.lrMultiplier, 1.0, accuracy: 1e-9)
    }

    func test_warn_logsButHoldsLR() {
        var c = SpikeController(mode: .warn)
        XCTAssertEqual(c.onSpike(ma: 2.0), .warn(ma: 2.0))
        XCTAssertEqual(c.lrMultiplier, 1.0, accuracy: 1e-9)
        XCTAssertEqual(c.drops, 0)
    }

    func test_on_cutsLRThenAborts() {
        var c = SpikeController(mode: .on, lrDropFactor: 0.5, maxDrops: 3)
        // drop 1 → ×0.5
        guard case .dropLR(let m1, _) = c.onSpike(ma: 1.0) else { return XCTFail("expected dropLR") }
        XCTAssertEqual(m1, 0.5, accuracy: 1e-6)
        // drop 2 → ×0.25
        guard case .dropLR(let m2, _) = c.onSpike(ma: 1.0) else { return XCTFail("expected dropLR") }
        XCTAssertEqual(m2, 0.25, accuracy: 1e-6)
        // drop 3 → ×0.125
        guard case .dropLR(let m3, _) = c.onSpike(ma: 1.0) else { return XCTFail("expected dropLR") }
        XCTAssertEqual(m3, 0.125, accuracy: 1e-6)
        XCTAssertEqual(c.lrMultiplier, 0.125, accuracy: 1e-6)
        // 4th spike exceeds budget (maxDrops=3) → abort
        XCTAssertEqual(c.onSpike(ma: 1.0), .abort(spikes: 4))
    }

    /// The detector + controller compose: a clean run never trips; a single
    /// 10× spike after warmup fires exactly once.
    func test_detector_plus_controller_endToEnd() {
        var det = LossSpikeDetector(window: 4, factor: 3.0)
        var ctl = SpikeController(mode: .on)
        var actions: [SpikeAction] = []
        let losses: [Float] = [1, 1, 1, 1, 1, 1, 20, 1, 1]  // spike at idx 6
        for (step, loss) in losses.enumerated() {
            let (spike, ma) = det.observe(loss: loss, step: step)
            if spike { actions.append(ctl.onSpike(ma: ma)) }
        }
        XCTAssertEqual(actions.count, 1, "exactly one spike should fire")
        if case .dropLR = actions.first { } else { XCTFail("expected an LR drop") }
        XCTAssertEqual(ctl.lrMultiplier, 0.5, accuracy: 1e-6)
    }
}
