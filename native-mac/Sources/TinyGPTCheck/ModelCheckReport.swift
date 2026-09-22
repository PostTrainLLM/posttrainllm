import Foundation

/// Shared report schema for `posttrainllm model-check` and the Mac app's
/// "Check model compatibility" panel. Both surfaces render this single
/// Codable type — the CLI prints `renderText()` or encodes `--json`, the
/// app decodes the same struct for its cards. Keep field names stable:
/// the JSON output is a contract for agent handoffs.
///
/// Summary verdict vocabulary (from the feature spec — issue #156):
///   expected_to_work / changes_required / unsupported_on_checked_path / unknown
/// "Unsupported by your installed runtime" must never be reported as
/// "impossible on your Mac"; unknown is a first-class, acceptable result.
///
/// Schema v2 (issue #161) adds operation-specific predictions, explicit
/// execution stages, and an optional measured `model-run` receipt. The new
/// fields stay optional in the Codable shape so saved schema-v1 reports still
/// decode; reports produced by current code always populate them.
public struct ModelCheckReport: Codable, Equatable, Sendable {
    public var schemaVersion: Int
    public var checkedAt: String            // ISO-8601
    public var input: String                // raw user input, verbatim
    public var model: ModelSection
    public var environment: EnvironmentSection
    public var verdict: Verdict
    public var verdictSummary: String
    public var checkedPath: PathAssessment
    public var otherPaths: [ExecutionPath]
    public var requiredChanges: [RequiredChange]
    public var tools: [ToolOption]
    public var evidence: [Evidence]
    public var nextActions: [String]
    public var agentPrompt: String
    public var limitations: [String]
    public var operations: [OperationAssessment]? = nil
    public var executionStages: [ExecutionStage]? = nil
    public var verificationReceipt: VerificationReceipt? = nil

    public enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case checkedAt = "checked_at"
        case input, model, environment, verdict
        case verdictSummary = "verdict_summary"
        case checkedPath = "checked_path"
        case otherPaths = "other_paths"
        case requiredChanges = "required_changes"
        case tools, evidence
        case nextActions = "next_actions"
        case agentPrompt = "agent_prompt"
        case limitations
        case operations
        case executionStages = "execution_stages"
        case verificationReceipt = "verification_receipt"
    }

    public enum Verdict: String, Codable, Sendable {
        case expectedToWork = "expected_to_work"
        case changesRequired = "changes_required"
        case unsupportedOnCheckedPath = "unsupported_on_checked_path"
        case unknown = "unknown"

        public var displayName: String {
            switch self {
            case .expectedToWork: return "Expected to work"
            case .changesRequired: return "Changes required"
            case .unsupportedOnCheckedPath: return "Unsupported on checked path"
            case .unknown: return "Unknown"
            }
        }
    }

    public struct ModelSection: Codable, Equatable, Sendable {
        public var id: String               // "owner/repo"
        public var revision: String
        public var task: String?            // HF pipeline_tag
        public var library: String?         // HF library_name
        public var architectures: [String]
        public var formats: [String]        // "safetensors", "gguf", "diffusers", ...
        public var selectedVariant: String? // e.g. the GGUF quant we'd pick
        public var gated: Bool
        public var lastModified: String?

        enum CodingKeys: String, CodingKey {
            case id, revision, task, library, architectures, formats, gated
            case selectedVariant = "selected_variant"
            case lastModified = "last_modified"
        }
    }

    public struct EnvironmentSection: Codable, Equatable, Sendable {
        public var chip: String
        public var arch: String
        public var ramBytes: Int64
        public var freeDiskBytes: Int64
        public var macOSVersion: String
        public var source: String           // "detected" | "manual"
        public var runtimes: [RuntimeProbe]

        enum CodingKeys: String, CodingKey {
            case chip, arch, source, runtimes
            case ramBytes = "ram_bytes"
            case freeDiskBytes = "free_disk_bytes"
            case macOSVersion = "macos_version"
        }
    }

    public struct RuntimeProbe: Codable, Equatable, Sendable {
        public var name: String
        public var found: Bool
        public var version: String?
        public var detail: String?          // how it was probed
    }

    /// Verdict for one concrete execution path. `status` reuses Verdict
    /// minus `unknown` semantics — paths we cannot establish are simply
    /// not listed, and the report says so in `limitations`.
    public struct PathAssessment: Codable, Equatable, Sendable {
        public var name: String
        public var status: Verdict
        public var detail: String
    }

    public struct ExecutionPath: Codable, Equatable, Sendable {
        public var name: String             // "Ollama", "llama.cpp", "mlx-lm", ...
        public var status: Verdict
        public var detail: String
        public var source: String?          // documentation URL backing the claim
        public var evidenceKind: String     // "documented" | "inferred"

        enum CodingKeys: String, CodingKey {
            case name, status, detail, source
            case evidenceKind = "evidence_kind"
        }
    }

    /// One runnable tool and whether it applies to this model — the
    /// "what all can run it" matrix. `availability` is about this Mac:
    /// bundled (compiled into posttrainllm) / installed (probed) /
    /// not_installed / unknown (not probed). `applies` is about the
    /// model: would this tool actually execute it.
    public struct ToolOption: Codable, Equatable, Sendable {
        public var name: String
        public var availability: String   // bundled | installed | not_installed | unknown
        public var applies: Bool
        public var detail: String
        public var run: String?           // the command, when known
    }

    public struct RequiredChange: Codable, Equatable, Sendable {
        public var kind: String             // runtime | software | model-component | conversion | memory | access
        public var detail: String
        public var sizeBytes: Int64?
        public var estimate: Bool           // true when sizeBytes is inferred

        enum CodingKeys: String, CodingKey {
            case kind, detail, estimate
            case sizeBytes = "size_bytes"
        }
    }

    public struct Evidence: Codable, Equatable, Sendable {
        public var source: String           // URL, or "local system probe"
        public var kind: String             // "documented" | "inferred"
        public var detail: String
    }

    public enum Operation: String, Codable, CaseIterable, Sendable {
        case inspect
        case download
        case load
        case inference
        case loraSFT = "lora_sft"
        case agenticUse = "agentic_use"

        public var displayName: String {
            switch self {
            case .inspect: return "Inspect"
            case .download: return "Download"
            case .load: return "Load"
            case .inference: return "Inference"
            case .loraSFT: return "LoRA / SFT"
            case .agenticUse: return "Agentic use"
            }
        }
    }

    public enum OperationStatus: String, Codable, Sendable {
        case supported
        case blocked
        case unverified
        case verifiedOnThisDevice = "verified_on_this_device"

        public var displayName: String {
            switch self {
            case .supported: return "Supported (predicted)"
            case .blocked: return "Blocked"
            case .unverified: return "Unverified"
            case .verifiedOnThisDevice: return "Verified on this device"
            }
        }
    }

    public struct OperationAssessment: Codable, Equatable, Sendable {
        public var operation: Operation
        public var status: OperationStatus
        public var detail: String

        public init(operation: Operation, status: OperationStatus, detail: String) {
            self.operation = operation
            self.status = status
            self.detail = detail
        }
    }

    public enum ExecutionStageName: String, Codable, CaseIterable, Sendable {
        case inspect
        case validate
        case download
        case load
        case warmUp = "warm_up"
        case smokeTest = "smoke_test"
        case ready

        public var displayName: String {
            rawValue.replacingOccurrences(of: "_", with: " ")
        }
    }

    public enum ExecutionStageStatus: String, Codable, Sendable {
        case passed
        case pending
        case blocked
        case failed
    }

    public struct ExecutionStage: Codable, Equatable, Sendable {
        public var stage: ExecutionStageName
        public var status: ExecutionStageStatus
        public var detail: String

        public init(stage: ExecutionStageName, status: ExecutionStageStatus, detail: String) {
            self.stage = stage
            self.status = status
            self.detail = detail
        }
    }

    public enum VerificationStatus: String, Codable, Sendable {
        case verified
        case blocked
        case failed
    }

    public struct VerificationAttempt: Codable, Equatable, Sendable {
        public var runtime: String
        public var runtimeVersion: String?
        public var status: VerificationStatus
        public var failureStage: ExecutionStageName?
        public var stderr: String?
        public var durationMS: Int
        public var requestedTokens: Int
        public var promptTokens: Int?
        public var generatedTokens: Int?
        public var outputCharacters: Int

        enum CodingKeys: String, CodingKey {
            case runtime, status, stderr
            case runtimeVersion = "runtime_version"
            case failureStage = "failure_stage"
            case durationMS = "duration_ms"
            case requestedTokens = "requested_tokens"
            case promptTokens = "prompt_tokens"
            case generatedTokens = "generated_tokens"
            case outputCharacters = "output_characters"
        }

        public init(runtime: String, runtimeVersion: String? = nil,
                    status: VerificationStatus, failureStage: ExecutionStageName? = nil,
                    stderr: String? = nil, durationMS: Int, requestedTokens: Int,
                    promptTokens: Int? = nil, generatedTokens: Int? = nil,
                    outputCharacters: Int = 0) {
            self.runtime = runtime
            self.runtimeVersion = runtimeVersion
            self.status = status
            self.failureStage = failureStage
            self.stderr = stderr
            self.durationMS = durationMS
            self.requestedTokens = requestedTokens
            self.promptTokens = promptTokens
            self.generatedTokens = generatedTokens
            self.outputCharacters = outputCharacters
        }
    }

    public struct VerificationReceipt: Codable, Equatable, Sendable {
        public var schemaVersion: Int
        public var modelID: String
        public var revision: String
        public var environmentFingerprint: String
        public var verifiedAt: String
        public var status: VerificationStatus
        public var runtime: String?
        public var runtimeVersion: String?
        public var failureStage: ExecutionStageName?
        public var attempts: [VerificationAttempt]

        enum CodingKeys: String, CodingKey {
            case schemaVersion = "schema_version"
            case modelID = "model_id"
            case revision
            case environmentFingerprint = "environment_fingerprint"
            case verifiedAt = "verified_at"
            case status, runtime, attempts
            case runtimeVersion = "runtime_version"
            case failureStage = "failure_stage"
        }

        public init(schemaVersion: Int = 1, modelID: String, revision: String,
                    environmentFingerprint: String, verifiedAt: String,
                    status: VerificationStatus, runtime: String? = nil,
                    runtimeVersion: String? = nil,
                    failureStage: ExecutionStageName? = nil,
                    attempts: [VerificationAttempt] = []) {
            self.schemaVersion = schemaVersion
            self.modelID = modelID
            self.revision = revision
            self.environmentFingerprint = environmentFingerprint
            self.verifiedAt = verifiedAt
            self.status = status
            self.runtime = runtime
            self.runtimeVersion = runtimeVersion
            self.failureStage = failureStage
            self.attempts = attempts
        }
    }

    /// JSON encoding used by `model-check --json` and any tooling that
    /// consumes the report. Pretty-printed with stable key order so diffs
    /// between runs are meaningful.
    public func encoded() throws -> String {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        return String(decoding: try enc.encode(self), as: UTF8.self)
    }

    public static func decode(_ data: Data) throws -> ModelCheckReport {
        try JSONDecoder().decode(ModelCheckReport.self, from: data)
    }

    /// Human-readable rendering shared by the CLI. The app renders the
    /// same fields natively; this is the text contract for copy/paste and
    /// terminal output.
    public func renderText() -> String {
        var out: [String] = []
        out.append("")
        out.append("Model compatibility: \(model.id) @ \(model.revision)")
        out.append(String(repeating: "-", count: 64))
        out.append("verdict: \(verdict.displayName)")
        out.append("  \(verdictSummary)")
        appendModel(to: &out)
        appendEnvironment(to: &out)
        appendOperations(to: &out)
        appendExecutionStages(to: &out)
        out.append("")
        out.append("Checked path: \(checkedPath.name)")
        out.append("  status: \(checkedPath.status.displayName)")
        out.append("  \(checkedPath.detail)")
        appendOtherPaths(to: &out)
        appendTools(to: &out)
        appendRequiredChanges(to: &out)
        appendListSection("Next action", values: nextActions, to: &out)
        appendListSection("Limitations", values: limitations, to: &out)
        appendEvidence(to: &out)
        out.append("")
        out.append("Checked at \(checkedAt) · schema v\(schemaVersion)")
        out.append("Use the report's agent_prompt field for a copy-ready investigation handoff.")
        return out.joined(separator: "\n")
    }

    private func appendOperations(to out: inout [String]) {
        guard let operations, !operations.isEmpty else { return }
        out.append("")
        out.append("Operations")
        for operation in operations {
            out.append("  \(operation.operation.displayName): \(operation.status.displayName)")
            out.append("    \(operation.detail)")
        }
    }

    private func appendExecutionStages(to out: inout [String]) {
        guard let executionStages, !executionStages.isEmpty else { return }
        out.append("")
        out.append("Execution stages")
        for stage in executionStages {
            out.append("  \(stage.stage.displayName): \(stage.status.rawValue)")
            out.append("    \(stage.detail)")
        }
        guard let receipt = verificationReceipt else { return }
        let runtime = receipt.runtime.map { " via \($0)" } ?? ""
        out.append("  receipt: \(receipt.status.rawValue)\(runtime) at \(receipt.verifiedAt)")
    }

    private func appendModel(to out: inout [String]) {
        out.append("")
        out.append("Model")
        out.append("  task:          \(model.task ?? "unknown")")
        out.append("  library:       \(model.library ?? "unknown")")
        out.append("  architectures: \(model.architectures.isEmpty ? "unknown" : model.architectures.joined(separator: ", "))")
        out.append("  formats:       \(model.formats.isEmpty ? "unknown" : model.formats.joined(separator: ", "))")
        if let variant = model.selectedVariant { out.append("  variant:       \(variant)") }
        if model.gated { out.append("  gated:         yes (HF_TOKEN required)") }
    }

    private func appendEnvironment(to out: inout [String]) {
        out.append("")
        out.append("Environment (\(environment.source))")
        out.append("  chip:     \(environment.chip) (\(environment.arch))")
        out.append("  RAM:      \(Self.fmtBytes(environment.ramBytes))")
        out.append("  disk free: \(Self.fmtBytes(environment.freeDiskBytes))")
        out.append("  macOS:    \(environment.macOSVersion)")
        guard !environment.runtimes.isEmpty else { return }
        out.append("  runtimes:")
        for runtime in environment.runtimes where runtime.found {
            out.append("    \(runtime.name) \(runtime.version ?? "(version unknown)")")
        }
        let missing = environment.runtimes.filter { !$0.found }.map(\.name)
        if !missing.isEmpty { out.append("    not found: \(missing.joined(separator: ", "))") }
    }

    private func appendOtherPaths(to out: inout [String]) {
        guard !otherPaths.isEmpty else { return }
        out.append("")
        out.append("Other Mac execution paths")
        for path in otherPaths {
            let source = path.source.map { " — \($0)" } ?? ""
            out.append("  \(path.name) [\(path.status.displayName), \(path.evidenceKind)]\(source)")
            out.append("    \(path.detail)")
        }
    }

    private func appendTools(to out: inout [String]) {
        guard !tools.isEmpty else { return }
        out.append("")
        out.append("Tools that can run this model")
        let usable = tools.filter { $0.applies && $0.availability != "not_installed" }
        let absent = tools.filter { $0.applies && $0.availability == "not_installed" }
        for tool in usable {
            out.append("  ✓ \(tool.name) [\(tool.availability)]\(tool.run.map { " — \($0)" } ?? "")")
            out.append("    \(tool.detail)")
        }
        for tool in absent {
            out.append("  · \(tool.name) [not installed]\(tool.run.map { " — \($0)" } ?? "")")
        }
        let unavailable = tools.filter { !$0.applies }
        if !unavailable.isEmpty { out.append("  n/a: \(unavailable.map(\.name).joined(separator: ", "))") }
    }

    private func appendRequiredChanges(to out: inout [String]) {
        guard !requiredChanges.isEmpty else { return }
        out.append("")
        out.append("Required changes")
        for change in requiredChanges {
            var line = "  [\(change.kind)] \(change.detail)"
            if let size = change.sizeBytes {
                line += " (\(Self.fmtBytes(size))\(change.estimate ? ", estimate" : ""))"
            }
            out.append(line)
        }
    }

    private func appendListSection(_ title: String, values: [String], to out: inout [String]) {
        guard !values.isEmpty else { return }
        out.append("")
        out.append(title)
        for value in values { out.append("  • \(value)") }
    }

    private func appendEvidence(to out: inout [String]) {
        guard !evidence.isEmpty else { return }
        out.append("")
        out.append("Evidence")
        for item in evidence {
            out.append("  [\(item.kind)] \(item.detail)")
            out.append("    \(item.source)")
        }
    }

    public static func fmtBytes(_ n: Int64) -> String {
        if n >= 1_073_741_824 { return String(format: "%.1f GB", Double(n) / 1_073_741_824) }
        if n >= 1_048_576 { return String(format: "%.0f MB", Double(n) / 1_048_576) }
        if n >= 1_024 { return String(format: "%.0f KB", Double(n) / 1_024) }
        return "\(n) B"
    }
}
