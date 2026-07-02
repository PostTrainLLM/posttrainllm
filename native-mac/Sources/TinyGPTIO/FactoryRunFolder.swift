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

    public static func write(_ bundle: FactoryRun.Bundle,
                             to directory: URL,
                             trainLog: String? = nil) throws {
        try bundle.validate()
        try FileManager.default.createDirectory(at: directory,
                                                withIntermediateDirectories: true)
        try writeJSON(bundle.config, to: directory.appendingPathComponent(configFile))
        try writeJSON(bundle.dataset, to: directory.appendingPathComponent(datasetFile))
        try writeJSON(bundle.baseline, to: directory.appendingPathComponent(baselineFile))
        try writeJSON(bundle.candidate, to: directory.appendingPathComponent(candidateFile))
        if let artifact = bundle.artifact {
            try writeJSON(artifact, to: directory.appendingPathComponent(artifactFile))
        }
        try writeJSON(bundle.decision, to: directory.appendingPathComponent(decisionFile))
        try bundle.markdownReport().write(to: directory.appendingPathComponent(reportFile),
                                          atomically: true,
                                          encoding: .utf8)
        if let trainLog {
            try trainLog.write(to: directory.appendingPathComponent(trainLogFile),
                               atomically: true,
                               encoding: .utf8)
        } else {
            let logURL = directory.appendingPathComponent(trainLogFile)
            if !FileManager.default.fileExists(atPath: logURL.path) {
                try "No train log recorded.\n".write(to: logURL,
                                                     atomically: true,
                                                     encoding: .utf8)
            }
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
        return bundle
    }

    private static func writeJSON<T: Encodable>(_ value: T, to url: URL) throws {
        let data = try FactoryRun.encode(value)
        try data.write(to: url, options: [.atomic])
    }

    private static func readJSON<T: Decodable>(_ type: T.Type, from url: URL) throws -> T {
        let data = try Data(contentsOf: url)
        return try FactoryRun.decode(type, from: data)
    }
}
