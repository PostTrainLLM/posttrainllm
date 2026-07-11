import Foundation
import TinyGPTIO
import MLX
import TinyGPTModel

/// Export posttrainllm artifacts into a directory that Python MLX / MLX-Swift
/// callers can load without understanding `.tinygpt` or `.lora`.
enum ExportMLX {
    static func run(args: [String]) {
        var inputPath: String?
        var outDir: String?
        var hfNames = false

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--out":
                outDir = requireValue(args, &i)
            case "--hf-names":
                hfNames = true
                i += 1
            case "-h", "--help":
                exitUsage(0)
            default:
                if args[i].hasPrefix("-") {
                    fputs("unknown flag: \(args[i])\n", stderr)
                    exitUsage()
                }
                inputPath = args[i]
                i += 1
            }
        }

        guard let inputPath else {
            fputs("missing <model.tinygpt|adapter.lora|hf-dir>\n", stderr)
            exitUsage()
        }
        guard let outDir else {
            fputs("--out <dir> required\n", stderr)
            exitUsage()
        }

        let inputURL = URL(fileURLWithPath: inputPath)
        let outURL = URL(fileURLWithPath: outDir)

        do {
            try prepareEmptyOutputDirectory(outURL)
            if isAdapterFile(inputURL) {
                try exportAdapter(inputURL, to: outURL)
            } else if isDirectory(inputURL) {
                try exportHFDirectory(inputURL, to: outURL)
            } else {
                try exportposttrainllm(inputPath, to: outURL, hfNames: hfNames)
            }
        } catch {
            fputs("export-mlx failed: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func exportposttrainllm(_ path: String, to outURL: URL, hfNames: Bool) throws {
        let load = try ModelLoader.load(path)
        guard case .fromScratch(let model) = load.model else {
            throw NSError(domain: "ExportMLX", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "expected a posttrainllm from-scratch checkpoint",
            ])
        }

        var entries: [SafetensorsWriter.Entry] = []
        for (name, arr) in model.parameters().flattened() {
            MLX.eval(arr)
            entries.append(SafetensorsWriter.Entry(
                name: hfNames ? remapToHFLlama(name) : name,
                data: arr.asArray(Float.self),
                shape: arr.shape
            ))
        }

        try SafetensorsWriter.write(entries: entries, to: outURL.appendingPathComponent("model.safetensors"))
        try writeJSON(configJSON(load.config, hfNames: hfNames),
                      to: outURL.appendingPathComponent("config.json"))
        try writeJSON(generationConfigJSON(load.config),
                      to: outURL.appendingPathComponent("generation_config.json"))
        try writeTokenizerSidecars(config: load.config, tokenizerDir: load.hfTokenizerDir, outURL: outURL)
        try writeLoaderScript(to: outURL)

        let metadata: [String: Any] = [
            "format": "posttrainllm-mlx-export",
            "version": 1,
            "artifact_type": "full_model",
            "source": URL(fileURLWithPath: path).path,
            "weights": "model.safetensors",
            "weight_naming": hfNames ? "hf-llama" : "posttrainllm-native",
            "mlx_lm_compatible": false,
            "loader": "mlx_load.py",
            "note": "posttrainllm-native architectures need a posttrainllm-aware MLX module; mlx_load.py loads arrays/config for integration.",
        ]
        try writeJSON(metadata, to: outURL.appendingPathComponent("posttrainllm_mlx_export.json"))

        printSummary(kind: "full model", outURL: outURL, tensors: entries.count,
                     bytes: entries.reduce(0) { $0 + $1.data.count * 4 })
    }

    private static func exportAdapter(_ url: URL, to outURL: URL) throws {
        let adapter = try LoraAdapterReader.read(url)
        var entries: [SafetensorsWriter.Entry] = []
        for (idx, entry) in adapter.header.entries.enumerated() {
            let matrices = adapter.matrices[idx]
            entries.append(.init(name: "\(entry.name).loraA",
                                 data: matrices.loraA,
                                 shape: entry.loraAShape))
            entries.append(.init(name: "\(entry.name).loraB",
                                 data: matrices.loraB,
                                 shape: entry.loraBShape))
            if let m = matrices.m, let shape = entry.loraMShape {
                entries.append(.init(name: "\(entry.name).doraM", data: m, shape: shape))
            }
        }

        try SafetensorsWriter.write(entries: entries, to: outURL.appendingPathComponent("adapters.safetensors"))
        try writeJSON(adapterConfigJSON(adapter), to: outURL.appendingPathComponent("adapter_config.json"))
        try writeLoaderScript(to: outURL)

        let metadata: [String: Any] = [
            "format": "posttrainllm-mlx-export",
            "version": 1,
            "artifact_type": "adapter",
            "source": url.path,
            "weights": "adapters.safetensors",
            "adapter_config": "adapter_config.json",
            "rank": adapter.header.rank,
            "alpha": adapter.header.alpha,
            "entries": adapter.header.entries.count,
            "mlx_lm_compatible": false,
            "loader": "mlx_load.py",
            "note": "Adapter tensor names preserve posttrainllm's module path plus .loraA/.loraB/.doraM suffixes.",
        ]
        try writeJSON(metadata, to: outURL.appendingPathComponent("posttrainllm_mlx_export.json"))

        printSummary(kind: "adapter", outURL: outURL, tensors: entries.count,
                     bytes: entries.reduce(0) { $0 + $1.data.count * 4 })
    }

    private static func exportHFDirectory(_ inputURL: URL, to outURL: URL) throws {
        let fm = FileManager.default
        let children = try fm.contentsOfDirectory(at: inputURL, includingPropertiesForKeys: nil)
        for child in children {
            try fm.copyItem(at: child, to: outURL.appendingPathComponent(child.lastPathComponent))
        }
        try writeLoaderScript(to: outURL)
        try writeJSON([
            "format": "posttrainllm-mlx-export",
            "version": 1,
            "artifact_type": "hf_directory",
            "source": inputURL.path,
            "mlx_lm_compatible": true,
            "loader": "mlx_load.py",
            "note": "HF/MLX model directory copied as-is; use mlx_lm.load or mlx_load.py.",
        ], to: outURL.appendingPathComponent("posttrainllm_mlx_export.json"))

        print("""

        posttrainllm - MLX export
        --------------------
        kind:             HF/MLX directory
        out:              \(outURL.path)
        mlx-lm:           compatible when the original architecture is supported by mlx-lm
        """)
    }

    private static func configJSON(_ cfg: ModelConfig, hfNames: Bool) -> [String: Any] {
        var obj: [String: Any] = [
            "architectures": ["TinyGPTForCausalLM"],
            "model_type": "posttrainllm",
            "posttrainllm_config_version": 1,
            "weight_naming": hfNames ? "hf-llama" : "posttrainllm-native",
            "model_name": cfg.modelName,
            "vocab_size": cfg.vocabSize,
            "hidden_size": cfg.dModel,
            "intermediate_size": cfg.dMlp,
            "num_hidden_layers": cfg.nLayers,
            "num_attention_heads": cfg.nHeads,
            "num_key_value_heads": cfg.nKvHeads,
            "head_dim": cfg.headDim,
            "max_position_embeddings": cfg.contextLength,
            "tie_word_embeddings": cfg.tieEmbeddings,
            "torch_dtype": cfg.dtype,
            "use_rope": cfg.useRoPE,
            "rope_theta": cfg.ropeBase,
            "use_rms_norm": cfg.useRMSNorm,
            "use_swiglu": cfg.useSwiGLU,
            "attention_bias": cfg.attnBias,
            "n_experts": cfg.nExperts,
            "moe_top_k": cfg.moeTopK,
            "load_balance_weight": cfg.loadBalanceWeight,
            "use_alibi": cfg.useALiBi,
            "use_mod": cfg.useMoD,
            "use_differential_attention": cfg.useDifferentialAttention,
            "use_yoco": cfg.useYOCO,
            "use_embedding_rms_norm": cfg.useEmbeddingRMSNorm,
            "use_qk_norm": cfg.useQKNorm,
        ]
        if let v = cfg.tokenizerSource { obj["tokenizer_source"] = v }
        if let v = cfg.slidingWindow { obj["sliding_window"] = v }
        if let v = cfg.kviBits { obj["kivi_bits"] = v }
        if let v = cfg.streamingSink { obj["streaming_sink"] = v }
        if let v = cfg.streamingWindow { obj["streaming_window"] = v }
        if let v = cfg.qatBits { obj["qat_bits"] = v }
        return obj
    }

    private static func generationConfigJSON(_ cfg: ModelConfig) -> [String: Any] {
        [
            "max_length": cfg.contextLength,
            "do_sample": true,
            "temperature": 0.8,
            "top_p": 0.95,
        ]
    }

    private static func adapterConfigJSON(_ adapter: LoraAdapter) -> [String: Any] {
        let h = adapter.header
        return [
            "peft_type": adapter.matrices.allSatisfy { $0.m != nil } ? "DORA" : "LORA",
            "format": "posttrainllm-lora",
            "rank": h.rank,
            "alpha": h.alpha,
            "target_modules": h.targetSuffixes,
            "base": [
                "num_hidden_layers": h.baseLayers,
                "hidden_size": h.baseDModel,
                "max_position_embeddings": h.baseCtx,
                "num_attention_heads": h.baseHeads,
                "intermediate_size": h.baseDMlp,
            ],
            "entries": h.entries.map { e in
                [
                    "name": e.name,
                    "lora_a": "\(e.name).loraA",
                    "lora_b": "\(e.name).loraB",
                    "dora_m": e.loraMShape == nil ? NSNull() : "\(e.name).doraM",
                    "lora_a_shape": e.loraAShape,
                    "lora_b_shape": e.loraBShape,
                    "dora_m_shape": e.loraMShape as Any? ?? NSNull(),
                ] as [String: Any]
            },
        ]
    }

    private static func writeTokenizerSidecars(config cfg: ModelConfig, tokenizerDir: URL?, outURL: URL) throws {
        if let tokenizerDir {
            for name in ["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                         "added_tokens.json", "vocab.json", "merges.txt"] {
                let src = tokenizerDir.appendingPathComponent(name)
                guard FileManager.default.fileExists(atPath: src.path) else { continue }
                try FileManager.default.copyItem(at: src, to: outURL.appendingPathComponent(name))
            }
            return
        }

        try writeJSON([
            "type": "byte",
            "vocab_size": cfg.vocabSize,
            "encoding": "utf-8",
            "description": "posttrainllm byte tokenizer: token id equals raw byte value for vocab_size=256.",
        ], to: outURL.appendingPathComponent("posttrainllm_tokenizer.json"))
        try writeJSON([
            "tokenizer_class": "TinyGPTByteTokenizer",
            "model_max_length": cfg.contextLength,
            "vocab_size": cfg.vocabSize,
        ], to: outURL.appendingPathComponent("tokenizer_config.json"))
    }

    private static func writeLoaderScript(to outURL: URL) throws {
        let script = #"""
        # posttrainllm MLX export helper.
        # Usage:
        #   python mlx_load.py /path/to/export-dir
        from __future__ import annotations

        import json
        import sys
        from pathlib import Path

        import mlx.core as mx


        def load_export(path: str | Path):
            root = Path(path)
            meta = json.loads((root / "posttrainllm_mlx_export.json").read_text())
            result = {"metadata": meta}
            config_path = root / "config.json"
            if config_path.exists():
                result["config"] = json.loads(config_path.read_text())
            adapter_config_path = root / "adapter_config.json"
            if adapter_config_path.exists():
                result["adapter_config"] = json.loads(adapter_config_path.read_text())
            weights = meta.get("weights")
            if weights:
                result["weights"] = mx.load(str(root / weights))
            return result


        if __name__ == "__main__":
            export = load_export(sys.argv[1] if len(sys.argv) > 1 else ".")
            arrays = export.get("weights", {})
            print(json.dumps({
                "artifact_type": export["metadata"].get("artifact_type"),
                "tensor_count": len(arrays),
                "sample_keys": list(arrays.keys())[:8],
            }, indent=2))
        """#
        try script.write(to: outURL.appendingPathComponent("mlx_load.py"),
                         atomically: true, encoding: .utf8)
    }

    private static func writeJSON(_ obj: [String: Any], to url: URL) throws {
        let data = try JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: url, options: .atomic)
    }

    private static func prepareEmptyOutputDirectory(_ url: URL) throws {
        let fm = FileManager.default
        if fm.fileExists(atPath: url.path) {
            guard isDirectory(url) else {
                throw NSError(domain: "ExportMLX", code: 2, userInfo: [
                    NSLocalizedDescriptionKey: "\(url.path) exists and is not a directory",
                ])
            }
            let children = try fm.contentsOfDirectory(atPath: url.path)
            guard children.isEmpty else {
                throw NSError(domain: "ExportMLX", code: 3, userInfo: [
                    NSLocalizedDescriptionKey: "\(url.path) already exists and is not empty",
                ])
            }
        } else {
            try fm.createDirectory(at: url, withIntermediateDirectories: true)
        }
    }

    private static func isDirectory(_ url: URL) -> Bool {
        var isDir: ObjCBool = false
        return FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir) && isDir.boolValue
    }

    private static func isAdapterFile(_ url: URL) -> Bool {
        let ext = url.pathExtension.lowercased()
        return ext == "lora" || ext == "tgla"
    }

    private static func remapToHFLlama(_ name: String) -> String {
        var s = name
        s = s.replacingOccurrences(of: "tokenEmbedding.weight", with: "model.embed_tokens.weight")
        s = s.replacingOccurrences(of: "lnFinal.weight", with: "model.norm.weight")
        s = s.replacingOccurrences(of: "lnFinal.bias", with: "model.norm.bias")
        s = s.replacingOccurrences(of: "blocks.", with: "model.layers.")
        s = s.replacingOccurrences(of: ".ln1.", with: ".input_layernorm.")
        s = s.replacingOccurrences(of: ".ln2.", with: ".post_attention_layernorm.")
        s = s.replacingOccurrences(of: ".attn.q_proj", with: ".self_attn.q_proj")
        s = s.replacingOccurrences(of: ".attn.k_proj", with: ".self_attn.k_proj")
        s = s.replacingOccurrences(of: ".attn.v_proj", with: ".self_attn.v_proj")
        s = s.replacingOccurrences(of: ".attn.o_proj", with: ".self_attn.o_proj")
        s = s.replacingOccurrences(of: ".mlp.fc_in", with: ".mlp.gate_proj")
        s = s.replacingOccurrences(of: ".mlp.fc_out", with: ".mlp.down_proj")
        return s
    }

    private static func printSummary(kind: String, outURL: URL, tensors: Int, bytes: Int) {
        print("""

        posttrainllm - MLX export
        --------------------
        kind:             \(kind)
        tensors written:  \(tensors)
        body size:        \(formatBytes(bytes))
        out:              \(outURL.path)

        Load arrays from Python MLX:
          python \(outURL.appendingPathComponent("mlx_load.py").path) \(outURL.path)
        """)
    }

    private static func requireValue(_ args: [String], _ i: inout Int) -> String {
        guard i + 1 < args.count else {
            fputs("\(args[i]) requires a value\n", stderr)
            exitUsage()
        }
        let value = args[i + 1]
        i += 2
        return value
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm export-mlx <model.tinygpt|adapter.lora|adapter.tgla|hf-dir> --out <dir> [--hf-names]

        Export posttrainllm artifacts for MLX integration:
          .tinygpt  -> model.safetensors + config/tokenizer sidecars
          .lora     -> adapters.safetensors + adapter_config.json
          HF dir    -> copied as an MLX/HF directory with posttrainllm metadata

        By default, .tinygpt tensor names stay posttrainllm-native. Pass
        --hf-names to write best-effort HF Llama-style names for tools
        that expect model.layers.* keys.
        """)
        exit(code)
    }
}
