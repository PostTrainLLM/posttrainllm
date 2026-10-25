import Foundation
import MLX
import MLXNN
import TinyGPTIO

/// LoRA injection for TinyGPTModelHF. Parallel to LoraInjection but
/// uses the HF-native @ModuleInfo keys ("layers", "self_attn", etc.)
/// when building the Module.update NestedDictionary. Same on-disk
/// adapter format as the from-scratch path so the same .lora files
/// load against either model class.
public enum LoraInjectionHF {

    @discardableResult
    public static func inject(_ model: TinyGPTModelHF, config: LoraConfig) -> TinyGPTModelHF {
        let suffixes = Set(config.targetSuffixes)
        var layersList: [NestedItem<String, Module>] = []
        for block in model.blocks {
            var attnEntries: [String: NestedItem<String, Module>] = [:]
            var mlpEntries: [String: NestedItem<String, Module>] = [:]
            // Build the adapter via the shared factory so DoRA / VeRA /
            // PISSA / LoftQ / etc. all flow through one path.
            if suffixes.contains("q_proj") {
                attnEntries["q_proj"] = .value(makeAdapterLinear(wrapping: block.attn.qProj, config: config))
            }
            if suffixes.contains("k_proj") {
                attnEntries["k_proj"] = .value(makeAdapterLinear(wrapping: block.attn.kProj, config: config))
            }
            if suffixes.contains("v_proj") {
                attnEntries["v_proj"] = .value(makeAdapterLinear(wrapping: block.attn.vProj, config: config))
            }
            if suffixes.contains("o_proj") {
                attnEntries["o_proj"] = .value(makeAdapterLinear(wrapping: block.attn.oProj, config: config))
            }
            // HF MLP is SwiGLU — the targetable Linears are gate_proj /
            // up_proj / down_proj. Suffixes referencing fc_in / fc_out
            // (from-scratch naming) silently no-op for HF models.
            if suffixes.contains("gate_proj") {
                mlpEntries["gate_proj"] = .value(makeAdapterLinear(wrapping: block.mlp.fcGate, config: config))
            }
            if suffixes.contains("up_proj") {
                mlpEntries["up_proj"] = .value(makeAdapterLinear(wrapping: block.mlp.fcUp, config: config))
            }
            if suffixes.contains("down_proj") {
                mlpEntries["down_proj"] = .value(makeAdapterLinear(wrapping: block.mlp.fcDown, config: config))
            }

            var blockChildren: [String: NestedItem<String, Module>] = [:]
            if !attnEntries.isEmpty { blockChildren["self_attn"] = .dictionary(attnEntries) }
            if !mlpEntries.isEmpty { blockChildren["mlp"] = .dictionary(mlpEntries) }
            layersList.append(.dictionary(blockChildren))
        }
        var root = NestedDictionary<String, Module>()
        root["layers"] = .array(layersList)
        model.update(modules: root)
        return model
    }

    public static func trainableParamCount(in model: TinyGPTModelHF) -> Int {
        var n = 0
        for block in model.blocks {
            let leaves: [Linear] = [block.attn.qProj, block.attn.kProj,
                                    block.attn.vProj, block.attn.oProj,
                                    block.mlp.fcGate, block.mlp.fcUp, block.mlp.fcDown]
            for layer in leaves {
                if let lora = layer as? LoraLinear {
                    n += trainableElementCount(of: lora)
                } else if let dora = layer as? DoraLinear {
                    n += dora.loraA.shape.reduce(1, *) + dora.loraB.shape.reduce(1, *)
                        + dora.m.shape.reduce(1, *)
                }
            }
        }
        return n
    }

    public static func freezeBase(_ model: TinyGPTModelHF) {
        model.freeze(recursive: true)
        for block in model.blocks {
            let leaves: [Linear] = [block.attn.qProj, block.attn.kProj,
                                    block.attn.vProj, block.attn.oProj,
                                    block.mlp.fcGate, block.mlp.fcUp, block.mlp.fcDown]
            for layer in leaves {
                if let lora = layer as? LoraLinear {
                    unfreezeLoraLinear(lora)
                } else if let dora = layer as? DoraLinear {
                    dora.unfreeze(recursive: false, keys: ["loraA", "loraB", "m"])
                }
            }
        }
    }
}

/// LoRA-adapter writer for the HF model. Walks the targeted Linears
/// (which are LoraLinear instances after injection) and saves their
/// A/B matrices. Uses the same `.lora` format the from-scratch path
/// uses, with the architecture-validation header field carrying the
/// HF arch instead.
public enum LoraAdapterHFWriter {
    public static func write(model: TinyGPTModelHF, baseConfig: ModelConfig,
                              loraConfig: LoraConfig, finalLoss: Float?,
                              to url: URL) throws {
        var entries: [LoraAdapter.Entry] = []
        var matrices: [(loraA: [Float], loraB: [Float], m: [Float]?)] = []

        for (i, block) in model.blocks.enumerated() {
            let attnLinears: [(String, Linear)] = [
                ("self_attn.q_proj", block.attn.qProj),
                ("self_attn.k_proj", block.attn.kProj),
                ("self_attn.v_proj", block.attn.vProj),
                ("self_attn.o_proj", block.attn.oProj),
            ]
            let mlpLinears: [(String, Linear)] = [
                ("mlp.gate_proj", block.mlp.fcGate),
                ("mlp.up_proj",   block.mlp.fcUp),
                ("mlp.down_proj", block.mlp.fcDown),
            ]
            for (suffix, lin) in attnLinears + mlpLinears {
                // Accept both LoraLinear and DoraLinear. v2 format
                // preserves DoRA's magnitude vector (loraMShape + m
                // bytes after loraB).
                let lA: MLXArray
                let lB: MLXArray
                var mFloats: [Float]? = nil
                var mShape: [Int]? = nil
                if let lora = lin as? LoraLinear {
                    lA = lora.loraA; lB = lora.loraB
                } else if let dora = lin as? DoraLinear {
                    lA = dora.loraA; lB = dora.loraB
                    eval(dora.m)
                    mFloats = dora.m.asArray(Float.self)
                    mShape = dora.m.shape
                } else { continue }
                eval(lA, lB)
                entries.append(.init(name: "layers.\(i).\(suffix)",
                                     loraAShape: lA.shape,
                                     loraBShape: lB.shape,
                                     loraMShape: mShape))
                matrices.append((lA.asArray(Float.self),
                                 lB.asArray(Float.self),
                                 mFloats))
            }
        }
        let header = LoraAdapter.Header(
            rank: loraConfig.rank, alpha: loraConfig.alpha,
            targetSuffixes: loraConfig.targetSuffixes,
            baseLayers: baseConfig.nLayers, baseDModel: baseConfig.dModel,
            baseCtx: baseConfig.contextLength, baseHeads: baseConfig.nHeads,
            baseDMlp: baseConfig.dMlp,
            entries: entries,
            savedAt: ISO8601DateFormatter().string(from: Date()),
            finalLoss: finalLoss
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        let headerData = try encoder.encode(header)
        var out = Data()
        out.append(contentsOf: LoraAdapterFormat.magic)
        var v = LoraAdapterFormat.currentVersion.littleEndian
        withUnsafeBytes(of: &v) { out.append(contentsOf: $0) }
        var hl = UInt32(headerData.count).littleEndian
        withUnsafeBytes(of: &hl) { out.append(contentsOf: $0) }
        out.append(headerData)
        for (a, b, m) in matrices {
            a.withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
            b.withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
            if let m {
                m.withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
            }
        }
        try out.write(to: url, options: .atomic)
    }
}

public enum LoraAdapterHFReader {
    private typealias Matrices = (loraA: [Float], loraB: [Float], m: [Float]?)
    private struct Plan {
        let entry: LoraAdapter.Entry
        let values: Matrices
        let base: Linear
    }

    private static func invalid(_ message: String) -> NSError {
        NSError(domain: "TinyGPTLoRA", code: 4,
                userInfo: [NSLocalizedDescriptionKey: message])
    }

    private static func projection(_ entry: LoraAdapter.Entry,
                                   header: LoraAdapter.Header,
                                   model: TinyGPTModelHF) throws -> Linear {
        let parts = entry.name.split(separator: ".").map(String.init)
        guard parts.count == 4, parts[0] == "layers",
              parts.joined(separator: ".") == entry.name,
              let layer = Int(parts[1]), String(layer) == parts[1],
              model.blocks.indices.contains(layer),
              header.targetSuffixes.contains(parts[3]) else {
            throw invalid("invalid adapter projection: \(entry.name)")
        }
        let block = model.blocks[layer]
        let projections: [String: Linear] = [
            "self_attn.q_proj": block.attn.qProj, "self_attn.k_proj": block.attn.kProj,
            "self_attn.v_proj": block.attn.vProj, "self_attn.o_proj": block.attn.oProj,
            "mlp.gate_proj": block.mlp.fcGate, "mlp.up_proj": block.mlp.fcUp,
            "mlp.down_proj": block.mlp.fcDown,
        ]
        guard let base = projections[parts[2] + "." + parts[3]],
              !(base is LoraLinear), !(base is DoraLinear),
              !(base is StackedLoraLinear) else {
            throw invalid("unknown or already adapted projection: \(entry.name)")
        }
        return base
    }

    private static func validate(_ plan: Plan, rank: Int) throws {
        let (outFeatures, inFeatures) = plan.base.shape
        let e = plan.entry, v = plan.values
        guard e.loraAShape == [inFeatures, rank],
              e.loraBShape == [rank, outFeatures],
              v.loraA.count == inFeatures * rank,
              v.loraB.count == rank * outFeatures,
              v.loraA.allSatisfy({ $0.isFinite }),
              v.loraB.allSatisfy({ $0.isFinite }) else {
            throw invalid("adapter shape or values mismatch: \(e.name)")
        }
        if let magnitude = v.m {
            guard e.loraMShape == [outFeatures], magnitude.count == outFeatures,
                  magnitude.allSatisfy({ $0.isFinite }) else {
                throw invalid("invalid adapter magnitude: \(e.name)")
            }
        } else if e.loraMShape != nil {
            throw invalid("adapter magnitude is missing: \(e.name)")
        }
    }

    private static func replacement(_ plan: Plan, header: LoraAdapter.Header) throws -> Module {
        let a = MLXArray(plan.values.loraA, plan.entry.loraAShape)
        let b = MLXArray(plan.values.loraB, plan.entry.loraBShape)
        if let magnitude = plan.values.m {
            let layer = DoraLinear(wrapping: plan.base, rank: header.rank, alpha: header.alpha)
            let updates: [String: MLXArray] = ["loraA": a, "loraB": b, "m": MLXArray(magnitude)]
            try layer.update(parameters: ModuleParameters.unflattened(updates), verify: [])
            return layer
        }
        return LoraLinear(wrapping: plan.base, loraA: a, loraB: b,
                          rank: header.rank, alpha: header.alpha)
    }

    /// Load named projections, including subset-layer adapters. Validate every
    /// entry before replacing anything, so a malformed import is atomic.
    public static func apply(_ adapter: LoraAdapter, to model: TinyGPTModelHF) throws {
        let h = adapter.header, cfg = model.config
        guard h.baseLayers == cfg.nLayers, h.baseDModel == cfg.dModel,
              h.baseCtx == cfg.contextLength, h.baseHeads == cfg.nHeads,
              h.baseDMlp == cfg.dMlp else {
            throw invalid("adapter base config doesn't match loaded HF model")
        }
        guard h.rank > 0, h.rank <= 4096, h.alpha.isFinite,
              !h.entries.isEmpty, h.entries.count == adapter.matrices.count,
              Set(h.entries.map(\.name)).count == h.entries.count else {
            throw invalid("invalid or duplicate adapter entries")
        }
        let magnitudes = adapter.matrices.map { $0.m != nil }
        guard magnitudes.allSatisfy({ $0 }) || magnitudes.allSatisfy({ !$0 }) else {
            throw invalid("mixed DoRA/LoRA entries are not supported")
        }
        let plans = try zip(h.entries, adapter.matrices).map { entry, values in
            let plan = Plan(entry: entry, values: values,
                            base: try projection(entry, header: h, model: model))
            try validate(plan, rank: h.rank)
            return plan
        }
        let swaps = try plans.map { plan in
            (plan.entry.name, try replacement(plan, header: h))
        }
        // MLX's sparse unflattened arrays contain .none, which cannot update
        // a module array. Untargeted layers must be explicit empty dictionaries.
        var layers: [NestedItem<String, Module>] = []
        for i in model.blocks.indices {
            var children: [String: NestedItem<String, Module>] = [:]
            for group in ["self_attn", "mlp"] {
                let prefix = "layers.\(i).\(group)."
                let values = swaps.filter { $0.0.hasPrefix(prefix) }
                if !values.isEmpty {
                    children[group] = .dictionary(Dictionary(uniqueKeysWithValues:
                        values.map { (String($0.0.dropFirst(prefix.count)), .value($0.1)) }))
                }
            }
            layers.append(.dictionary(children))
        }
        var modules = ModuleChildren()
        modules["layers"] = .array(layers)
        model.update(modules: modules)
    }
}
