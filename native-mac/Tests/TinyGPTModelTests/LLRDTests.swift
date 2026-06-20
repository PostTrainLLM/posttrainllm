import XCTest
import MLX
import MLXNN
@testable import TinyGPTModel

/// B15 — layer-wise LR decay. `scaleLayerwiseLR` is the shared helper the
/// `sft`, `dpo`, and `finetune` subcommands route their `--llrd γ` flag
/// through (it scales each block's gradient by γ^(L-1-i) so the deepest
/// layer trains at full LR). These tests pin the decay math and the no-op
/// fast path.
final class LLRDTests: XCTestCase {

    /// Build a 3-layer grad tree (`layers.N.w`) plus a non-layer leaf, then
    /// assert γ^(L-1-i) scaling: shallow layers shrink, deepest stays full,
    /// embeddings/norms (no `layers.N` ancestor) keep the full LR.
    func test_scaleLayerwiseLR_appliesDepthDecay() {
        var grads = NestedDictionary<String, MLXArray>()
        grads["layers"] = .array([
            .dictionary(["w": .value(MLXArray([1.0] as [Float]))]),
            .dictionary(["w": .value(MLXArray([1.0] as [Float]))]),
            .dictionary(["w": .value(MLXArray([1.0] as [Float]))]),
        ])
        grads["embed"] = .value(MLXArray([1.0] as [Float]))

        let scaled = scaleLayerwiseLR(grads, decay: 0.5, nLayers: 3)
        let flat = Dictionary(uniqueKeysWithValues: scaled.flattened())

        // layer 0 (shallowest): 0.5^(3-1-0) = 0.25
        XCTAssertEqual(flat["layers.0.w"]!.item(Float.self), 0.25, accuracy: 1e-6)
        // layer 1: 0.5^1 = 0.5
        XCTAssertEqual(flat["layers.1.w"]!.item(Float.self), 0.5, accuracy: 1e-6)
        // layer 2 (deepest): 0.5^0 = 1.0 (full LR)
        XCTAssertEqual(flat["layers.2.w"]!.item(Float.self), 1.0, accuracy: 1e-6)
        // non-layer leaf: full LR
        XCTAssertEqual(flat["embed"]!.item(Float.self), 1.0, accuracy: 1e-6)
    }

    /// γ == 1.0 is the no-op fast path used when `--llrd` is omitted.
    func test_scaleLayerwiseLR_noopAtDecay1() {
        var grads = NestedDictionary<String, MLXArray>()
        grads["layers"] = .array([.dictionary(["w": .value(MLXArray([2.0] as [Float]))])])

        let scaled = scaleLayerwiseLR(grads, decay: 1.0, nLayers: 1)
        let flat = Dictionary(uniqueKeysWithValues: scaled.flattened())
        XCTAssertEqual(flat["layers.0.w"]!.item(Float.self), 2.0, accuracy: 1e-6)
    }
}
