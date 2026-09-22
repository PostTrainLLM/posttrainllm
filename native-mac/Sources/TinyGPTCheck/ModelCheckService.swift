import Foundation
import TinyGPTIO

/// The one inspection flow behind `posttrainllm model-check` and the Mac
/// app's "Check model compatibility" panel. Read-only end to end:
///
///   URL + environment
///     → fetch repository metadata + small config files
///     → apply known compatibility checks
///     → merge an exact-revision/device local receipt when one exists
///     → produce a schema-v2 structured report
///
/// It never downloads weights, installs software, runs a model, or
/// executes repository code. Missing metadata and failed lookups produce
/// explicit limitations, not invented claims — `unknown` is a valid
/// outcome.
public enum ModelCheckService {

    /// Progress stages surfaced by both the CLI and the UI panel.
    public enum Stage: String, Sendable {
        case inspectingRepository = "Inspecting repository"
        case checkingEnvironment = "Checking environment"
        case preparingReport = "Preparing report"
    }

    public enum CheckError: Error, CustomStringConvertible {
        case invalidInput(String)
        public var description: String {
            switch self {
            case .invalidInput(let s): return s
            }
        }
    }

    /// Run the check. Synchronous by design (matches the codebase's
    /// HTTP style); the app wraps it on a background queue.
    ///
    /// - Parameters:
    ///   - input: HF URL or `owner/repo`
    ///   - environment: override environment; nil → `MacEnvironment.detect()`
    ///   - progress: optional stage callback
    /// - Throws: `CheckError.invalidInput` only — every fetch/parse failure
    ///   lands inside the report as `unknown` + limitations.
    public static func check(
        input: String,
        environment: MacEnvironment? = nil,
        progress: (@Sendable (Stage) -> Void)? = nil
    ) throws -> ModelCheckReport {
        let ref: ModelRef
        do { ref = try ModelRef.parse(input) }
        catch let e as ModelRef.ParseError {
            throw CheckError.invalidInput(e.description)
        }

        progress?(.inspectingRepository)

        var info: HubModelClient.Info? = nil
        var fetchIssue: String? = nil
        do {
            info = try HubModelClient.info(id: ref.id, revision: ref.revision)
        } catch {
            fetchIssue = "\(error)"
        }

        // config.json is the one small file that unlocks the architecture
        // gates; model_index.json presence is already visible in siblings.
        var config: HuggingFaceConfig? = nil
        var configIssue: String? = nil
        var architecturesHint: [String] = []
        var remoteCode = false
        if let info = info {
            var rawConfig: [String: Any]? = nil
            if info.sibling(named: "config.json") != nil {
                do {
                    if let data = try HubModelClient.smallFile(
                        id: ref.id, revision: ref.revision, path: "config.json") {
                        rawConfig = (try JSONSerialization.jsonObject(with: data)) as? [String: Any]
                    }
                } catch {
                    configIssue = "config.json present but unreadable: \(error)"
                }
            }
            // Fallback: the Hub embeds the parsed config in the API
            // response — this is what unlocks gated repos, whose
            // resolve/ URLs 401 without a token.
            if rawConfig == nil, let api = info.apiConfig { rawConfig = api }
            if rawConfig == nil, info.sibling(named: "config.json") == nil, info.apiConfig == nil {
                configIssue = "no config.json in the repository file list"
            }
            if let raw = rawConfig {
                architecturesHint = (raw["architectures"] as? [String]) ?? []
                remoteCode = raw["auto_map"] != nil || info.customClass != nil
                do {
                    config = try HuggingFaceConfig.fromDict(normalizeLegacyKeys(raw))
                } catch {
                    configIssue = configIssue ?? "config parsed partially: \(error)"
                }
            }
        }

        // Structural evidence: tensor names from the safetensors index
        // (sharded repos) or a Range-read of the first shard's header.
        // Metadata only — a 200 (Range ignored) is refused, never a
        // weight download.
        var tensorLayout: TensorLayout? = nil
        var exactWeightBytes: Int64? = nil
        var exactParams: Int64? = nil
        if let info = info, !info.siblings(matchingSuffix: ".safetensors").isEmpty {
            if let fetched = try? HubModelClient.tensorNames(
                id: ref.id, revision: ref.revision, info: info) {
                tensorLayout = TensorLayout.assess(names: fetched.names)
                if let entries = fetched.entries {
                    var bytes: Int64 = 0
                    var params: Int64 = 0
                    for (name, e) in entries where name != "__metadata__" {
                        let shape = (e["shape"] as? [NSNumber])?.map(\.int64Value) ?? []
                        let count = shape.reduce(1, *)
                        params += count
                        bytes += count * Self.dtypeBytes(e["dtype"] as? String)
                    }
                    exactWeightBytes = bytes; exactParams = params
                }
            }
        }

        // PEFT/LoRA adapter repos: adapter_model.* + adapter_config.json
        // (which names the base model). Detected before format dispatch.
        var adapter: (base: String?, peftType: String?)? = nil
        if let info = info {
            let isAdapter = info.sibling(named: "adapter_config.json") != nil
                || info.sibling(named: "adapter_model.safetensors") != nil
                || info.sibling(named: "adapter_model.bin") != nil
                || info.libraryName == "peft"
                || info.tags.contains(where: { $0.lowercased() == "peft" || $0.lowercased() == "lora" })
            if isAdapter {
                var base = info.baseModel, peftType: String? = nil
                if let data = try? HubModelClient.smallFile(
                    id: ref.id, revision: ref.revision, path: "adapter_config.json"),
                   let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    base = base ?? (obj["base_model_name_or_path"] as? String)
                    peftType = obj["peft_type"] as? String
                }
                adapter = (base: base, peftType: peftType)
            }
        }

        // GGUF header: arch + quant + context for the selected variant.
        var ggufMeta: GGUFHeader.Meta? = nil
        if let info = info, adapter == nil {
            let ggufs = info.siblings(matchingSuffix: ".gguf")
            if !ggufs.isEmpty {
                let preferred = ["q4_k_m", "q5_k_m", "q4_0", "q8_0", "f16"]
                let variant = preferred.compactMap({ tag in
                    ggufs.first { $0.name.lowercased().contains(tag) }
                }).first ?? ggufs.max(by: { ($0.size ?? 0) < ($1.size ?? 0) })
                if let variant {
                    ggufMeta = try? HubModelClient.ggufMeta(
                        id: ref.id, revision: ref.revision, path: variant.name)
                }
            }
        }

        progress?(.checkingEnvironment)
        let env = environment ?? MacEnvironment.detect()

        progress?(.preparingReport)
        let rulesInput = CompatibilityRules.Input(
            ref: ref, info: info, fetchIssue: fetchIssue,
            config: config, configIssue: configIssue,
            architecturesHint: architecturesHint,
            tensorLayout: tensorLayout, remoteCode: remoteCode,
            adapter: adapter, ggufMeta: ggufMeta,
            exactWeightBytes: exactWeightBytes, exactParams: exactParams,
            env: env)
        let a = CompatibilityRules.assess(rulesInput)

        let report = ModelCheckReport(
            schemaVersion: 2,
            checkedAt: ISO8601DateFormatter().string(from: Date()),
            input: input,
            model: .init(
                id: ref.id, revision: ref.revision,
                task: a.task, library: a.library,
                architectures: a.architectures, formats: a.formats,
                selectedVariant: a.selectedVariant,
                gated: a.gated, lastModified: a.lastModified),
            environment: .init(
                chip: env.chip, arch: env.arch, ramBytes: env.ramBytes,
                freeDiskBytes: env.freeDiskBytes, macOSVersion: env.macOSVersion,
                source: env.source, runtimes: env.runtimes),
            verdict: a.verdict,
            verdictSummary: a.verdictSummary,
            checkedPath: a.checkedPath,
            otherPaths: a.otherPaths,
            requiredChanges: a.requiredChanges,
            tools: CompatibilityRules.toolMatrix(input: rulesInput, assessment: a),
            evidence: a.evidence,
            nextActions: a.nextActions,
            agentPrompt: "",   // filled below
            limitations: a.limitations)

        let storedReceipt = env.source == "detected"
            ? ModelVerificationStore().load(
                modelID: ref.id, revision: ref.revision,
                environment: report.environment)
            : nil
        let hasHFAccess = !(ProcessInfo.processInfo.environment["HF_TOKEN"] ?? "").isEmpty
        var final = ModelCompatibilityContract.enrich(
            report, hasHFAccess: hasHFAccess, receipt: storedReceipt)
        final.agentPrompt = agentPrompt(for: final)
        return final
    }

    /// safetensors dtype string → bytes per element.
    static func dtypeBytes(_ dtype: String?) -> Int64 {
        switch dtype {
        case "F64", "I64", "U64": return 8
        case "F32", "I32", "U32": return 4
        case "F16", "BF16", "I16", "U16": return 2
        default: return 1   // I8/U8/F8_*/BOOL
        }
    }

    /// Legacy HF schemas use different key names — GPT-2/GPT-Neo/J use
    /// `n_head`/`n_embd`/`n_layer`, older models use `d_model`,
    /// `layer_norm_epsilon`, `ffn_dim`. Normalize aliases so the strict
    /// `HuggingFaceConfig` parser can read them; the architecture gate
    /// still decides the verdict, this only unlocks the parse.
    static let legacyConfigAliases: [String: [String]] = [
        "vocab_size": ["n_vocab"],
        "hidden_size": ["n_embd", "d_model", "dim"],
        "num_hidden_layers": ["n_layer", "num_layers", "n_layers"],
        "num_attention_heads": ["n_head", "n_heads", "num_heads"],
        "intermediate_size": ["n_inner", "ffn_dim", "mlp_dim"],
        "max_position_embeddings": ["n_positions", "n_ctx", "max_seq_len", "seq_length"],
        "rms_norm_eps": ["layer_norm_epsilon", "norm_eps", "layernorm_epsilon", "layer_norm_eps"],
        "hidden_act": ["activation_function", "hidden_activation"],
        "num_key_value_heads": ["n_head_kv", "multi_query_group_num", "num_kv_heads"],
        "rope_theta": ["rotary_emb_base", "rope_base"],
    ]

    static func normalizeLegacyKeys(_ raw: [String: Any]) -> [String: Any] {
        var out = raw
        for (canonical, aliases) in legacyConfigAliases where out[canonical] == nil {
            for alias in aliases {
                if let v = raw[alias] { out[canonical] = v; break }
            }
        }
        // GPT-2/GPT-Neo omit n_inner entirely — the MLP is implicitly
        // 4× hidden. Synthesize it so the strict parser can proceed;
        // intermediate_size only feeds memory/param estimates here.
        if out["intermediate_size"] == nil {
            let hidden = (out["hidden_size"] as? Int)
                ?? (out["n_embd"] as? Int) ?? (out["d_model"] as? Int)
            if let hidden { out["intermediate_size"] = hidden * 4 }
        }
        return out
    }

    /// The copy-ready handoff for cases the checker can't close. Carries
    /// the exact model/revision, environment, observed findings, sources,
    /// and open questions — and instructs the receiving agent to
    /// investigate before proposing changes.
    public static func agentPrompt(for r: ModelCheckReport) -> String {
        var lines = [
            "Investigate whether and how this Hugging Face model can run on the described Mac, then report findings BEFORE proposing or making any changes. Do not install software, download weights, or modify the machine without explicit confirmation.",
            "",
        ]
        appendModelSummary(r, to: &lines)
        appendEnvironmentSummary(r, to: &lines)
        appendCompatibilitySummary(r, to: &lines)
        lines.append("")
        lines.append("Evidence:")
        for evidence in r.evidence {
            lines.append("- [\(evidence.kind)] \(evidence.detail) — \(evidence.source)")
        }
        lines += [
            "",
            "Questions to resolve:",
            "- Is there a documented execution path on Apple Silicon for this exact repo/revision?",
            "- What are the real memory, disk, and runtime requirements — verified against official documentation, not assumed?",
            "- If the checked path is wrong or incomplete, what did the checker miss?",
        ]
        return lines.joined(separator: "\n")
    }

    private static func appendModelSummary(
        _ report: ModelCheckReport,
        to lines: inout [String]
    ) {
        lines.append("Model: https://huggingface.co/\(report.model.id) (revision: \(report.model.revision))")
        if let task = report.model.task { lines.append("Task: \(task)") }
        if !report.model.architectures.isEmpty {
            lines.append("Architectures: \(report.model.architectures.joined(separator: ", "))")
        }
        if !report.model.formats.isEmpty {
            lines.append("Formats seen: \(report.model.formats.joined(separator: ", "))")
        }
        if report.model.gated {
            lines.append("Repo is gated — an HF_TOKEN with accepted license terms is required.")
        }
    }

    private static func appendEnvironmentSummary(
        _ report: ModelCheckReport,
        to lines: inout [String]
    ) {
        lines.append("")
        lines.append("Environment (\(report.environment.source)):")
        lines.append("- chip: \(report.environment.chip) (\(report.environment.arch))")
        lines.append("- RAM: \(ModelCheckReport.fmtBytes(report.environment.ramBytes)); free disk: \(ModelCheckReport.fmtBytes(report.environment.freeDiskBytes)); \(report.environment.macOSVersion)")
        let found = report.environment.runtimes.filter(\.found)
        if !found.isEmpty {
            let runtimes = found.map {
                "\($0.name) \($0.version ?? "")".trimmingCharacters(in: .whitespaces)
            }.joined(separator: "; ")
            lines.append("- runtimes: \(runtimes)")
        }
    }

    private static func appendCompatibilitySummary(
        _ report: ModelCheckReport,
        to lines: inout [String]
    ) {
        lines.append("")
        lines.append("Checker verdict: \(report.verdict.rawValue) — \(report.verdictSummary)")
        lines.append("Checked path: \(report.checkedPath.name) → \(report.checkedPath.status.rawValue): \(report.checkedPath.detail)")
        if let operations = report.operations, !operations.isEmpty {
            lines.append("Operation-specific states:")
            for operation in operations {
                lines.append("- \(operation.operation.rawValue): \(operation.status.rawValue) — \(operation.detail)")
            }
        }
        if let receipt = report.verificationReceipt {
            let runtime = receipt.runtime.map { " via \($0)" } ?? ""
            lines.append("Matching local receipt: \(receipt.status.rawValue)\(runtime), \(receipt.verifiedAt).")
        }
        if !report.otherPaths.isEmpty {
            lines.append("Other paths considered:")
            for path in report.otherPaths {
                lines.append("- \(path.name) [\(path.status.rawValue), \(path.evidenceKind)]: \(path.detail)")
            }
        }
        if !report.requiredChanges.isEmpty {
            lines.append("Required changes identified:")
            for change in report.requiredChanges {
                lines.append("- [\(change.kind)] \(change.detail)")
            }
        }
        if !report.limitations.isEmpty {
            lines.append("Limitations / unresolved questions:")
            for limitation in report.limitations { lines.append("- \(limitation)") }
        }
    }
}
