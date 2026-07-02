#!/usr/bin/env bash
# No-MLX Swift smoke for pure TinyGPTModel helpers.
#
# Covers P1/P2 helpers whose XCTest target normally sits behind the full Swift
# package graph:
#   - B28 CompositeReward
#   - B11 WSD schedule
#   - B12 loss-spike recovery controller
#   - B15 layer-wise LR factor math
#   - B18 depth-derived hyperparameters
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

func assertClose(_ got: Double, _ want: Double, _ tol: Double = 1e-6, _ msg: String) {
    if abs(got - want) > tol {
        fputs("SMOKE FAIL: \(msg): got \(got), want \(want)\n", stderr)
        exit(1)
    }
}

func assertTrue(_ condition: @autoclosure () -> Bool, _ msg: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(msg)\n", stderr)
        exit(1)
    }
}

let reward = CompositeReward(dimensions: [
    RewardDimension(name: "correctness", score: 0.9, weight: 1.0),
    RewardDimension(name: "conciseness", score: 0.6, weight: 0.5),
    RewardDimension(name: "tool_call_efficiency", score: 0.8, weight: 0.25),
])
assertClose(reward.total, 1.4, 1e-9, "B28 weighted reward total")
assertTrue(reward.names == ["correctness", "conciseness", "tool_call_efficiency"],
           "B28 reward name order")
let encoded = try reward.encoded()
let decoded = try CompositeReward.decoded(from: encoded)
assertTrue(decoded == reward, "B28 JSON roundtrip")

let defaultDecay = lrAtWSD(step: 925, total: 1000, warmup: 100, decaySteps: 100,
                           maxLR: 1.0, minLR: 0.0)
let linearDecay = lrAtWSD(step: 925, total: 1000, warmup: 100, decaySteps: 100,
                          maxLR: 1.0, minLR: 0.0, decayShape: .linear)
let cosineDecay = lrAtWSD(step: 925, total: 1000, warmup: 100, decaySteps: 100,
                          maxLR: 1.0, minLR: 0.0, decayShape: .cosine)
assertClose(Double(defaultDecay), 0.5, 1e-6, "B11 default 1-sqrt decay")
assertClose(Double(linearDecay), 0.75, 1e-6, "B11 linear decay")
assertClose(Double(cosineDecay), 0.853553, 1e-5, "B11 cosine decay")

var controller = SpikeController(mode: .on, lrDropFactor: 0.5, maxDrops: 2)
if case .dropLR(let first, _) = controller.onSpike(ma: 1.0) {
    assertClose(Double(first), 0.5, 1e-6, "B12 first LR drop")
} else {
    assertTrue(false, "B12 first spike should drop LR")
}
if case .dropLR(let second, _) = controller.onSpike(ma: 1.0) {
    assertClose(Double(second), 0.25, 1e-6, "B12 second LR drop")
} else {
    assertTrue(false, "B12 second spike should drop LR")
}
assertTrue(controller.onSpike(ma: 1.0) == .abort(spikes: 3), "B12 abort after spike budget")

assertClose(Double(layerwiseLRFactor(parameterName: "layers.0.w", decay: 0.5, nLayers: 3)),
            0.25, 1e-6, "B15 shallow layer factor")
assertClose(Double(layerwiseLRFactor(parameterName: "layers.1.w", decay: 0.5, nLayers: 3)),
            0.5, 1e-6, "B15 middle layer factor")
assertClose(Double(layerwiseLRFactor(parameterName: "layers.2.w", decay: 0.5, nLayers: 3)),
            1.0, 1e-6, "B15 deepest layer factor")
assertClose(Double(layerwiseLRFactor(parameterName: "embed.weight", decay: 0.5, nLayers: 3)),
            1.0, 1e-6, "B15 non-layer factor")
assertTrue(layerwiseLayerIndex(parameterName: "blocks.7.attn.q_proj.weight") == 7,
           "B15 blocks.N index parse")

let depth4 = deriveHP(depth: 4, regime: .chinchilla, seqLen: 1024)
assertTrue(depth4.nLayers == 4, "B18 depth maps to layer count")
assertTrue(depth4.dModel == 256, "B18 depth maps to width")
assertTrue(depth4.approxParams == 3_145_728, "B18 param estimate")
assertTrue(depth4.approxTokens == 62_914_560, "B18 token estimate")
assertTrue(depth4.batchSize == 8, "B18 batch estimate")
assertTrue(depth4.totalSteps == 7_680, "B18 step estimate")
let overtrained = deriveHP(depth: 4, regime: .overtrained, seqLen: 1024)
assertTrue(overtrained.approxTokens == 2 * depth4.approxTokens, "B18 overtrained token budget")
assertTrue(overtrained.totalSteps == 2 * depth4.totalSteps, "B18 overtrained step budget")

print("SMOKE OK: pure Swift model helpers (B28/B11/B12/B15/B18)")
SWIFT

swiftc \
  "$ROOT/native-mac/Sources/TinyGPTModel/CompositeReward.swift" \
  "$ROOT/native-mac/Sources/TinyGPTModel/TrainSchedHelpers.swift" \
  "$ROOT/native-mac/Sources/TinyGPTModel/LayerwiseLR.swift" \
  "$ROOT/native-mac/Sources/TinyGPTModel/DepthDerivation.swift" \
  "$WORK/main.swift" \
  -o "$WORK/swift-pure-smoke"

"$WORK/swift-pure-smoke"
