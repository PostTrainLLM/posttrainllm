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

        let lower = names.map { $0.lowercased() }
        let kind = classify(lowerNames: lower, lmCount: lmCount, sawQWeight: sawQWeight)
        let convention = kind == .unknown ? recognizedConvention(lower) : nil

        return TensorLayout(
            kind: kind, totalTensors: names.count,
            lmConventionCount: lmCount,
            sampleNames: Array(names.prefix(6)),
            markers: Array(markers.prefix(8)),
            conventionName: convention)
    }

    private static func isMarker(_ name: String) -> Bool {
        let fragments = [
            "unet", "vae.", "vision_tower", "multi_modal_projector", "image_tower",
            ".experts.", "block_sparse_moe", "router.weight",
        ]
        return fragments.contains { name.contains($0) }
            || name.hasPrefix("text_encoder") || name.hasPrefix("visual.")
            || (name.hasSuffix(".gate.weight") && name.contains("mlp"))
    }

    private static func classify(
        lowerNames: [String], lmCount: Int, sawQWeight: Bool
    ) -> Kind {
        if lowerNames.contains(where: { isDiffusionName($0) }) { return .diffusion }
        if lowerNames.contains(where: { isMultimodalName($0) }) { return .multimodal }
        if lowerNames.contains(where: { isMoEName($0) }) { return .moe }
        if sawQWeight { return .packedQuant }
        let encoder = lowerNames.contains { $0.hasPrefix("encoder.") || $0.contains("pooler") }
        if encoder && !lowerNames.contains("lm_head.weight") && lmCount == 0 { return .encoderOnly }
        let ratio = Double(lmCount) / Double(max(lowerNames.count, 1))
        return lmCount > 0 && ratio > 0.5 ? .llamaFamily : .unknown
    }

    private static func isDiffusionName(_ name: String) -> Bool {
        ["unet", "vae."].contains { name.contains($0) } || name.hasPrefix("text_encoder")
    }

    private static func isMultimodalName(_ name: String) -> Bool {
        ["vision_tower", "multi_modal_projector", "image_tower"].contains { name.contains($0) }
            || name.hasPrefix("visual.")
    }

    private static func isMoEName(_ name: String) -> Bool {
        [".experts.", "block_sparse_moe", "mlp.router"].contains { name.contains($0) }
            || name.hasSuffix("router.weight")
    }

    private static func recognizedConvention(_ names: [String]) -> String? {
        if names.contains(where: {
            $0.range(of: #"h\.\d+\.attn\.c_attn"#, options: .regularExpression) != nil
        }) { return "GPT-2-style fused c_attn attention (h.N.attn.c_attn)" }
        if names.contains(where: { $0.hasPrefix("gpt_neox.") || $0.contains("query_key_value") }) {
            return "GPT-NeoX-style fused query_key_value"
        }
        if names.contains(where: {
            $0.hasPrefix("transformer.h.") || $0.hasPrefix("transformer.word_embeddings")
        }) { return "BLOOM/Falcon-style transformer.h.N" }
        if names.contains(where: { $0.contains("encoder.layer.") }) {
            return "BERT-style encoder stack"
        }
        return nil
    }
}
