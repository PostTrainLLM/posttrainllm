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
        if let info = info, info.sibling(named: "config.json") != nil {
            do {
                if let data = try HubModelClient.smallFile(
                    id: ref.id, revision: ref.revision, path: "config.json") {
                    config = try HuggingFaceConfig.fromDict(
                        (try JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:])
                }
            } catch {
                configIssue = "config.json present but unreadable: \(error)"
            }
        } else if info != nil {
            configIssue = "no config.json in the repository file list"
        }

        progress?(.checkingEnvironment)
        let env = environment ?? MacEnvironment.detect()

        progress?(.preparingReport)
        let rulesInput = CompatibilityRules.Input(
            ref: ref, info: info, fetchIssue: fetchIssue,
            config: config, configIssue: configIssue, env: env)
        let a = CompatibilityRules.assess(rulesInput)

        let report = ModelCheckReport(
            schemaVersion: 1,
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
            evidence: a.evidence,
            nextActions: a.nextActions,
            agentPrompt: "",   // filled below
            limitations: a.limitations)

        var final = report
        final.agentPrompt = agentPrompt(for: final)
        return final
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
        if !r.limitations.isEmpty {
            p.append("Limitations / unresolved questions:")
            for l in r.limitations { p.append("- \(l)") }
        }
        p.append("")
        p.append("Evidence:")
        for e in r.evidence { p.append("- [\(e.kind)] \(e.detail) — \(e.source)") }
        p.append("")
        p.append("Questions to resolve:")
        p.append("- Is there a documented execution path on Apple Silicon for this exact repo/revision?")
        p.append("- What are the real memory, disk, and runtime requirements — verified against official documentation, not assumed?")
        p.append("- If the checked path is wrong or incomplete, what did the checker miss?")
        return p.joined(separator: "\n")
    }
}
