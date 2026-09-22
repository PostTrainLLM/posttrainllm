import Foundation

/// Shared report schema for `posttrainllm model-check` and the Mac app's
/// "Check model compatibility" panel. Both surfaces render this single
/// Codable type — the CLI prints `renderText()` or encodes `--json`, the
/// app decodes the same struct for its cards. Keep field names stable:
/// the JSON output is a contract for agent handoffs.
///
/// Verdict vocabulary (from the feature spec — issue #156):
///   expected_to_work / changes_required / unsupported_on_checked_path / unknown
/// "Unsupported by your installed runtime" must never be reported as
/// "impossible on your Mac"; unknown is a first-class, acceptable result.
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
        appendModelAndEnvironment(to: &out)
        appendPathsAndTools(to: &out)
        appendOutcomeDetails(to: &out)
        out.append("")
        out.append("Checked at \(checkedAt) · schema v\(schemaVersion)")
        out.append("Use the report's agent_prompt field for a copy-ready investigation handoff.")
        return out.joined(separator: "\n")
    }

    private func appendModelAndEnvironment(to out: inout [String]) {
        out += ["", "Model",
                "  task:          \(model.task ?? "unknown")",
                "  library:       \(model.library ?? "unknown")",
                "  architectures: \(model.architectures.isEmpty ? "unknown" : model.architectures.joined(separator: ", "))",
                "  formats:       \(model.formats.isEmpty ? "unknown" : model.formats.joined(separator: ", "))"]
        if let variant = model.selectedVariant { out.append("  variant:       \(variant)") }
        if model.gated { out.append("  gated:         yes (HF_TOKEN required)") }
        out += ["", "Environment (\(environment.source))",
                "  chip:     \(environment.chip) (\(environment.arch))",
                "  RAM:      \(Self.fmtBytes(environment.ramBytes))",
                "  disk free: \(Self.fmtBytes(environment.freeDiskBytes))",
                "  macOS:    \(environment.macOSVersion)"]
        if !environment.runtimes.isEmpty {
            out.append("  runtimes:")
            for rt in environment.runtimes where rt.found {
                out.append("    \(rt.name) \(rt.version ?? "(version unknown)")")
            }
            let missing = environment.runtimes.filter { !$0.found }.map(\.name)
            if !missing.isEmpty {
                out.append("    not found: \(missing.joined(separator: ", "))")
            }
        }
    }

    private func appendPathsAndTools(to out: inout [String]) {
        out += ["", "Checked path: \(checkedPath.name)",
                "  status: \(checkedPath.status.displayName)", "  \(checkedPath.detail)"]
        if !otherPaths.isEmpty {
            out += ["", "Other Mac execution paths"]
            for p in otherPaths {
                let src = p.source.map { " — \($0)" } ?? ""
                out.append("  \(p.name) [\(p.status.displayName), \(p.evidenceKind)]\(src)")
                out.append("    \(p.detail)")
            }
        }
        if !tools.isEmpty {
            out += ["", "Tools that can run this model"]
            let usable = tools.filter { $0.applies && $0.availability != "not_installed" }
            let absent = tools.filter { $0.applies && $0.availability == "not_installed" }
            for t in usable {
                out.append("  ✓ \(t.name) [\(t.availability)]\(t.run.map { " — \($0)" } ?? "")")
                out.append("    \(t.detail)")
            }
            for t in absent {
                out.append("  · \(t.name) [not installed]\(t.run.map { " — \($0)" } ?? "")")
            }
            let nA = tools.filter { !$0.applies }
            if !nA.isEmpty {
                out.append("  n/a: \(nA.map(\.name).joined(separator: ", "))")
            }
        }
    }

    private func appendOutcomeDetails(to out: inout [String]) {
        if !requiredChanges.isEmpty {
            out += ["", "Required changes"]
            for c in requiredChanges {
                var line = "  [\(c.kind)] \(c.detail)"
                if let s = c.sizeBytes {
                    line += " (\(Self.fmtBytes(s))\(c.estimate ? ", estimate" : ""))"
                }
                out.append(line)
            }
        }
        if !nextActions.isEmpty {
            out += ["", "Next action"]
            for a in nextActions { out.append("  • \(a)") }
        }
        if !limitations.isEmpty {
            out += ["", "Limitations"]
            for l in limitations { out.append("  • \(l)") }
        }
        if !evidence.isEmpty {
            out += ["", "Evidence"]
            for e in evidence {
                out.append("  [\(e.kind)] \(e.detail)")
                out.append("    \(e.source)")
            }
        }
    }

    public static func fmtBytes(_ n: Int64) -> String {
        if n >= 1_073_741_824 { return String(format: "%.1f GB", Double(n) / 1_073_741_824) }
        if n >= 1_048_576 { return String(format: "%.0f MB", Double(n) / 1_048_576) }
        if n >= 1_024 { return String(format: "%.0f KB", Double(n) / 1_024) }
        return "\(n) B"
    }
}
