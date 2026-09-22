import Foundation
import TinyGPTIO

/// Pure verdict logic for model-check: repo snapshot + environment →
/// assessment. No network, no process spawning, no side effects — every
/// branch is unit-testable against fixtures.
///
/// The checked path is always the posttrainllm native runtime
/// (`HFModelLoader` → `TinyGPTModelHF`, MLX-Swift). Its real gates:
///   - the loader unconditionally builds RoPE + RMSNorm + SwiGLU + GQA
///     (`HFConfigConverter.toModelConfig`), so only the verified
///     Llama-family `*ForCausalLM` set is a documented yes — anything else
///     would silently construct the wrong architecture, which is worse
///     than `unknown`.
///   - `HuggingFaceConfig.unsupportedReason()` catches the remaining
///     config-level blockers (activation whitelist, RoPE scaling, GQA
///     divisibility).
///   - RAM: bf16/fp16 checkpoints are up-converted to fp32 at load
///     (~2× weight bytes resident). MLX-packed checkpoints load
///     quantized (~1.15× weight bytes).
public enum CompatibilityRules {

    /// Everything the rules need, pre-fetched by the service. A nil
    /// `info` means the API lookup itself failed — see `fetchIssue`.
    public struct Input {
        public var ref: ModelRef
        public var info: HubModelClient.Info?       // nil → fetch failed
        public var fetchIssue: String?              // human-readable why
        public var config: HuggingFaceConfig?       // parsed config.json
        public var configIssue: String?             // why config is nil
        public var env: MacEnvironment
        /// Extra formats found in the sibling list that Info doesn't model.
        public init(ref: ModelRef, info: HubModelClient.Info?, fetchIssue: String?,
                    config: HuggingFaceConfig?, configIssue: String?, env: MacEnvironment) {
            self.ref = ref; self.info = info; self.fetchIssue = fetchIssue
            self.config = config; self.configIssue = configIssue; self.env = env
        }
    }

    public struct Assessment {
        public var verdict: ModelCheckReport.Verdict
        public var verdictSummary: String
        public var checkedPath: ModelCheckReport.PathAssessment
        public var otherPaths: [ModelCheckReport.ExecutionPath]
        public var requiredChanges: [ModelCheckReport.RequiredChange]
        public var evidence: [ModelCheckReport.Evidence]
        public var nextActions: [String]
        public var limitations: [String]
        public var formats: [String]
        public var architectures: [String]
        public var selectedVariant: String?
        public var task: String?
        public var library: String?
        public var gated: Bool
        public var lastModified: String?
    }

    /// Architectures HFModelLoader is verified to build correctly. The
    /// converter always produces a RoPE+RMSNorm+SwiGLU model, so this is
    /// intentionally the Llama-family list only — a generic
    /// `*ForCausalLM` (Falcon, GPT-2, MPT…) would load into the wrong
    /// architecture and produce garbage rather than an error.
    public static let verifiedArchitectures: Set<String> = [
        "LlamaForCausalLM", "MistralForCausalLM",
        "Qwen2ForCausalLM", "Qwen3ForCausalLM",
        "PhiForCausalLM", "Phi3ForCausalLM",
        "GemmaForCausalLM", "Gemma2ForCausalLM", "Gemma3ForCausalLM",
        "LFM2ForCausalLM", "SmolLM3ForCausalLM",
    ]

    /// pipeline_tags that are generation-side language tasks the checked
    /// runtime exists for. Anything else is a documented mismatch, not a
    /// capability claim.
    static let languageTasks: Set<String> = [
        "text-generation", "text2text-generation", "fill-mask",
        "summarization", "translation", "question-answering",
        "text-classification", "token-classification",
        "feature-extraction", "sentence-similarity",
    ]

    static let checkedPathName = "posttrainllm native runtime (MLX-Swift)"

    // MARK: - entry point

    public static func assess(_ input: Input) -> Assessment {
        var a = Assessment(
            verdict: .unknown, verdictSummary: "",
            checkedPath: .init(name: checkedPathName, status: .unknown, detail: ""),
            otherPaths: [], requiredChanges: [], evidence: [],
            nextActions: [], limitations: [],
            formats: [], architectures: [], selectedVariant: nil,
            task: nil, library: nil, gated: false, lastModified: nil)

        let apiURL = "https://huggingface.co/api/models/\(input.ref.id)"
        a.evidence.append(.init(source: apiURL, kind: "documented",
                                detail: "Hugging Face Hub model metadata"))
        a.evidence.append(.init(source: "local system probe", kind: "documented",
                                detail: "environment: \(input.env.chip), "
                                    + "\(fmtBytes(input.env.ramBytes)) RAM, "
                                    + "\(fmtBytes(input.env.freeDiskBytes)) free disk "
                                    + "(\(input.env.source))"))

        // Fetch-level failures → Unknown with the limitation named.
        guard let info = input.info else {
            a.verdict = .unknown
            a.verdictSummary = "could not inspect the repository"
            a.limitations.append(input.fetchIssue ?? "model metadata unavailable")
            a.checkedPath.detail = "repository metadata could not be fetched"
            a.nextActions.append("Hand the agent prompt to an agent with network access to identify the repo, or set HF_TOKEN if the repo is gated/private.")
            return a
        }

        a.task = info.pipelineTag
        a.library = info.libraryName
        a.gated = info.gated
        a.lastModified = info.lastModified
        a.architectures = input.config?.architectures ?? []
        a.formats = detectFormats(info: info, config: input.config)
        a.selectedVariant = pickVariant(info: info)

        let ram = input.env.ramBytes
        let disk = input.env.freeDiskBytes

        // --- Repo-kind / task gates -----------------------------------
        if isDiffusers(info: info) {
            return diffusersAssessment(&a, info: info, env: input.env)
        }

        // --- Format → candidate paths ---------------------------------
        let safetensorsBytes = info.sizeOf(".safetensors")
        let ggufFiles = info.siblings(matchingSuffix: ".gguf")
        let hasConfig = info.sibling(named: "config.json") != nil
        let hasSafetensors = safetensorsBytes > 0 || !info.siblings(matchingSuffix: ".safetensors").isEmpty
        let hasPytorchBin = !info.siblings(matchingSuffix: ".bin").isEmpty
        let mlxPacked = isMLXQuantized(info: info, config: input.config)

        if hasSafetensors && hasConfig {
            return safetensorsAssessment(&a, input: input, info: info,
                                         weightBytes: safetensorsBytes,
                                         mlxPacked: mlxPacked,
                                         ram: ram, disk: disk)
        }
        if !ggufFiles.isEmpty {
            return ggufAssessment(&a, info: info, ggufFiles: ggufFiles,
                                  env: input.env)
        }
        if hasPytorchBin && hasConfig {
            return pytorchBinAssessment(&a, input: input, info: info)
        }
        if hasConfig, let cfg = input.config {
            // config but no weights we recognise — e.g. sharded .bin under
            // a different name, or remote-code repos.
            return configOnlyAssessment(&a, input: input, cfg: cfg, info: info)
        }

        // Nothing we can identify.
        a.verdict = .unknown
        a.verdictSummary = "repository has no safetensors, GGUF, or readable config.json we can assess"
        a.checkedPath.status = .unknown
        a.checkedPath.detail = "no loadable weight format was identified in the file manifest"
        if let ci = input.configIssue { a.limitations.append(ci) }
        if info.gated { a.limitations.append("repo is gated (\(info.gatedKind ?? "auto")) — file manifest may be incomplete without HF_TOKEN") }
        a.nextActions.append("Use the agent prompt to have an agent inspect the full file list and README for a documented execution path.")
        return a
    }

    // MARK: - format detection

    static func detectFormats(info: HubModelClient.Info, config: HuggingFaceConfig?) -> [String] {
        var f: [String] = []
        if info.sibling(named: "model_index.json") != nil { f.append("diffusers") }
        if !info.siblings(matchingSuffix: ".safetensors").isEmpty { f.append("safetensors") }
        if !info.siblings(matchingSuffix: ".gguf").isEmpty { f.append("gguf") }
        if !info.siblings(matchingSuffix: ".onnx").isEmpty { f.append("onnx") }
        if info.siblings.contains(where: { $0.name.contains(".mlpackage") || $0.name.contains(".mlmodelc") }) {
            f.append("coreml")
        }
        if !info.siblings(matchingSuffix: ".bin").isEmpty { f.append("pytorch-bin") }
        if isMLXQuantized(info: info, config: config) { f.append("mlx-quantized") }
        return f
    }

    static func isDiffusers(info: HubModelClient.Info) -> Bool {
        if info.libraryName == "diffusers" { return true }
        if info.sibling(named: "model_index.json") != nil { return true }
        if let tag = info.pipelineTag {
            return tag.hasPrefix("text-to-image") || tag.hasPrefix("image-to-")
                || tag.hasPrefix("text-to-video") || tag.hasPrefix("text-to-audio")
                || tag.hasPrefix("audio-") || tag == "image-text-to-text"
                || tag.hasPrefix("image-") || tag.hasPrefix("video-")
                || tag == "automatic-speech-recognition" || tag == "text-to-speech"
        }
        return false
    }

    static func isMLXQuantized(info: HubModelClient.Info, config: HuggingFaceConfig?) -> Bool {
        if let q = config?.extras["quantization"] as? [String: Any],
           (q["quant_method"] as? String) == "mlx" { return true }
        if let q = config?.extras["quantization_config"] as? [String: Any],
           (q["quant_method"] as? String) == "mlx" { return true }
        if info.id.hasPrefix("mlx-community/") || info.tags.contains("mlx") { return true }
        return false
    }

    /// The GGUF sibling we'd pick — prefer a middle quant (Q4_K_M/Q5) if
    /// several exist, else the largest single file.
    static func pickVariant(info: HubModelClient.Info) -> String? {
        let ggufs = info.siblings(matchingSuffix: ".gguf")
        guard !ggufs.isEmpty else { return nil }
        let preferred = ["q4_k_m", "q5_k_m", "q4_0", "q8_0"]
        for tag in preferred {
            if let hit = ggufs.first(where: { $0.name.lowercased().contains(tag) }) {
                return hit.name
            }
        }
        return ggufs.max(by: { ($0.size ?? 0) < ($1.size ?? 0) })?.name
    }

    // MARK: - memory estimates (all estimates, always flagged)

    /// Parameter count → dtype bytes per param. Only the dominant dtype
    /// matters for a back-of-envelope figure.
    static func weightEstimate(info: HubModelClient.Info) -> (params: Int64, bytes: Int64, source: String)? {
        if !info.safetensorsParams.isEmpty {
            let bytesPer: [String: Double] = [
                "F64": 8, "F32": 4, "BF16": 2, "F16": 2,
                "I64": 8, "I32": 4, "I16": 2, "I8": 1, "U8": 1,
                "F8_E4M3": 1, "F8_E5M2": 1,
            ]
            var params: Int64 = 0
            var bytes: Double = 0
            for (dtype, count) in info.safetensorsParams {
                params += count
                bytes += Double(count) * (bytesPer[dtype] ?? 2)
            }
            return (params, Int64(bytes), "safetensors parameter stats")
        }
        let stBytes = info.sizeOf(".safetensors")
        if stBytes > 0 { return (0, stBytes, "safetensors file sizes") }
        return nil
    }

    /// Resident-memory estimate for the posttrainllm path: fp16/bf16
    /// checkpoints up-convert to fp32 (~2× weight bytes); MLX-packed
    /// checkpoints stay quantized (~1.15×).
    static func loadFootprint(weightBytes: Int64, mlxPacked: Bool) -> Int64 {
        Int64(Double(weightBytes) * (mlxPacked ? 1.15 : 2.0))
    }

    // MARK: - per-format assessments

    static func safetensorsAssessment(
        _ a: inout Assessment, input: Input, info: HubModelClient.Info,
        weightBytes: Int64, mlxPacked: Bool, ram: Int64, disk: Int64
    ) -> Assessment {
        guard let cfg = input.config else {
            a.verdict = .unknown
            a.verdictSummary = "safetensors present but config.json could not be read"
            a.checkedPath.status = .unknown
            a.checkedPath.detail = "cannot determine the architecture without config.json"
            if let ci = input.configIssue { a.limitations.append(ci) }
            a.nextActions.append("Set HF_TOKEN if the repo is gated, then re-run; otherwise hand the agent prompt to investigate config.json.")
            return a
        }

        let archs = cfg.architectures
        if archs.isEmpty {
            a.limitations.append("config.json has no architectures field")
        }

        // Task mismatch first — a text-to-image safetensors repo with a
        // config.json still isn't a language model for this runtime.
        if let tag = info.pipelineTag, !languageTasks.contains(tag) {
            a.verdict = .unsupportedOnCheckedPath
            a.verdictSummary = "a \(tag) model is not a language task the posttrainllm runtime executes"
            a.checkedPath.status = .unsupportedOnCheckedPath
            a.checkedPath.detail = "the checked path is a causal-LM runtime; '\(tag)' pipelines need a different executor (task mismatch, not a Mac capability limit)"
            a.otherPaths.append(transformersPath(env: input.env, task: tag))
            a.nextActions.append("Run it through a runtime that implements the '\(tag)' pipeline — see Other Mac execution paths.")
            addMemoryChange(&a, weightBytes: weightBytes, disk: disk)
            return a
        }

        // Architecture gates.
        let moe = archs.contains { $0.localizedCaseInsensitiveContains("moe") }
        let multimodal = archs.contains { $0.contains("ConditionalGeneration") || $0.contains("Vision") }
        let verified = archs.contains { verifiedArchitectures.contains($0) }

        if multimodal {
            a.verdict = .unsupportedOnCheckedPath
            a.verdictSummary = "multimodal \(archs.joined(separator: ", ")) — the HF loader is text-only"
            a.checkedPath.status = .unsupportedOnCheckedPath
            a.checkedPath.detail = "architectures wrap a vision/audio tower around the LM; posttrainllm's HF path loads text-only *ForCausalLM weights (a VLM path exists but is parked)"
            a.otherPaths.append(mlxLmPath(env: input.env, note: "mlx-lm / mlx-vlm handle several VLM families natively"))
            a.otherPaths.append(transformersPath(env: input.env, task: info.pipelineTag ?? "multimodal"))
            a.nextActions.append("Use mlx-vlm or transformers for the multimodal wrapper; a text-only variant of this family may exist as a separate repo.")
            addMemoryChange(&a, weightBytes: weightBytes, disk: disk)
            return a
        }
        if moe {
            a.verdict = .unsupportedOnCheckedPath
            a.verdictSummary = "MoE \(archs.joined(separator: ", ")) — the HF loader builds a dense MLP"
            a.checkedPath.status = .unsupportedOnCheckedPath
            a.checkedPath.detail = "HFConfigConverter does not wire expert routing for HF configs; loading would silently produce a wrong dense model"
            a.otherPaths.append(mlxLmPath(env: input.env, note: "mlx-lm supports MoE families including Qwen3-MoE and Mixtral"))
            a.otherPaths.append(ollamaOrLlamaCppPath(env: input.env, ggufPresent: false))
            a.nextActions.append("Prefer mlx-lm or a GGUF variant through llama.cpp/Ollama for MoE checkpoints.")
            addMemoryChange(&a, weightBytes: weightBytes, disk: disk)
            return a
        }
        if !verified {
            let named = archs.isEmpty ? "(unnamed)" : archs.joined(separator: ", ")
            a.verdict = .unknown
            a.verdictSummary = "architecture \(named) is not in the verified load set"
            a.checkedPath.status = .unknown
            a.checkedPath.detail = "posttrainllm's HF loader unconditionally builds the Llama-family layout (RoPE+RMSNorm+SwiGLU); \(named) is outside the verified set, so loading could silently produce the wrong model"
            a.otherPaths.append(mlxLmPath(env: input.env, note: "mlx-lm carries a wider verified architecture table"))
            a.otherPaths.append(transformersPath(env: input.env, task: info.pipelineTag ?? "text-generation"))
            a.limitations.append("verified set: \(verifiedArchitectures.sorted().joined(separator: ", "))")
            a.nextActions.append("Ask the agent to verify whether \(named) matches the Llama-family layout (attention + SwiGLU MLP + RMSNorm + RoPE) before attempting a load.")
            addMemoryChange(&a, weightBytes: weightBytes, disk: disk)
            return a
        }

        // Verified family — config-level blockers next.
        if let reason = cfg.unsupportedReason() {
            a.verdict = .unsupportedOnCheckedPath
            a.verdictSummary = "\(archs.joined(separator: ", ")) needs runtime work: \(reason)"
            a.checkedPath.status = .unsupportedOnCheckedPath
            a.checkedPath.detail = reason
            a.requiredChanges.append(.init(kind: "runtime", detail: reason, sizeBytes: nil, estimate: false))
            a.otherPaths.append(mlxLmPath(env: input.env, note: nil))
            a.otherPaths.append(transformersPath(env: input.env, task: info.pipelineTag ?? "text-generation"))
            a.nextActions.append("Run through mlx-lm or transformers while the runtime gap is open, or extend the loader for the blocker above.")
            addMemoryChange(&a, weightBytes: weightBytes, disk: disk)
            return a
        }

        // Loadable — now it's a memory/disk question.
        let est = weightEstimate(info: info)
        let weights = weightBytes > 0 ? weightBytes : (est?.bytes ?? 0)
        let footprint = loadFootprint(weightBytes: weights, mlxPacked: mlxPacked)
        let estNote = est.map { "~\($0.params > 0 ? fmtParams($0.params) + " params, " : "")\(fmtBytes($0.bytes)) weights (\($0.source))" }
            ?? "weight size unknown"
        if weights == 0 {
            a.limitations.append("weight size could not be determined — memory fit is unverified")
        }

        a.evidence.append(.init(
            source: "https://huggingface.co/\(info.id)/resolve/\(input.ref.revision)/config.json",
            kind: "documented", detail: "config.json → \(archs.joined(separator: ", "))"))
        a.evidence.append(.init(source: apiDetail(info), kind: "inferred",
                                detail: "memory estimate: \(fmtBytes(footprint)) resident — \(estNote), marked estimate"))

        if disk > 0 && weights > disk {
            a.requiredChanges.append(.init(kind: "memory", detail: "free disk space — weights are ~\(fmtBytes(weights)) but only \(fmtBytes(disk)) is free", sizeBytes: weights, estimate: true))
        }
        if ram > 0 {
            if footprint <= Int64(Double(ram) * 0.70) {
                a.verdict = .expectedToWork
                a.verdictSummary = "\(archs.joined(separator: ", ")) on \(input.env.chip): estimated \(fmtBytes(footprint)) resident vs \(fmtBytes(ram)) RAM"
                a.checkedPath.status = .expectedToWork
                a.checkedPath.detail = "verified architecture, no config blockers, estimated footprint fits with headroom (all memory figures are estimates)"
                a.nextActions.append("Download with the app's HF browser or `posttrainllm hf-load` after download; then `posttrainllm sample <dir>` or `sft` it.")
            } else if footprint <= Int64(Double(ram) * 0.95) {
                a.verdict = .changesRequired
                a.verdictSummary = "should load, but estimated \(fmtBytes(footprint)) is tight against \(fmtBytes(ram)) RAM"
                a.checkedPath.status = .changesRequired
                a.checkedPath.detail = "fits only with most of RAM free; fp32 up-conversion doubles bf16/fp16 weights at load"
                a.requiredChanges.append(.init(kind: "memory", detail: "free memory headroom — close large apps, or prefer a quantized variant", sizeBytes: footprint, estimate: true))
                a.nextActions.append("Close memory-heavy apps and retry, or pick a quantized variant (see Other paths).")
            } else {
                // Doesn't fit dense — does a q4 path plausibly fit?
                let q4 = Int64(Double(weights) * (mlxPacked ? 1.15 : 0.55 * 1.15)) + weights / 8
                a.verdict = .changesRequired
                a.verdictSummary = "too large to load dense (est. \(fmtBytes(footprint)) vs \(fmtBytes(ram)) RAM); a quantized variant is the documented route"
                a.checkedPath.status = .changesRequired
                a.checkedPath.detail = "dense fp32 load estimate exceeds RAM; quantization or a smaller variant is required before this runtime can hold it"
                a.requiredChanges.append(.init(kind: "conversion", detail: "use an MLX-quantized or GGUF variant — rough q4 estimate \(fmtBytes(q4))", sizeBytes: q4, estimate: true))
                a.otherPaths.append(ollamaOrLlamaCppPath(env: input.env, ggufPresent: false))
                a.otherPaths.append(mlxLmPath(env: input.env, note: "mlx-lm can serve community -4bit/-8bit quantizations of the same base"))
                a.nextActions.append("Look for a -GGUF or mlx-community -4bit variant of this repo, then re-run model-check against it.")
            }
        } else {
            a.verdict = .expectedToWork
            a.verdictSummary = "\(archs.joined(separator: ", ")) is a verified load; RAM unknown — memory could not be checked"
            a.checkedPath.status = .expectedToWork
            a.checkedPath.detail = "verified architecture with no config blockers; RAM was not supplied so fit is unverified"
            a.limitations.append("RAM not detected/supplied — fit estimate skipped")
        }
        return a
    }

    static func ggufAssessment(
        _ a: inout Assessment, info: HubModelClient.Info,
        ggufFiles: [HubModelClient.Sibling], env: MacEnvironment
    ) -> Assessment {
        let variant = a.selectedVariant ?? ggufFiles.first?.name ?? "the .gguf file"
        let variantSize = ggufFiles.first(where: { $0.name == variant })?.size
            ?? ggufFiles.compactMap(\.size).max()

        a.verdict = .changesRequired
        a.verdictSummary = "GGUF weights — needs a download plus a GGUF-capable runtime"
        a.checkedPath.status = .changesRequired
        a.checkedPath.detail = "posttrainllm loads single-file GGUF (`gguf-load`, materialized through the HF loader) for Llama-family architectures; this repo ships no safetensors, so download '\(variant)' first — architecture support still needs verifying against the verified set"
        a.requiredChanges.append(.init(kind: "model-component",
            detail: "download \(variant) from the repo's Files tab",
            sizeBytes: variantSize, estimate: variantSize == nil))

        let ollama = env.runtimes.first { $0.name == "ollama" }
        let llamacpp = env.runtimes.first { $0.name == "llama.cpp" }
        if ollama?.found == true {
            a.otherPaths.append(.init(name: "Ollama", status: .expectedToWork,
                detail: "installed (\(ollama?.version ?? "version unknown")) — `ollama run hf.co/\(info.id)` pulls and runs GGUF repos directly",
                source: "https://ollama.com/blog/gguf", evidenceKind: "documented"))
        } else {
            a.otherPaths.append(.init(name: "Ollama / llama.cpp", status: .changesRequired,
                detail: "not detected\(llamacpp?.found == true ? " (llama-cli is installed)" : "") — `ollama run hf.co/\(info.id)` or `llama-cli -hf \(info.id)` are the documented GGUF paths once installed",
                source: "https://github.com/ggml-org/llama.cpp", evidenceKind: "documented"))
        }
        if let sz = variantSize {
            a.evidence.append(.init(source: "https://huggingface.co/\(info.id)", kind: "documented",
                                    detail: "selected variant \(variant): \(fmtBytes(sz)) (GGUF mmap footprint ≈ file size + context, estimate)"))
        }
        a.nextActions.append("Download \(variant) and run `posttrainllm gguf-load <file>`, or run it directly through Ollama/llama.cpp.")
        return a
    }

    static func pytorchBinAssessment(
        _ a: inout Assessment, input: Input, info: HubModelClient.Info
    ) -> Assessment {
        a.verdict = .changesRequired
        a.verdictSummary = "PyTorch .bin weights — conversion or a different loader required"
        a.checkedPath.status = .unsupportedOnCheckedPath
        a.checkedPath.detail = "the HF loader reads safetensors; this repo ships pytorch_model.bin only"
        a.requiredChanges.append(.init(kind: "conversion",
            detail: "convert to safetensors (transformers save_pretrained / safetensors convert), or find the safetensors variant HF often auto-generates as a sibling ref",
            sizeBytes: nil, estimate: false))
        a.otherPaths.append(transformersPath(env: input.env, task: info.pipelineTag ?? "text-generation"))
        a.nextActions.append("Check the repo's refs for a safetensors revision, or run through transformers.")
        return a
    }

    static func configOnlyAssessment(
        _ a: inout Assessment, input: Input, cfg: HuggingFaceConfig, info: HubModelClient.Info
    ) -> Assessment {
        a.verdict = .unknown
        a.verdictSummary = "config.json is readable but no recognized weight format is listed"
        a.checkedPath.status = .unknown
        a.checkedPath.detail = "no .safetensors / .gguf / .bin siblings — the repo may use remote code, sharded formats under different names, or be a weights-less repo"
        a.limitations.append("file manifest does not show a recognized weight file; remote-code repos are out of scope (code execution is never performed)")
        a.nextActions.append("Have an agent read the repo's README + full file list for its documented load path.")
        return a
    }

    static func diffusersAssessment(
        _ a: inout Assessment, info: HubModelClient.Info, env: MacEnvironment
    ) -> Assessment {
        let task = info.pipelineTag ?? "diffusion"
        a.verdict = .unsupportedOnCheckedPath
        a.verdictSummary = "\(task) pipeline — the checked runtime executes language models, not this task"
        a.checkedPath.status = .unsupportedOnCheckedPath
        a.checkedPath.detail = "'\(task)' is not a language-model task. This says nothing about the Mac — it is a runtime/task mismatch, and a different executor is required regardless of hardware."

        let pyStack = env.runtimes.first { $0.name == "python3 ML stack" }
        let hasDiffusers = pyStack?.version?.contains("diffusers") == true
        a.otherPaths.append(.init(
            name: "Python diffusers",
            status: hasDiffusers ? .expectedToWork : .changesRequired,
            detail: hasDiffusers
                ? "diffusers is installed\(pyStack?.version.map { " (\($0))" } ?? "") — `DiffusionPipeline.from_pretrained(\"\(info.id)\")` is the documented load path"
                : "documented path: `pip install diffusers torch` then `DiffusionPipeline.from_pretrained(\"\(info.id)\")` — not currently installed",
            source: "https://huggingface.co/docs/diffusers/index", evidenceKind: "documented"))
        a.otherPaths.append(.init(
            name: "Core ML / app ecosystem", status: .changesRequired,
            detail: "community Core ML conversions and apps (e.g. Draw Things) run many diffusion models natively on Apple Silicon",
            source: "https://github.com/huggingface/coreml-community", evidenceKind: "inferred"))
        a.nextActions.append("Use Python diffusers or a Core ML conversion — see Other Mac execution paths. The agent prompt carries the full context if you want a deeper investigation.")
        return a
    }

    // MARK: - shared path builders

    static func transformersPath(env: MacEnvironment, task: String) -> ModelCheckReport.ExecutionPath {
        let pyStack = env.runtimes.first { $0.name == "python3 ML stack" }
        let hasTransformers = pyStack?.version?.contains("transformers") == true
        return .init(
            name: "Python transformers",
            status: hasTransformers ? .expectedToWork : .changesRequired,
            detail: hasTransformers
                ? "transformers is installed — `AutoModel.from_pretrained` covers '\(task)' families"
                : "documented generic path: `pip install transformers` then the matching Auto class for '\(task)'",
            source: "https://huggingface.co/docs/transformers/index", evidenceKind: "documented")
    }

    static func mlxLmPath(env: MacEnvironment, note: String?) -> ModelCheckReport.ExecutionPath {
        let pyStack = env.runtimes.first { $0.name == "python3 ML stack" }
        let hasMLXLM = pyStack?.version?.contains("mlx-lm") == true
        return .init(
            name: "mlx-lm",
            status: hasMLXLM ? .expectedToWork : .changesRequired,
            detail: (note.map { $0 + "; " } ?? "")
                + (hasMLXLM ? "installed\(pyStack?.version.map { " (\($0))" } ?? "")"
                            : "not detected — `pip install mlx-lm`"),
            source: "https://github.com/ml-explore/mlx-lm", evidenceKind: "documented")
    }

    static func ollamaOrLlamaCppPath(env: MacEnvironment, ggufPresent: Bool) -> ModelCheckReport.ExecutionPath {
        let ollama = env.runtimes.first { $0.name == "ollama" }
        let llamacpp = env.runtimes.first { $0.name == "llama.cpp" }
        if ollama?.found == true || llamacpp?.found == true {
            return .init(name: "Ollama / llama.cpp", status: .expectedToWork,
                detail: "installed — GGUF repos run directly; for safetensors, a published GGUF conversion is needed",
                source: "https://github.com/ggml-org/llama.cpp", evidenceKind: "documented")
        }
        return .init(name: "Ollama / llama.cpp", status: .changesRequired,
            detail: "not detected — install Ollama or llama.cpp for the GGUF path\(ggufPresent ? " (this repo ships GGUF files)" : " (requires a GGUF conversion of this repo)")",
            source: "https://github.com/ggml-org/llama.cpp", evidenceKind: "documented")
    }

    static func addMemoryChange(_ a: inout Assessment, weightBytes: Int64, disk: Int64) {
        if disk > 0 && weightBytes > disk {
            a.requiredChanges.append(.init(kind: "memory",
                detail: "free disk space — weights ~\(fmtBytes(weightBytes)) vs \(fmtBytes(disk)) free",
                sizeBytes: weightBytes, estimate: true))
        }
    }

    static func apiDetail(_ info: HubModelClient.Info) -> String {
        "https://huggingface.co/api/models/\(info.id)"
    }

    static func fmtBytes(_ n: Int64) -> String {
        ModelCheckReport.fmtBytes(n)
    }

    static func fmtParams(_ n: Int64) -> String {
        if n >= 1_000_000_000 { return String(format: "%.1fB", Double(n) / 1_000_000_000) }
        if n >= 1_000_000 { return String(format: "%.0fM", Double(n) / 1_000_000) }
        return "\(n)"
    }
}
