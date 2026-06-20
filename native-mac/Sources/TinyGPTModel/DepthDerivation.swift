// B18 — single `--depth N` knob → every pretrain hyperparameter.
//
// nanochat (karpathy/nanochat) ships this surface: pick a depth, and the
// width, heads, MLP, learning rate, batch size, and total step count all
// fall out of compute-optimal scaling laws. We borrow it.
//
// V1 = the Chinchilla compute-optimal corner (Hoffmann et al. 2022,
// arxiv 2203.15556): ~20 tokens per parameter. `--regime overtrained`
// doubles that (small models keep improving well past the corner).
import Foundation

/// Token budget regime for depth-derived training (B18).
public enum TrainRegime: String, Sendable, CaseIterable {
    case chinchilla     // D ≈ 20 · N   (compute-optimal corner)
    case overtrained    // D ≈ 40 · N   (small-model sweet spot)

    /// Tokens-per-parameter for this regime.
    public var tokensPerParam: Int { self == .chinchilla ? 20 : 40 }
}

/// Every pretrain HP derived from one depth knob.
public struct DepthDerivedHP: Sendable, Equatable {
    public let nLayers: Int
    public let dModel: Int
    public let nHeads: Int
    public let dMlp: Int
    public let peakLR: Float
    public let batchSize: Int      // sequences per optimizer step
    public let totalSteps: Int
    public let approxParams: Int   // non-embedding parameter estimate
    public let approxTokens: Int   // regime token budget
}

/// Map a depth (and regime + sequence length) to the full HP tuple.
///
/// Architecture follows the GPT-2 / nanochat shape (head_dim = 64):
///   nLayers = depth, dModel = 64·depth, nHeads = depth, dMlp = 4·dModel.
///
/// Scaling-law derivation:
///   - Non-embedding params  N ≈ 12 · L · d²  (attn 4d² + MLP 8d² per layer)
///   - Token budget          D = regime.tokensPerParam · N
///   - Peak LR               muP-flavoured 1/√width, anchored at 3e-3 @ d=512,
///                           clamped to [1e-4, 6e-3] (smaller nets → higher LR)
///   - Batch (sequences)     ⌈32·dModel / seqLen⌉  (global batch grows with width)
///   - Total steps           ⌈D / (batch · seqLen)⌉
///
/// These are a documented approximation of nanochat's curve, not a port of
/// its exact constants; `DepthDerivationTests` pins the numbers so the
/// formula can't drift silently.
public func deriveHP(depth: Int, regime: TrainRegime = .chinchilla,
                     seqLen: Int = 1024) -> DepthDerivedHP {
    let d = max(1, depth)
    let nLayers = d
    let dModel = 64 * d
    let nHeads = d
    let dMlp = 4 * dModel

    let params = 12 * nLayers * dModel * dModel
    let tokens = regime.tokensPerParam * params

    let lrRef: Float = 3e-3, dRef: Float = 512
    let peakLR = min(6e-3, max(1e-4, lrRef * (dRef / Float(dModel)).squareRoot()))

    let seq = max(1, seqLen)
    let batchSize = max(1, (32 * dModel) / seq)
    let totalSteps = max(1, tokens / (batchSize * seq))

    return DepthDerivedHP(nLayers: nLayers, dModel: dModel, nHeads: nHeads,
                          dMlp: dMlp, peakLR: peakLR, batchSize: batchSize,
                          totalSteps: totalSteps, approxParams: params,
                          approxTokens: tokens)
}
