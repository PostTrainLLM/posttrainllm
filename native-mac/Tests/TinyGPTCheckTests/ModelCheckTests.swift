import XCTest
@testable import TinyGPTCheck
import TinyGPTIO

/// Fixture-driven verdict tests — no network, no Metal, no weight files.
/// Every acceptance-criteria scenario from issue #156 gets a case:
/// supported model → evidence-backed yes; image model vs LM runtime →
/// explained mismatch; unfamiliar/inaccessible repo → Unknown + handoff.
final class ModelCheckTests: XCTestCase {

    // MARK: - fixtures

    private func env(ramGB: Int = 48, diskGB: Int = 400,
                     ollama: Bool = false) -> MacEnvironment {
        var runtimes: [ModelCheckReport.RuntimeProbe] = [
            .init(name: "posttrainllm", found: true, version: "0.1.0", detail: "test"),
            .init(name: "python3 ML stack", found: true,
                  version: "mlx==0.28.0, mlx-lm==0.27.0, transformers==4.55.0", detail: "test"),
        ]
        if ollama {
            runtimes.append(.init(name: "ollama", found: true, version: "0.12.0", detail: "test"))
        } else {
            runtimes.append(.init(name: "ollama", found: false, version: nil, detail: "test"))
        }
        return MacEnvironment(
            chip: "Apple M5 Pro", arch: "arm64",
            ramBytes: Int64(ramGB) * 1_073_741_824,
            freeDiskBytes: Int64(diskGB) * 1_073_741_824,
            macOSVersion: "macOS 26.0", source: "detected", runtimes: runtimes)
    }

    private func ref(_ s: String) -> ModelRef { try! ModelRef.parse(s) }

    private func lmInfo(id: String = "Qwen/Qwen3-4B-Instruct-2507",
                        weightBytes: Int64 = 8_000_000_000,
                        archs: [String] = ["Qwen3ForCausalLM"],
                        pipeline: String? = "text-generation") -> (HubModelClient.Info, HuggingFaceConfig) {
        let info = HubModelClient.Info(
            id: id, sha: "abc123",
            tags: ["safetensors", "text-generation"],
            pipelineTag: pipeline, libraryName: "transformers",
            siblings: [
                .init(name: "config.json", size: 1200),
                .init(name: "tokenizer.json", size: 11_000_000),
                .init(name: "model-00001-of-00002.safetensors", size: weightBytes / 2),
                .init(name: "model-00002-of-00002.safetensors", size: weightBytes / 2),
            ],
            safetensorsParams: ["BF16": weightBytes / 2])
        let cfg = try! HuggingFaceConfig.fromDict([
            "architectures": archs,
            "vocab_size": 151_936, "hidden_size": 2560,
            "intermediate_size": 9728, "num_hidden_layers": 36,
            "num_attention_heads": 32, "num_key_value_heads": 8,
            "head_dim": 128, "max_position_embeddings": 262_144,
            "rms_norm_eps": 1e-6, "hidden_act": "silu",
            "rope_theta": 5_000_000.0, "tie_word_embeddings": true,
        ])
        return (info, cfg)
    }

    private func assess(_ info: HubModelClient.Info?,
                        config: HuggingFaceConfig?,
                        fetchIssue: String? = nil,
                        configIssue: String? = nil,
                        env: MacEnvironment? = nil,
                        refString: String? = nil) -> CompatibilityRules.Assessment {
        let refStr = refString ?? "https://huggingface.co/\(info?.id ?? "x/y")"
        return CompatibilityRules.assess(.init(
            ref: ref(refStr), info: info, fetchIssue: fetchIssue,
            config: config, configIssue: configIssue,
            env: env ?? self.env()))
    }

    // MARK: - URL parsing

    func testParseBareId() throws {
        let r = try ModelRef.parse("Qwen/Qwen3-0.6B")
        XCTAssertEqual(r.id, "Qwen/Qwen3-0.6B")
        XCTAssertEqual(r.revision, "main")
        XCTAssertNil(r.filePath)
    }

    func testParseFullURL() throws {
        let r = try ModelRef.parse("https://huggingface.co/mlx-community/Qwen3-4B-4bit")
        XCTAssertEqual(r.id, "mlx-community/Qwen3-4B-4bit")
        XCTAssertEqual(r.revision, "main")
    }

    func testParseTreeRevision() throws {
        let r = try ModelRef.parse("https://huggingface.co/owner/repo/tree/v2.1")
        XCTAssertEqual(r.id, "owner/repo")
        XCTAssertEqual(r.revision, "v2.1")
    }

    func testParseBlobPath() throws {
        let r = try ModelRef.parse("https://huggingface.co/o/r/blob/main/model.safetensors")
        XCTAssertEqual(r.id, "o/r")
        XCTAssertEqual(r.revision, "main")
        XCTAssertEqual(r.filePath, "model.safetensors")
    }

    func testParseHfDotCo() throws {
        XCTAssertEqual(try ModelRef.parse("https://hf.co/a/b").id, "a/b")
    }

    func testRejectDatasetURL() {
        XCTAssertThrowsError(try ModelRef.parse("https://huggingface.co/datasets/a/b")) { e in
            guard case ModelRef.ParseError.notAModelRepo = e else {
                return XCTFail("expected notAModelRepo, got \(e)")
            }
        }
    }

    func testRejectGarbage() {
        XCTAssertThrowsError(try ModelRef.parse("https://example.com/a/b"))
        XCTAssertThrowsError(try ModelRef.parse("justonepart"))
        XCTAssertThrowsError(try ModelRef.parse("   "))
    }

    // MARK: - supported model → expected_to_work

    func testVerifiedModelOnBigRAM() {
        let (info, cfg) = lmInfo()
        let a = assess(info, config: cfg)
        XCTAssertEqual(a.verdict, .expectedToWork)
        XCTAssertEqual(a.checkedPath.status, .expectedToWork)
        XCTAssertFalse(a.evidence.isEmpty)
        XCTAssertFalse(a.nextActions.isEmpty)
    }

    func testVerifiedModelOnSmallRAMNeedsChanges() {
        // 4B bf16 ≈ 8 GB weights → ~16 GB fp32 resident; on 8 GB that's
        // over the line → changesRequired with a quantization route.
        let (info, cfg) = lmInfo()
        let a = assess(info, config: cfg, env: env(ramGB: 8))
        XCTAssertEqual(a.verdict, .changesRequired)
        XCTAssertTrue(a.requiredChanges.contains { $0.kind == "conversion" })
        XCTAssertTrue(a.requiredChanges.allSatisfy { $0.estimate || $0.sizeBytes == nil })
    }

    // MARK: - diffusers → explained mismatch, never "impossible"

    func testDiffusersModelMismatch() {
        var info = HubModelClient.Info(
            id: "black-forest-labs/FLUX.1-dev",
            tags: ["diffusers"], pipelineTag: "text-to-image",
            libraryName: "diffusers",
            siblings: [
                .init(name: "model_index.json", size: 500),
                .init(name: "transformer/diffusion_pytorch_model.safetensors", size: 23_000_000_000),
            ])
        info.gated = true
        let a = assess(info, config: nil)
        XCTAssertEqual(a.verdict, .unsupportedOnCheckedPath)
        XCTAssertTrue(a.checkedPath.detail.contains("mismatch"))
        // Other path documented — "unsupported here" ≠ "impossible on Mac".
        XCTAssertTrue(a.otherPaths.contains { $0.name.contains("diffusers") })
        XCTAssertFalse(a.verdictSummary.lowercased().contains("impossible"))
    }

    // MARK: - unknown cases

    func testUnknownArchitecture() {
        let (info, cfg) = lmInfo(archs: ["FalconForCausalLM"])
        let a = assess(info, config: cfg)
        XCTAssertEqual(a.verdict, .unknown)
        XCTAssertTrue(a.limitations.contains { $0.contains("verified set") })
    }

    func testMoENotDenseLoadable() {
        let (info, cfg) = lmInfo(archs: ["Qwen3MoeForCausalLM"])
        let a = assess(info, config: cfg)
        XCTAssertEqual(a.verdict, .unsupportedOnCheckedPath)
        XCTAssertTrue(a.checkedPath.detail.contains("dense"))
    }

    func testInaccessibleRepoIsUnknown() {
        let a = assess(nil, config: nil, fetchIssue: "model 'x/y' not found on Hugging Face")
        XCTAssertEqual(a.verdict, .unknown)
        XCTAssertTrue(a.limitations.contains { $0.contains("not found") })
        XCTAssertFalse(a.nextActions.isEmpty)
    }

    func testGatedWithoutTokenKeepsUnknownHonest() {
        // API answered but gated → config fetch failed.
        let info = HubModelClient.Info(
            id: "meta-llama/Llama-3.1-8B", gated: true, gatedKind: "auto",
            siblings: [.init(name: "config.json", size: 800)])
        let a = assess(info, config: nil, configIssue: "config.json present but unreadable: needs auth")
        // has config.json sibling but we couldn't read it and there are
        // no weight siblings → no identifiable format → unknown.
        XCTAssertEqual(a.verdict, .unknown)
        XCTAssertTrue(a.limitations.contains { $0.contains("config.json") })
    }

    // MARK: - GGUF

    func testGGUFRepo() {
        let info = HubModelClient.Info(
            id: "bartowski/Qwen3-4B-GGUF",
            siblings: [
                .init(name: "Qwen3-4B-Q4_K_M.gguf", size: 2_500_000_000),
                .init(name: "Qwen3-4B-Q8_0.gguf", size: 4_200_000_000),
            ])
        let a = assess(info, config: nil, env: env(ollama: true))
        XCTAssertEqual(a.verdict, .changesRequired)
        XCTAssertEqual(a.selectedVariant, "Qwen3-4B-Q4_K_M.gguf")
        XCTAssertTrue(a.otherPaths.contains { $0.name.contains("Ollama") && $0.status == .expectedToWork })
    }

    // MARK: - tensor layout + legacy schema

    private func llamaTensorNames() -> [String] {
        var names = ["model.embed_tokens.weight", "model.norm.weight", "lm_head.weight"]
        for i in 0..<4 {
            for p in ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
                      "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj",
                      "input_layernorm", "post_attention_layernorm"] {
                names.append("model.layers.\(i).\(p).weight")
            }
        }
        return names
    }

    func testLayoutLlamaFamily() {
        let l = TensorLayout.assess(names: llamaTensorNames())
        XCTAssertEqual(l.kind, .llamaFamily)
        XCTAssertGreaterThan(l.lmConventionRatio, 0.9)
    }

    func testLayoutMoE() {
        var names = llamaTensorNames()
        names.append(contentsOf: [
            "model.layers.0.mlp.experts.0.gate_proj.weight",
            "model.layers.0.mlp.router.weight",
        ])
        XCTAssertEqual(TensorLayout.assess(names: names).kind, .moe)
    }

    func testLayoutMultimodal() {
        var names = llamaTensorNames()
        names.append(contentsOf: ["vision_tower.vision_model.encoder.layers.0.fc1.weight",
                                  "multi_modal_projector.linear_1.weight"])
        XCTAssertEqual(TensorLayout.assess(names: names).kind, .multimodal)
    }

    func testLayoutEncoderOnly() {
        let names = ["embeddings.word_embeddings.weight", "embeddings.position_embeddings.weight",
                     "encoder.layer.0.attention.self.query.weight", "encoder.layer.0.output.dense.weight",
                     "pooler.dense.weight"]
        XCTAssertEqual(TensorLayout.assess(names: names).kind, .encoderOnly)
    }

    func testLayoutDiffusion() {
        let names = ["unet.down_blocks.0.attentions.0.to_q.weight", "vae.decoder.conv_in.weight",
                     "text_encoder.text_model.encoder.layers.0.mlp.fc1.weight"]
        XCTAssertEqual(TensorLayout.assess(names: names).kind, .diffusion)
    }

    func testLayoutUnknownGPT2Style() {
        // GPT-2 checkpoints use h.N.attn.c_attn — nonstandard naming.
        let names = (0..<4).map { "h.\($0).attn.c_attn.weight" } + ["wte.weight", "ln_f.weight"]
        XCTAssertEqual(TensorLayout.assess(names: names).kind, .unknown)
    }

    func testStructuralRescueUnlistedArch() {
        // An unlisted *ForCausalLM arch whose tensors match the loader's
        // convention upgrades unknown → changesRequired (verify-by-smoke).
        let (info, cfg) = lmInfo(archs: ["SmolLM2ForCausalLM"])
        let layout = TensorLayout.assess(names: llamaTensorNames())
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/smollm2"), info: info, fetchIssue: nil,
            config: cfg, configIssue: nil, tensorLayout: layout, env: env()))
        XCTAssertEqual(a.verdict, .changesRequired)
        XCTAssertTrue(a.checkedPath.detail.contains("hf-load"))
        XCTAssertTrue(a.evidence.contains { $0.kind == "inferred" })
    }

    func testUnlistedArchStillUnknownWithoutLayout() {
        let (info, cfg) = lmInfo(archs: ["NemotronForCausalLM"])
        let a = assess(info, config: cfg)   // no tensorLayout → unknown
        XCTAssertEqual(a.verdict, .unknown)
    }

    func testLegacyKeyNormalization() {
        let raw: [String: Any] = [
            "n_vocab": 50257, "n_embd": 768, "n_layer": 12, "n_head": 12,
            "n_positions": 1024, "activation_function": "gelu_new",
            "layer_norm_epsilon": 1e-5, "architectures": ["GPT2LMHeadModel"],
        ]
        let normalized = ModelCheckService.normalizeLegacyKeys(raw)
        XCTAssertEqual(normalized["vocab_size"] as? Int, 50257)
        XCTAssertEqual(normalized["hidden_size"] as? Int, 768)
        XCTAssertEqual(normalized["num_hidden_layers"] as? Int, 12)
        XCTAssertEqual(normalized["num_attention_heads"] as? Int, 12)
        XCTAssertEqual(normalized["max_position_embeddings"] as? Int, 1024)
        // Strict parse now succeeds on a GPT-2-shaped config.
        XCTAssertNoThrow(try HuggingFaceConfig.fromDict(normalized))
    }

    func testTokenizerMissingFlagged() {
        let (info0, cfg) = lmInfo()
        var info = info0
        info.siblings = info.siblings.filter { !$0.name.contains("tokenizer") }
        let a = assess(info, config: cfg)
        XCTAssertTrue(a.requiredChanges.contains { $0.detail.contains("tokenizer") })
    }

    // MARK: - adapters / remote code / gated / GGUF meta

    func testAdapterRepo() {
        let info = HubModelClient.Info(
            id: "x/opt-lora", libraryName: "peft",
            siblings: [.init(name: "adapter_config.json", size: 400),
                       .init(name: "adapter_model.safetensors", size: 20_000_000)],
            baseModel: "facebook/opt-350m")
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/opt-lora"), info: info, fetchIssue: nil,
            config: nil, configIssue: nil,
            adapter: (base: "facebook/opt-350m", peftType: "lora"), env: env()))
        XCTAssertEqual(a.verdict, .changesRequired)
        XCTAssertTrue(a.verdictSummary.contains("opt-350m"))
        XCTAssertTrue(a.formats.contains("peft-adapter"))
    }

    func testRemoteCodeRepo() {
        let (info, cfg) = lmInfo(archs: ["Phi3VForCausalLM"])
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/phi3v"), info: info, fetchIssue: nil,
            config: cfg, configIssue: nil, remoteCode: true, env: env()))
        XCTAssertEqual(a.verdict, .unsupportedOnCheckedPath)
        XCTAssertTrue(a.checkedPath.detail.contains("auto_map"))
    }

    func testRemoteCodeOnVerifiedArchIsNoteOnly() {
        let (info, cfg) = lmInfo()
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/qwen"), info: info, fetchIssue: nil,
            config: cfg, configIssue: nil, remoteCode: true, env: env()))
        XCTAssertEqual(a.verdict, .expectedToWork)
        XCTAssertTrue(a.limitations.contains { $0.contains("auto_map") })
    }

    func testGatedDowngrade() {
        var (info, cfg) = lmInfo()
        info.gated = true
        let a = assess(info, config: cfg)
        XCTAssertEqual(a.verdict, .changesRequired)
        XCTAssertTrue(a.requiredChanges.contains { $0.kind == "access" })
    }

    func testGGUFMetaParsing() {
        // Hand-built minimal GGUF: magic + v3 + counts + two metadata KVs.
        var d = Data()
        d.append(contentsOf: [0x47, 0x47, 0x55, 0x46])          // 'GGUF'
        d.append(contentsOf: [3, 0, 0, 0])                       // version 3
        d.append(contentsOf: [1, 0, 0, 0, 0, 0, 0, 0])           // 1 tensor
        d.append(contentsOf: [2, 0, 0, 0, 0, 0, 0, 0])           // 2 kvs
        func str(_ s: String) -> [UInt8] {
            var n = UInt64(s.utf8.count)
            return withUnsafeBytes(of: &n) { Array($0) } + Array(s.utf8)
        }
        d.append(contentsOf: str("general.architecture"))
        d.append(contentsOf: [8, 0, 0, 0])                       // vtype string
        d.append(contentsOf: str("llama"))
        d.append(contentsOf: str("general.file_type"))
        d.append(contentsOf: [4, 0, 0, 0])                       // vtype u32
        d.append(contentsOf: [15, 0, 0, 0])                      // Q4_K_M
        let meta = GGUFHeader.parse(d)
        XCTAssertEqual(meta?.architecture, "llama")
        XCTAssertEqual(meta?.fileType, 15)
        XCTAssertEqual(GGUFHeader.fileTypeName(15), "Q4_K_M")
    }

    func testGGUFKQuantUnsupportedHonest() {
        let info = HubModelClient.Info(
            id: "x/gguf", siblings: [.init(name: "m-Q4_K_M.gguf", size: 2_000_000_000)])
        let kv: [String: Any] = ["general.architecture": "llama", "general.file_type": UInt32(15)]
        let meta = GGUFHeader.Meta(version: 3, tensorCount: 300, kv: kv)
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/gguf"), info: info, fetchIssue: nil,
            config: nil, configIssue: nil, ggufMeta: meta, env: env()))
        XCTAssertEqual(a.verdict, .unsupportedOnCheckedPath)   // K-quant not dequantized by our loader
        XCTAssertTrue(a.checkedPath.detail.contains("K-quant"))
    }

    func testGGUFLlamaQ80Loadable() {
        let info = HubModelClient.Info(
            id: "x/gguf", siblings: [.init(name: "m-Q8_0.gguf", size: 3_000_000_000)])
        let meta = GGUFHeader.Meta(version: 3, tensorCount: 300,
                                   kv: ["general.architecture": "qwen2", "general.file_type": UInt32(8)])
        let a = CompatibilityRules.assess(.init(
            ref: ref("x/gguf"), info: info, fetchIssue: nil,
            config: nil, configIssue: nil, ggufMeta: meta, env: env()))
        XCTAssertEqual(a.verdict, .changesRequired)   // verified arch + supported quant
    }

    // MARK: - report schema + agent prompt

    func testReportRoundTripsJSON() throws {
        let (info, cfg) = lmInfo()
        // Exercise the service's report assembly path directly against
        // rules output — the network stage is covered by HubModelClient,
        // not re-tested here.
        let a = CompatibilityRules.assess(.init(
            ref: ref("Qwen/Qwen3-4B-Instruct-2507"), info: info,
            fetchIssue: nil, config: cfg, configIssue: nil, env: env()))
        let report = ModelCheckReport(
            schemaVersion: 1, checkedAt: "2026-09-22T00:00:00Z",
            input: "Qwen/Qwen3-4B-Instruct-2507",
            model: .init(id: info.id, revision: "main", task: a.task,
                         library: a.library, architectures: a.architectures,
                         formats: a.formats, selectedVariant: a.selectedVariant,
                         gated: false, lastModified: nil),
            environment: .init(chip: "Apple M5 Pro", arch: "arm64",
                               ramBytes: 48 * 1_073_741_824,
                               freeDiskBytes: 400 * 1_073_741_824,
                               macOSVersion: "macOS 26.0", source: "detected",
                               runtimes: []),
            verdict: a.verdict, verdictSummary: a.verdictSummary,
            checkedPath: a.checkedPath, otherPaths: a.otherPaths,
            requiredChanges: a.requiredChanges, evidence: a.evidence,
            nextActions: a.nextActions, agentPrompt: "test",
            limitations: a.limitations)
        let json = try report.encoded()
        XCTAssertTrue(json.contains("\"schema_version\""))
        XCTAssertTrue(json.contains("\"expected_to_work\""))
        let decoded = try ModelCheckReport.decode(Data(json.utf8))
        XCTAssertEqual(decoded, report)
    }

    func testAgentPromptCarriesContext() {
        let (info, cfg) = lmInfo(archs: ["NemotronForCausalLM"])
        let a = assess(info, config: cfg)
        let report = ModelCheckReport(
            schemaVersion: 1, checkedAt: "2026-09-22T00:00:00Z",
            input: "x", model: .init(id: info.id, revision: "main", task: a.task,
                                     library: nil, architectures: a.architectures,
                                     formats: a.formats, selectedVariant: nil,
                                     gated: false, lastModified: nil),
            environment: .init(chip: "Apple M5 Pro", arch: "arm64",
                               ramBytes: 48 * 1_073_741_824, freeDiskBytes: 0,
                               macOSVersion: "macOS 26.0", source: "detected",
                               runtimes: []),
            verdict: a.verdict, verdictSummary: a.verdictSummary,
            checkedPath: a.checkedPath, otherPaths: a.otherPaths,
            requiredChanges: a.requiredChanges, evidence: a.evidence,
            nextActions: a.nextActions, agentPrompt: "", limitations: a.limitations)
        let prompt = ModelCheckService.agentPrompt(for: report)
        XCTAssertTrue(prompt.contains(info.id))
        XCTAssertTrue(prompt.contains("main"))
        XCTAssertTrue(prompt.contains("Apple M5 Pro"))
        XCTAssertTrue(prompt.lowercased().contains("investigate"))
        XCTAssertTrue(prompt.contains("NemotronForCausalLM"))
        XCTAssertFalse(prompt.contains("HF_TOKEN="))   // never leak a token value
    }
}
