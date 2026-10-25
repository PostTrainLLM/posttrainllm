import Foundation
import MLX
import MLXNN
import MLXRandom
import TinyGPTIO
import XCTest
@testable import TinyGPTModel

/// Numerics gate for the MLX-native quantized HF load path (#305 phase 2).
///
/// `mlx_lm convert -q` ships packed-uint32 weights + `.scales`/`.biases`
/// peers, self-described by config.json's `quantization` block.
/// `HFModelLoader` must (a) swap each quantized Linear for a real
/// `QuantizedLinear`, (b) dequantise quantized Embeddings to dense fp32,
/// and (c) produce logits that match BOTH the fp32 master (within int8
/// quantization error) and the in-memory `--quantize` serve path
/// (tightly — identical affine math from the same fp32 weights).
///
/// No-quality-regression rule: this is the automated gate for the
/// quantized HFModel path. It runs on a tiny random-weights checkpoint
/// built in-test — no model download, no multi-GB load.
final class HFQuantizedLoadTests: XCTestCase {

    private func adapter(for config: ModelConfig, names: [String]) -> LoraAdapter {
        let entries = names.map { LoraAdapter.Entry(name: $0,
            loraAShape: [64, 4], loraBShape: [4, 64]) }
        let header = LoraAdapter.Header(rank: 4, alpha: 8, targetSuffixes: ["q_proj"],
            baseLayers: config.nLayers, baseDModel: config.dModel,
            baseCtx: config.contextLength, baseHeads: config.nHeads,
            baseDMlp: config.dMlp, entries: entries)
        return LoraAdapter(header: header, matrices: names.map { _ in
            (Array(repeating: Float(0.01), count: 256),
             Array(repeating: Float(0.02), count: 256), nil)
        })
    }

    func test_subsetAdapter_usesNamesAndPreservesUntargetedLayers() throws {
        var json = configJSON
        json["num_hidden_layers"] = 3
        let cfg = HFConfigConverter.toModelConfig(try HuggingFaceConfig.fromDict(json))
        let model = TinyGPTModelHF(cfg)
        let untouched = model.blocks[1].attn.qProj
        let other = model.blocks[2].attn.vProj
        let named = adapter(for: cfg, names: ["layers.2.self_attn.q_proj", "layers.0.self_attn.q_proj"])
        try LoraAdapterHFReader.apply(named, to: model)
        XCTAssertTrue(model.blocks[0].attn.qProj is LoraLinear)
        XCTAssertTrue(model.blocks[2].attn.qProj is LoraLinear)
        XCTAssertTrue(model.blocks[1].attn.qProj === untouched)
        XCTAssertTrue(model.blocks[2].attn.vProj === other)
        let lastOnly = TinyGPTModelHF(cfg)
        try LoraAdapterHFReader.apply(adapter(for: cfg,
            names: ["layers.2.self_attn.q_proj"]), to: lastOnly)
        XCTAssertFalse(lastOnly.blocks[0].attn.qProj is LoraLinear)
        XCTAssertTrue(lastOnly.blocks[2].attn.qProj is LoraLinear)
    }

    func test_invalidAdapter_rejectsAtomically() throws {
        let cfg = HFConfigConverter.toModelConfig(try HuggingFaceConfig.fromDict(configJSON))
        for bad in ["layers.9.self_attn.q_proj", "layers..1.self_attn.q_proj", "layers.1.mlp.q_proj"] {
            let model = TinyGPTModelHF(cfg)
            let original = model.blocks[0].attn.qProj
            XCTAssertThrowsError(try LoraAdapterHFReader.apply(adapter(for: cfg,
                names: ["layers.0.self_attn.q_proj", bad]), to: model))
            XCTAssertTrue(model.blocks[0].attn.qProj === original)
        }
        let model = TinyGPTModelHF(cfg)
        var malformed = adapter(for: cfg, names: ["layers.1.self_attn.q_proj"])
        malformed.matrices[0].loraB[0] = .nan
        XCTAssertThrowsError(try LoraAdapterHFReader.apply(malformed, to: model))
        XCTAssertFalse(model.blocks[1].attn.qProj is LoraLinear)
        malformed = adapter(for: cfg, names: ["layers.1.self_attn.q_proj", "layers.1.self_attn.q_proj"])
        XCTAssertThrowsError(try LoraAdapterHFReader.apply(malformed, to: model))
    }

    func test_quantizedSubsetAdapter_roundtripAndFreeze() throws {
        var json = configJSON
        json["quantization"] = ["group_size": 64, "bits": 4]
        let directory = try writeCheckpoint(
            tensors: quantizedTensors(randomWeights(), bits: 4, groupSize: 64), config: json)
        defer { try? FileManager.default.removeItem(at: directory) }
        let loaded = try HFModelLoader.load(from: directory)
        let named = adapter(for: loaded.config, names: ["layers.1.self_attn.q_proj"])
        let input = MLXArray([Int32]([1, 5, 7]), [1, 3])
        try LoraAdapterHFReader.apply(named, to: loaded.model)
        LoraInjectionHF.freezeBase(loaded.model)
        let keys = Set(loaded.model.trainableParameters().flattened().map(\.0))
        XCTAssertEqual(keys, ["layers.1.self_attn.q_proj.loraA", "layers.1.self_attn.q_proj.loraB"])
        let expected = loaded.model(input)
        eval(expected)
        let path = directory.appendingPathComponent("subset.lora")
        try LoraAdapterHFWriter.write(model: loaded.model, baseConfig: loaded.config,
            loraConfig: LoraConfig(rank: 4, alpha: 8, targetSuffixes: ["q_proj"]),
            finalLoss: nil, to: path)
        let restored = try HFModelLoader.load(from: directory)
        try LoraAdapterHFReader.apply(LoraAdapterReader.read(path), to: restored.model)
        let actual = restored.model(input)
        XCTAssertLessThan((actual - expected).abs().max().item(Float.self), 1e-4)
        XCTAssertTrue(restored.model.blocks[0].attn.qProj is QuantizedLinear)
    }

    func test_quantizedLoraWrapping_preservesEffectiveBaseAndAdapter() {
        MLXRandom.seed(209)
        let dense = Linear(weight: MLXRandom.normal([32, 64]) * 0.08,
                           bias: MLXRandom.normal([32]) * 0.01)
        let quantized = QuantizedLinear(dense, groupSize: 64, bits: 4)
        let x = MLXRandom.normal([1, 3, 64])
        let fresh = LoraLinear(wrapping: quantized, rank: 4, alpha: 8)
        XCTAssertEqual(fresh.loraA.shape, [64, 4])
        XCTAssertLessThan((fresh(x) - quantized(x)).abs().max().item(Float.self), 1e-4)

        let a = MLXRandom.normal([64, 4]) * 0.02
        let b = MLXRandom.normal([4, 32]) * 0.02
        let restored = LoraLinear(wrapping: quantized, loraA: a, loraB: b,
                                  rank: 4, alpha: 8)
        let expected = quantized(x) + matmul(matmul(x, a), b) * MLXArray(Float(2))
        XCTAssertLessThan((restored(x) - expected).abs().max().item(Float.self), 1e-4)

        let dora = DoraLinear(wrapping: quantized, rank: 4, alpha: 8)
        XCTAssertEqual(dora.loraA.shape, [64, 4])
        XCTAssertLessThan((dora(x) - quantized(x)).abs().max().item(Float.self), 1e-4)
    }

    func test_hfNormEpsilon_reachesEveryQwenNorm() throws {
        var json = configJSON
        json["architectures"] = ["Qwen3ForCausalLM"]
        json["rms_norm_eps"] = 0.003
        let hf = try HuggingFaceConfig.fromDict(json)
        let cfg = HFConfigConverter.toModelConfig(hf)
        let model = TinyGPTModelHF(cfg)
        XCTAssertEqual(cfg.normEps, 0.003)
        XCTAssertEqual(model.lnFinal.eps, cfg.normEps)
        for block in model.blocks {
            XCTAssertEqual(block.ln1.eps, cfg.normEps)
            XCTAssertEqual(block.ln2.eps, cfg.normEps)
            XCTAssertEqual(block.attn.qNorm?.eps, cfg.normEps)
            XCTAssertEqual(block.attn.kNorm?.eps, cfg.normEps)
        }
        XCTAssertEqual(ModelConfig().normEps, 1e-5)
        XCTAssertEqual(ModelConfig().qkNormEps, 1e-6)
    }

    // Tiny Llama-style config. Every quantized axis (Linear input dims,
    // embedding dims) is a multiple of the group size (64).
    private let configJSON: [String: Any] = [
        "architectures": ["LlamaForCausalLM"],
        "vocab_size": 96,
        "hidden_size": 64,
        "intermediate_size": 128,
        "num_hidden_layers": 2,
        "num_attention_heads": 2,
        "num_key_value_heads": 1,
        "max_position_embeddings": 32,
        "rms_norm_eps": 1e-5,
        "rope_theta": 10000.0,
        "hidden_act": "silu",
        "tie_word_embeddings": false,
        "torch_dtype": "float32",
    ]

    /// Full random fp32 tensor set for the config above, HF naming.
    private func randomWeights() -> [String: MLXArray] {
        MLXRandom.seed(0x5305)
        var t: [String: MLXArray] = [:]
        func w(_ name: String, _ shape: [Int]) {
            t[name] = MLXRandom.normal(shape) * 0.08
        }
        w("model.embed_tokens.weight", [96, 64])
        for i in 0..<2 {
            let p = "model.layers.\(i)."
            t[p + "input_layernorm.weight"] = MLXRandom.uniform(low: 0.8, high: 1.2, [64])
            t[p + "post_attention_layernorm.weight"] = MLXRandom.uniform(low: 0.8, high: 1.2, [64])
            w(p + "self_attn.q_proj.weight", [64, 64])
            w(p + "self_attn.k_proj.weight", [32, 64])
            w(p + "self_attn.v_proj.weight", [32, 64])
            w(p + "self_attn.o_proj.weight", [64, 64])
            w(p + "mlp.gate_proj.weight", [128, 64])
            w(p + "mlp.up_proj.weight", [128, 64])
            w(p + "mlp.down_proj.weight", [64, 128])
        }
        t["model.norm.weight"] = MLXRandom.uniform(low: 0.8, high: 1.2, [64])
        w("lm_head.weight", [96, 64])
        return t
    }

    /// Write a config.json + model.safetensors checkpoint dir in tmp.
    private func writeCheckpoint(tensors: [String: MLXArray],
                                 config: [String: Any]) throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("hf-quant-gate-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let cfgData = try JSONSerialization.data(withJSONObject: config)
        try cfgData.write(to: dir.appendingPathComponent("config.json"))
        try MLX.save(arrays: tensors, url: dir.appendingPathComponent("model.safetensors"))
        return dir
    }

    /// MLX-pack every Linear/Embedding weight the way `mlx_lm convert -q`
    /// does; norms pass through fp32.
    private func quantizedTensors(_ fp: [String: MLXArray],
                                  bits: Int, groupSize: Int) -> [String: MLXArray] {
        var out: [String: MLXArray] = [:]
        for (name, w) in fp {
            let isTarget = name.hasSuffix(".weight") && w.ndim == 2
            if isTarget {
                let (wq, scales, biases) = MLX.quantized(
                    w, groupSize: groupSize, bits: bits)
                let base = String(name.dropLast(".weight".count))
                out[base + ".weight"] = wq
                out[base + ".scales"] = scales
                if let biases { out[base + ".biases"] = biases }
            } else {
                out[name] = w
            }
        }
        return out
    }

    private func cosine(_ a: MLXArray, _ b: MLXArray) -> Float {
        let x = a.flattened().asType(.float32)
        let y = b.flattened().asType(.float32)
        let num = (x * y).sum()
        let den = MLX.sqrt((x * x).sum()) * MLX.sqrt((y * y).sum())
        return (num / den).item(Float.self)
    }

    /// int8 g64 — the shipping default ("free lunch" per the serve
    /// measurements). Gates: structure, fp32 fidelity, serve-path parity.
    func test_quantizedLoad_int8_matchesFp32AndServePath() throws {
        let fp = randomWeights()
        let fpDir = try writeCheckpoint(tensors: fp, config: configJSON)
        defer { try? FileManager.default.removeItem(at: fpDir) }

        var qConfig = configJSON
        qConfig["quantization"] = ["group_size": 64, "bits": 8]
        let qDir = try writeCheckpoint(
            tensors: quantizedTensors(fp, bits: 8, groupSize: 64), config: qConfig)
        defer { try? FileManager.default.removeItem(at: qDir) }

        let fpLoad = try HFModelLoader.load(from: fpDir)
        XCTAssertNil(fpLoad.quantization, "fp checkpoint must not report quantization")
        let qLoad = try HFModelLoader.load(from: qDir)
        XCTAssertEqual(qLoad.quantization?.bits, 8)
        XCTAssertEqual(qLoad.quantization?.groupSize, 64)

        // Structure: Linears swapped for QuantizedLinear; embedding stays
        // a plain (dequantised-dense) Embedding.
        XCTAssertTrue(qLoad.model.blocks[0].attn.qProj is QuantizedLinear)
        XCTAssertTrue(qLoad.model.blocks[1].attn.oProj is QuantizedLinear)
        XCTAssertTrue(qLoad.model.blocks[1].mlp.fcDown is QuantizedLinear)
        XCTAssertTrue(qLoad.model.lmHead is QuantizedLinear)
        XCTAssertFalse(qLoad.model.tokenEmbedding is QuantizedEmbedding)

        let idx = MLXArray([Int32]([1, 5, 9, 42, 7, 88, 3, 64]), [1, 8])
        let fpLogits = fpLoad.model(idx)
        let qLogits = qLoad.model(idx)
        eval(fpLogits, qLogits)

        // Gate 1: int8 g64 vs the fp32 master.
        let cosFp = cosine(fpLogits, qLogits)
        XCTAssertGreaterThanOrEqual(
            cosFp, 0.999, "quantized-load logits drifted from fp32 (cos=\(cosFp))")

        // Gate 2: parity with the serve-path in-memory MLXNN.quantize —
        // same affine int8 math over the same fp32 weights, so the two
        // quantized paths must agree tightly.
        MLXNN.quantize(model: fpLoad.model, groupSize: 64, bits: 8)
        let serveLogits = fpLoad.model(idx)
        eval(serveLogits)
        let cosServe = cosine(serveLogits, qLogits)
        XCTAssertGreaterThanOrEqual(
            cosServe, 0.9999,
            "native packed load disagrees with in-memory quantize (cos=\(cosServe))")
        let maxAbs = MLX.abs(serveLogits - qLogits).max().item(Float.self)
        XCTAssertLessThanOrEqual(
            maxAbs, 1e-3,
            "native packed load disagrees with in-memory quantize (maxAbs=\(maxAbs))")
    }

    /// int4 g64 also loads + runs (it fails quality gates on real planners,
    /// but the loader must still handle the format — smoke only).
    func test_quantizedLoad_int4_loadsAndRuns() throws {
        let fp = randomWeights()
        var qConfig = configJSON
        qConfig["quantization"] = ["group_size": 64, "bits": 4]
        let qDir = try writeCheckpoint(
            tensors: quantizedTensors(fp, bits: 4, groupSize: 64), config: qConfig)
        defer { try? FileManager.default.removeItem(at: qDir) }

        let qLoad = try HFModelLoader.load(from: qDir)
        XCTAssertEqual(qLoad.quantization?.bits, 4)
        XCTAssertTrue(qLoad.model.blocks[0].mlp.fcGate is QuantizedLinear)

        let idx = MLXArray([Int32]([2, 4, 8, 16]), [1, 4])
        let logits = qLoad.model(idx)
        eval(logits)
        let maxAbs = MLX.abs(logits).max().item(Float.self)
        XCTAssertTrue(maxAbs.isFinite, "int4 logits are not finite")
    }
}
