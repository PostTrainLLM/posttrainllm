import Foundation
import TinyGPTIO

/// The one inspection flow behind `posttrainllm model-check` and the Mac
/// app's "Check model compatibility" panel. Read-only end to end:
///
///   URL + environment
///     → fetch repository metadata + small config files
///     → apply known compatibility checks
///     → produce a structured report
///
/// It never downloads weights, installs software, runs a model, or
/// executes repository code. Missing metadata and failed lookups produce
/// explicit limitations, not invented claims — `unknown` is a valid
/// outcome.
public enum ModelCheckService {

    public typealias ProgressHandler = @Sendable (Stage) -> Void

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
        progress: ProgressHandler? = nil
    ) throws -> ModelCheckReport {
        try performCheck(input: input, environment: environment, progress: progress)
    }

    private struct ConfigFacts {
        var config: HuggingFaceConfig?
        var issue: String?
        var architectures: [String] = []
        var remoteCode = false
    }

    private static func readConfig(ref: ModelRef, info: HubModelClient.Info?) -> ConfigFacts {
        guard let info else { return ConfigFacts() }
        var facts = ConfigFacts()
        var raw: [String: Any]?
        if info.sibling(named: "config.json") != nil {
            do {
                if let data = try HubModelClient.smallFile(
                    id: ref.id, revision: ref.revision, path: "config.json") {
                    raw = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                }
            } catch {
                facts.issue = "config.json present but unreadable: \(error)"
            }
        }
        if raw == nil { raw = info.apiConfig }
        if raw == nil, info.sibling(named: "config.json") == nil, info.apiConfig == nil {
            facts.issue = "no config.json in the repository file list"
        }
        guard let raw else { return facts }
        facts.architectures = (raw["architectures"] as? [String]) ?? []
        facts.remoteCode = raw["auto_map"] != nil || info.customClass != nil
        do { facts.config = try HuggingFaceConfig.fromDict(normalizeLegacyKeys(raw)) }
        catch { facts.issue = facts.issue ?? "config parsed partially: \(error)" }
        return facts
    }

    private struct TensorFacts {
        var layout: TensorLayout?
        var bytes: Int64?
        var params: Int64?
    }

    private static func readTensorFacts(
        ref: ModelRef, info: HubModelClient.Info?
    ) -> TensorFacts {
        guard let info, !info.siblings(matchingSuffix: ".safetensors").isEmpty,
              let fetched = try? HubModelClient.tensorNames(
                  id: ref.id, revision: ref.revision, info: info) else {
            return TensorFacts()
        }
        var facts = TensorFacts(layout: TensorLayout.assess(names: fetched.names))
        if let entries = fetched.entries {
            (facts.bytes, facts.params) = exactTensorTotals(entries)
        }
        return facts
    }

    private static func readAdapter(
        ref: ModelRef, info: HubModelClient.Info?
    ) -> (base: String?, peftType: String?)? {
        guard let info else { return nil }
        let adapterFiles = info.sibling(named: "adapter_config.json") != nil
            || info.sibling(named: "adapter_model.safetensors") != nil
            || info.sibling(named: "adapter_model.bin") != nil
        let adapterLabels = info.libraryName == "peft"
            || info.tags.contains { ["peft", "lora"].contains($0.lowercased()) }
        guard adapterFiles || adapterLabels else { return nil }
        var base = info.baseModel
        var peftType: String?
        if let data = try? HubModelClient.smallFile(
            id: ref.id, revision: ref.revision, path: "adapter_config.json"),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            base = base ?? (object["base_model_name_or_path"] as? String)
            peftType = object["peft_type"] as? String
        }
        return (base, peftType)
    }

    private static func readGGUFMeta(
        ref: ModelRef, info: HubModelClient.Info?,
        adapter: (base: String?, peftType: String?)?
    ) -> GGUFHeader.Meta? {
        guard let info, adapter == nil else { return nil }
        let files = info.siblings(matchingSuffix: ".gguf")
        let preferred = ["q4_k_m", "q5_k_m", "q4_0", "q8_0", "f16"]
        let requested = ref.filePath.flatMap { path in
            path.lowercased().hasSuffix(".gguf") ? HubModelClient.Sibling(
                name: path, size: files.first { $0.name == path }?.size) : nil
        }
        let variant = requested ?? preferred.compactMap { tag in
            files.first { $0.name.lowercased().contains(tag) }
        }.first ?? files.max(by: { ($0.size ?? 0) < ($1.size ?? 0) })
        guard let variant else { return nil }
        return try? HubModelClient.ggufMeta(
            id: ref.id, revision: ref.revision, path: variant.name
        )
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

    /// Untrusted safetensors headers must not be able to overflow the
    /// checker. If any dimension or aggregate is invalid, keep the exact
    /// totals unknown and let the manifest-based estimate remain visible.
    static func exactTensorTotals(
        _ entries: [String: [String: Any]]
    ) -> (bytes: Int64?, params: Int64?) {
        var bytes: Int64 = 0
        var params: Int64 = 0
        for (name, entry) in entries where name != "__metadata__" {
            let shape = (entry["shape"] as? [NSNumber])?.map(\.int64Value) ?? []
            var count: Int64 = 1
            for dimension in shape {
                guard dimension >= 0 else { return (nil, nil) }
                let product = count.multipliedReportingOverflow(by: dimension)
                guard !product.overflow else { return (nil, nil) }
                count = product.partialValue
            }
            let paramTotal = params.addingReportingOverflow(count)
            let tensorBytes = count.multipliedReportingOverflow(
                by: dtypeBytes(entry["dtype"] as? String)
            )
            guard !paramTotal.overflow, !tensorBytes.overflow else { return (nil, nil) }
            let byteTotal = bytes.addingReportingOverflow(tensorBytes.partialValue)
            guard !byteTotal.overflow else { return (nil, nil) }
            params = paramTotal.partialValue
            bytes = byteTotal.partialValue
        }
        return (bytes, params)
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
            if let hidden {
                let scaled = hidden.multipliedReportingOverflow(by: 4)
                if !scaled.overflow { out["intermediate_size"] = scaled.partialValue }
            }
        }
        return out
    }

    /// The copy-ready handoff for cases the checker can't close. Carries
    /// the exact model/revision, environment, observed findings, sources,
    /// and open questions — and instructs the receiving agent to
    /// investigate before proposing changes.
    public static func agentPrompt(for r: ModelCheckReport) -> String {
        var p: [String] = []
        p.append("Investigate whether and how this Hugging Face model can run on the described Mac, then report findings BEFORE proposing or making any changes. Do not install software, download weights, or modify the machine without explicit confirmation.")
        p.append("")
        p.append("Model: https://huggingface.co/\(r.model.id) (revision: \(r.model.revision))")
        if let t = r.model.task { p.append("Task: \(t)") }
        if !r.model.architectures.isEmpty {
            p.append("Architectures: \(r.model.architectures.joined(separator: ", "))")
        }
        if !r.model.formats.isEmpty {
            p.append("Formats seen: \(r.model.formats.joined(separator: ", "))")
        }
        if r.model.gated { p.append("Repo is gated — an HF_TOKEN with accepted license terms is required.") }
        p.append("")
        p.append("Environment (\(r.environment.source)):")
        p.append("- chip: \(r.environment.chip) (\(r.environment.arch))")
        p.append("- RAM: \(ModelCheckReport.fmtBytes(r.environment.ramBytes)); free disk: \(ModelCheckReport.fmtBytes(r.environment.freeDiskBytes)); \(r.environment.macOSVersion)")
        let found = r.environment.runtimes.filter(\.found)
        if !found.isEmpty {
            p.append("- runtimes: " + found.map { "\($0.name) \($0.version ?? "")".trimmingCharacters(in: .whitespaces) }.joined(separator: "; "))
        }
        p.append("")
        p.append("Checker verdict: \(r.verdict.rawValue) — \(r.verdictSummary)")
        p.append("Checked path: \(r.checkedPath.name) → \(r.checkedPath.status.rawValue): \(r.checkedPath.detail)")
        appendOperationEvidence(r, to: &p)
        appendAlternativePaths(r, to: &p)
        appendLimitationsAndEvidence(r, to: &p)
        p.append("")
        p.append("Questions to resolve:")
        p.append("- Is there a documented execution path on Apple Silicon for this exact repo/revision?")
        p.append("- What are the real memory, disk, and runtime requirements — verified against official documentation, not assumed?")
        p.append("- If the checked path is wrong or incomplete, what did the checker miss?")
        return p.joined(separator: "\n")
    }

    private static func appendOperationEvidence(_ r: ModelCheckReport, to p: inout [String]) {
        if let operations = r.operations, !operations.isEmpty {
            p.append("Operation-specific states:")
            for operation in operations {
                p.append("- \(operation.operation.rawValue): \(operation.status.rawValue) — \(operation.detail)")
            }
        }
        if let receipt = r.verificationReceipt {
            let runtime = receipt.runtime.map { " via \($0)" } ?? ""
            p.append("Matching local receipt: \(receipt.status.rawValue)\(runtime), \(receipt.verifiedAt).")
        }
    }

    private static func appendAlternativePaths(_ r: ModelCheckReport, to p: inout [String]) {
        if !r.otherPaths.isEmpty {
            p.append("Other paths considered:")
            for path in r.otherPaths {
                p.append("- \(path.name) [\(path.status.rawValue), \(path.evidenceKind)]: \(path.detail)")
            }
        }
        if !r.requiredChanges.isEmpty {
            p.append("Required changes identified:")
            for c in r.requiredChanges { p.append("- [\(c.kind)] \(c.detail)") }
        }
    }

    private static func appendLimitationsAndEvidence(_ r: ModelCheckReport, to p: inout [String]) {
        if !r.limitations.isEmpty {
            p.append("Limitations / unresolved questions:")
            for l in r.limitations { p.append("- \(l)") }
        }
        p.append("")
        p.append("Evidence:")
        for e in r.evidence { p.append("- [\(e.kind)] \(e.detail) — \(e.source)") }
    }

    private static func performCheck(
        input: String, environment: MacEnvironment?, progress: ProgressHandler?
    ) throws -> ModelCheckReport {
        let ref: ModelRef
        do { ref = try ModelRef.parse(input) }
        catch let error as ModelRef.ParseError {
            throw CheckError.invalidInput(error.description)
        }
        progress?(.inspectingRepository)
        var info: HubModelClient.Info?
        var fetchIssue: String?
        do { info = try HubModelClient.info(id: ref.id, revision: ref.revision) }
        catch { fetchIssue = "\(error)" }

        let config = readConfig(ref: ref, info: info)
        let tensors = readTensorFacts(ref: ref, info: info)
        let adapter = readAdapter(ref: ref, info: info)
        let gguf = readGGUFMeta(ref: ref, info: info, adapter: adapter)
        progress?(.checkingEnvironment)
        let env = environment ?? MacEnvironment.detect()
        progress?(.preparingReport)

        var rules = CompatibilityRules.Input(ref: ref, env: env)
        rules.info = info
        rules.fetchIssue = fetchIssue
        rules.config = config.config
        rules.configIssue = config.issue
        rules.architecturesHint = config.architectures
        rules.tensorLayout = tensors.layout
        rules.remoteCode = config.remoteCode
        rules.adapter = adapter
        rules.ggufMeta = gguf
        rules.exactWeightBytes = tensors.bytes
        rules.exactParams = tensors.params
        let assessment = CompatibilityRules.assess(rules)

        let report = ModelCheckReport(
            schemaVersion: 2,
            checkedAt: ISO8601DateFormatter().string(from: Date()),
            input: input,
            model: ModelCheckReport.ModelSection(
                id: ref.id, revision: ref.revision, filePath: ref.filePath,
                task: assessment.task, library: assessment.library,
                architectures: assessment.architectures, formats: assessment.formats,
                selectedVariant: assessment.selectedVariant,
                gated: assessment.gated, lastModified: assessment.lastModified),
            environment: .init(
                chip: env.chip, arch: env.arch, ramBytes: env.ramBytes,
                freeDiskBytes: env.freeDiskBytes, macOSVersion: env.macOSVersion,
                source: env.source, runtimes: env.runtimes),
            verdict: assessment.verdict,
            verdictSummary: assessment.verdictSummary,
            checkedPath: assessment.checkedPath,
            otherPaths: assessment.otherPaths,
            requiredChanges: assessment.requiredChanges,
            tools: CompatibilityRules.toolMatrix(input: rules, assessment: assessment),
            evidence: assessment.evidence,
            nextActions: assessment.nextActions,
            agentPrompt: "",
            limitations: assessment.limitations)
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
}
