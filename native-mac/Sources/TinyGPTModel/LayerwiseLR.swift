import Foundation

/// Pure B15 layer-wise LR decay factor.
///
/// Dotted parameter names under `blocks.N` or `layers.N` get
/// `decay^(nLayers - 1 - N)` so shallower layers move less and the deepest
/// layer keeps the full LR. Non-layer leaves keep factor 1.0.
public func layerwiseLRFactor(parameterName name: String, decay: Float, nLayers: Int) -> Float {
    guard decay < 0.9999, let layerIdx = layerwiseLayerIndex(parameterName: name) else {
        return 1.0
    }
    let exponent = max(0, nLayers - 1 - layerIdx)
    return pow(decay, Float(exponent))
}

/// Parse a dotted parameter name like `blocks.7.attn.q_proj.weight` or
/// `layers.3.self_attn.o_proj.weight`. Returns nil for embeddings, final
/// norms, heads, or malformed layer names.
public func layerwiseLayerIndex(parameterName name: String) -> Int? {
    let parts = name.split(separator: ".")
    guard parts.count >= 2 else { return nil }
    for i in 0..<(parts.count - 1) {
        if parts[i] == "blocks" || parts[i] == "layers" {
            return Int(parts[i + 1])
        }
    }
    return nil
}
