import Foundation

/// Read/write helpers for the canonical `runs/<id>/` factory artifact folder.
///
/// This stays in TinyGPTIO so dashboards, reports, and CLI tools can validate
/// completed run metadata without loading MLX or model checkpoints.
public enum FactoryRunFolder {
    public static let configFile = "config.json"
    public static let datasetFile = "dataset.json"
    public static let baselineFile = "eval-baseline.json"
    public static let candidateFile = "eval-candidate.json"
    public static let artifactFile = "artifact.json"
    public static let decisionFile = "decision.json"
    public static let reportFile = "report.md"
    public static let trainLogFile = "train.log"
    public static let lifecycleFile = FactoryRunLifecycle.statusFile

    public static func write(_ bundle: FactoryRun.Bundle,
                             to directory: URL,
                             trainLog: String? = nil) throws {
        try bundle.validate()
        let fm = FileManager.default
        let hadConfig = fm.fileExists(
            atPath: directory.appendingPathComponent(configFile).path
        )
        let hadLifecycle = fm.fileExists(
            atPath: directory.appendingPathComponent(lifecycleFile).path
        )
        var lifecycle: FactoryRunLifecycle.Status?

        do {
            try fm.createDirectory(at: directory, withIntermediateDirectories: true)
            if hadLifecycle {
                lifecycle = try FactoryRunLifecycle.readStatus(directory: directory)
                if lifecycle!.phase.isTerminal {
                    throw FactoryRunLifecycle.LifecycleError.terminalState(
                        lifecycle!.phase
                    )
                }
                guard lifecycle!.runId == bundle.config.runId else {
                    throw FactoryRunLifecycle.LifecycleError.identityMismatch(
                        status: lifecycle!.runId,
                        config: bundle.config.runId
                    )
                }
            }
            try writeJSON(bundle.config,
                          to: directory.appendingPathComponent(configFile))

            // Newly rendered folders are lifecycle-v1. Existing folders without
            // status remain legacy-compatible until an explicit import.
            if !hadConfig {
                lifecycle = try FactoryRunLifecycle.initialize(
                    directory: directory,
                    source: "factory-run-render",
                    command: "factory-run render"
                )
            }

            try writeJSON(bundle.dataset,
                          to: directory.appendingPathComponent(datasetFile))
            if lifecycle?.phase == .created {
                lifecycle = try advance(lifecycle!, directory: directory, to: .dataReady)
            }

            if lifecycle?.phase == .dataReady {
                lifecycle = try advance(
                    lifecycle!,
                    directory: directory,
                    to: .evaluating,
                    reason: "metadata-only-render"
                )
            }
            try writeJSON(bundle.baseline,
                          to: directory.appendingPathComponent(baselineFile))
            try FactoryRun.validate(bundle.baseline)
            try writeJSON(bundle.candidate,
                          to: directory.appendingPathComponent(candidateFile))
            try FactoryRun.validate(bundle.candidate)
            if lifecycle?.phase == .evaluating {
                lifecycle = try advance(lifecycle!, directory: directory, to: .evaluated)
            }

            if let artifact = bundle.artifact {
                if lifecycle?.phase == .evaluated {
                    lifecycle = try advance(lifecycle!,
                                            directory: directory,
                                            to: .packaging)
                }
                try writeJSON(artifact,
                              to: directory.appendingPathComponent(artifactFile))
                try FactoryRun.validate(artifact)
                if lifecycle?.phase == .packaging {
                    lifecycle = try advance(lifecycle!,
                                            directory: directory,
                                            to: .packaged)
                }
            }

            try writeJSON(bundle.decision,
                          to: directory.appendingPathComponent(decisionFile))
            try bundle.markdownReport().write(
                to: directory.appendingPathComponent(reportFile),
                atomically: true,
                encoding: .utf8
            )
            if lifecycle?.phase == .packaged {
                lifecycle = try advance(lifecycle!, directory: directory, to: .reporting)
            } else if lifecycle?.phase == .evaluated {
                lifecycle = try advance(
                    lifecycle!,
                    directory: directory,
                    to: .reporting,
                    reason: "report-only"
                )
            }

            if let trainLog {
                try trainLog.write(to: directory.appendingPathComponent(trainLogFile),
                                   atomically: true,
                                   encoding: .utf8)
            } else {
                let logURL = directory.appendingPathComponent(trainLogFile)
                if !fm.fileExists(atPath: logURL.path) {
                    try "No train log recorded.\n".write(to: logURL,
                                                         atomically: true,
                                                         encoding: .utf8)
                }
            }
            if lifecycle?.phase == .reporting {
                lifecycle = try advance(lifecycle!, directory: directory, to: .decided)
            }
        } catch {
            if let lifecycle, !lifecycle.phase.isTerminal {
                _ = try? FactoryRunLifecycle.transition(
                    directory: directory,
                    to: .failed,
                    expectedRevision: lifecycle.revision,
                    source: "factory-run-render",
                    command: "factory-run render",
                    failure: .init(
                        code: "metadata-write-failed",
                        summary: "Factory run metadata could not be written or validated."
                    )
                )
            }
            throw error
        }
    }

    public static func read(from directory: URL) throws -> FactoryRun.Bundle {
        let config = try readJSON(FactoryRun.Config.self,
                                  from: directory.appendingPathComponent(configFile))
        let dataset = try readJSON(FactoryRun.DatasetManifest.self,
                                   from: directory.appendingPathComponent(datasetFile))
        let baseline = try readJSON(FactoryRun.EvalResult.self,
                                    from: directory.appendingPathComponent(baselineFile))
        let candidate = try readJSON(FactoryRun.EvalResult.self,
                                     from: directory.appendingPathComponent(candidateFile))
        let artifactURL = directory.appendingPathComponent(artifactFile)
        let artifact = FileManager.default.fileExists(atPath: artifactURL.path)
            ? try readJSON(FactoryRun.Artifact.self, from: artifactURL)
            : nil
        let decision = try readJSON(FactoryRun.DecisionRecord.self,
                                    from: directory.appendingPathComponent(decisionFile))
        return FactoryRun.Bundle(config: config,
                                 dataset: dataset,
                                 baseline: baseline,
                                 candidate: candidate,
                                 artifact: artifact,
                                 decision: decision)
    }

    public static func validate(directory: URL) throws -> FactoryRun.Bundle {
        let bundle = try read(from: directory)
        try bundle.validate()
        if FileManager.default.fileExists(
            atPath: directory.appendingPathComponent(lifecycleFile).path
        ) {
            _ = try FactoryRunLifecycle.readStatus(directory: directory)
        }
        return bundle
    }

    public static func readLifecycle(from directory: URL)
        throws -> FactoryRunLifecycle.Status? {
        let url = directory.appendingPathComponent(lifecycleFile)
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        return try FactoryRunLifecycle.readStatus(directory: directory)
    }

    private static func advance(_ status: FactoryRunLifecycle.Status,
                                directory: URL,
                                to phase: FactoryRunLifecycle.Phase,
                                reason: String? = nil) throws
        -> FactoryRunLifecycle.Status {
        try FactoryRunLifecycle.transition(
            directory: directory,
            to: phase,
            expectedRevision: status.revision,
            source: "factory-run-render",
            command: "factory-run render",
            reason: reason
        )
    }

    static func writeJSON<T: Encodable>(_ value: T, to url: URL) throws {
        let data = try FactoryRun.encode(value)
        try data.write(to: url, options: [.atomic])
    }

    static func readJSON<T: Decodable>(_ type: T.Type, from url: URL) throws -> T {
        let data = try Data(contentsOf: url)
        return try FactoryRun.decode(type, from: data)
    }
}
