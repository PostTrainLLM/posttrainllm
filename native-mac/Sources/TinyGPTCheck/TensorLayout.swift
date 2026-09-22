import Foundation

/// Structural classification of a checkpoint's tensor names — the signal
/// that turns "is this architecture on our list" into "does this
/// checkpoint's weight layout match what HFModelLoader actually builds".
///
/// Names come from either `model.safetensors.index.json` (sharded repos
/// — a small JSON manifest) or a Range-read of a safetensors file's JSON
/// header (the header is metadata at the front of the file; weights are
/// never fetched).
///
/// `TinyGPTModelHF` consumes the standard HF naming convention:
///   model.embed_tokens.weight, model.layers.N.self_attn.{q,k,v,o}_proj,
///   model.layers.N.mlp.{gate,up,down}_proj, model.norm.weight,
///   lm_head.weight
/// so a name-level match is strong — though not sufficient — evidence of
/// loadability. Mismatches (encoder-only, MoE routers, vision towers,
/// diffusers UNet/VAE) are detected the same way.
public struct TensorLayout: Sendable, Equatable {
    public enum Kind: String, Sendable {
        case llamaFamily        // HF-native causal-LM naming our loader expects
        case moe                // expert/router tensors present
        case multimodal         // vision/audio tower + projector tensors
        case encoderOnly        // encoder.* / pooler, no LM head shape
        case diffusion          // unet / vae / text_encoder
        case packedQuant        // qweight/qzeros/scales — GPTQ/AWQ (loader dequants)
        case unknown
    }

    public let kind: Kind
    public let totalTensors: Int
    /// Tensor names matching the HF-native causal-LM convention.
    public let lmConventionCount: Int
    /// A few illustrative names for the report.
    public let sampleNames: [String]
    /// Names that triggered non-LM classifications (evidence trail).
    public let markers: [String]
    /// Recognized non-Llama convention, when the layout is a *named*
    /// family the loader can't map — e.g. GPT-2's fused `c_attn`,
    /// GPT-NeoX's fused `query_key_value`, BLOOM/Falcon `h.N`/`transformer.h`.
    /// Turns "unknown layout" into "unsupported layout: <name>".
    public let conventionName: String?

    public var lmConventionRatio: Double {
        totalTensors > 0 ? Double(lmConventionCount) / Double(totalTensors) : 0
    }

    private static func markerKind(for name: String) -> Kind? {
        let value = name.lowercased()
        if value.contains("unet") || value.contains("vae.") || value.hasPrefix("text_encoder") {
            return .diffusion
        }
        if value.contains("vision_tower") || value.contains("multi_modal_projector")
            || value.contains("image_tower") || value.hasPrefix("visual.") {
            return .multimodal
        }
        if value.contains(".experts.") || value.contains("block_sparse_moe")
            || value.hasSuffix("router.weight") || value.contains("mlp.router") {
            return .moe
        }
        return nil
    }

    private static func isMarker(_ name: String) -> Bool {
        markerKind(for: name) != nil || name.contains("router.weight")
            || (name.hasSuffix(".gate.weight") && name.contains("mlp"))
    }

    private static func namedConvention(in names: [String]) -> String? {
        if names.contains(where: { $0.range(of: #"h\.\d+\.attn\.c_attn"#, options: .regularExpression) != nil }) {
            return "GPT-2-style fused c_attn attention (h.N.attn.c_attn)"
        }
        if names.contains(where: { $0.hasPrefix("gpt_neox.") || $0.contains("query_key_value") }) {
            return "GPT-NeoX-style fused query_key_value"
        }
        if names.contains(where: { $0.hasPrefix("transformer.h.") || $0.hasPrefix("transformer.word_embeddings") }) {
            return "BLOOM/Falcon-style transformer.h.N"
        }
        if names.contains(where: { $0.contains("encoder.layer.") }) {
            return "BERT-style encoder stack"
        }
        return nil
    }

    public static func assess(names: [String]) -> TensorLayout {
        let lmPattern = #/model\.(embed_tokens|norm|layers\.\d+\.(self_attn\.(q|k|v|o)_proj|mlp\.(gate|up|down)_proj|(input|post_attention)_layernorm))\.weight/#
        var lmCount = 0
        var markers: [String] = []
        var sawQWeight = false

        for name in names {
            if name.firstMatch(of: lmPattern) != nil || name == "lm_head.weight" {
                lmCount += 1
            }
            let n = name.lowercased()
            if n.hasSuffix(".qweight") || n.hasSuffix(".qzeros") { sawQWeight = true }
            if isMarker(n) { markers.append(name) }
        }

        let kind: Kind
        let lower = names.map { $0.lowercased() }
        let markerKinds = Set(lower.compactMap(markerKind))
        if markerKinds.contains(.diffusion) {
            kind = .diffusion
        } else if markerKinds.contains(.multimodal) {
            kind = .multimodal
        } else if markerKinds.contains(.moe) {
            kind = .moe
        } else if sawQWeight {
            kind = .packedQuant
        } else if names.contains(where: { $0.hasPrefix("encoder.") || $0.contains("pooler") })
                    && !names.contains("lm_head.weight") && lmCount == 0 {
            kind = .encoderOnly
        } else if lmCount > 0 && Double(lmCount) / Double(max(names.count, 1)) > 0.5 {
            kind = .llamaFamily
        } else {
            kind = .unknown
        }

        // Named non-Llama conventions — a positive ID is more useful
        // than "unknown": it tells the user exactly which gap exists.
        let convention = kind == .unknown ? namedConvention(in: lower) : nil

        return TensorLayout(
            kind: kind, totalTensors: names.count,
            lmConventionCount: lmCount,
            sampleNames: Array(names.prefix(6)),
            markers: Array(markers.prefix(8)),
            conventionName: convention)
    }
}
