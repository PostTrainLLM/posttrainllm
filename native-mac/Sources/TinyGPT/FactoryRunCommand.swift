import Foundation
import TinyGPTIO

enum FactoryRunCommand {
    static func run(args: [String]) {
        guard let subcommand = args.first else { exitUsage() }
        switch subcommand {
        case "render":
            render(args: Array(args.dropFirst()))
        case "validate":
            validate(args: Array(args.dropFirst()))
        case "publish-check":
            publishCheck(args: Array(args.dropFirst()))
        case "-h", "--help":
            exitUsage(0)
        default:
            fputs("factory-run: unknown subcommand \(subcommand)\n", stderr)
            exitUsage()
        }
    }

    private static func render(args: [String]) {
        var configPath: String?
        var datasetPath: String?
        var baselinePath: String?
        var candidatePath: String?
        var decisionPath: String?
        var artifactPath: String?
        var trainLogPath: String?
        var outPath: String?

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--config": configPath = value(args, i); i += 2
            case "--dataset": datasetPath = value(args, i); i += 2
            case "--baseline": baselinePath = value(args, i); i += 2
            case "--candidate": candidatePath = value(args, i); i += 2
            case "--decision": decisionPath = value(args, i); i += 2
            case "--artifact": artifactPath = value(args, i); i += 2
            case "--train-log": trainLogPath = value(args, i); i += 2
            case "--out": outPath = value(args, i); i += 2
            case "-h", "--help": exitUsage(0)
            default:
                fputs("factory-run render: unknown flag \(args[i])\n", stderr)
                exitUsage()
            }
        }

        guard let configPath, let datasetPath, let baselinePath, let candidatePath,
              let decisionPath, let outPath else {
            fputs("factory-run render: --config, --dataset, --baseline, --candidate, --decision, and --out are required\n", stderr)
            exitUsage()
        }

        do {
            let artifact: FactoryRun.Artifact?
            if let artifactPath {
                artifact = try read(FactoryRun.Artifact.self, artifactPath)
            } else {
                artifact = nil
            }
            let trainLog = try trainLogPath.map { try String(contentsOfFile: $0, encoding: .utf8) }
            let bundle = FactoryRun.Bundle(
                config: try read(FactoryRun.Config.self, configPath),
                dataset: try read(FactoryRun.DatasetManifest.self, datasetPath),
                baseline: try read(FactoryRun.EvalResult.self, baselinePath),
                candidate: try read(FactoryRun.EvalResult.self, candidatePath),
                artifact: artifact,
                decision: try read(FactoryRun.DecisionRecord.self, decisionPath)
            )
            let outURL = URL(fileURLWithPath: outPath)
            try FactoryRunFolder.write(bundle, to: outURL, trainLog: trainLog)
            print("factory-run: wrote \(outURL.path)")
        } catch {
            fputs("factory-run render failed: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func validate(args: [String]) {
        guard args.count == 1 else { exitUsage() }
        do {
            let dir = URL(fileURLWithPath: args[0])
            let bundle = try FactoryRunFolder.validate(directory: dir)
            print("factory-run: OK \(dir.path) decision=\(bundle.decision.decision.rawValue)")
        } catch {
            fputs("factory-run validate failed: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func publishCheck(args: [String]) {
        var allowReportOnly = false
        var path: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--allow-report-only":
                allowReportOnly = true
                i += 1
            case "-h", "--help":
                exitUsage(0)
            default:
                if path == nil {
                    path = args[i]
                    i += 1
                } else {
                    fputs("factory-run publish-check: unexpected argument \(args[i])\n", stderr)
                    exitUsage()
                }
            }
        }
        guard let path else { exitUsage() }

        do {
            let dir = URL(fileURLWithPath: path)
            let bundle = try FactoryRunFolder.validate(directory: dir)
            try checkPublishEvidence(bundle: bundle, directory: dir, allowReportOnly: allowReportOnly)
            print("factory-run: publish-check OK \(dir.path) decision=\(bundle.decision.decision.rawValue)")
        } catch {
            fputs("factory-run publish-check failed: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func checkPublishEvidence(bundle: FactoryRun.Bundle,
                                             directory: URL,
                                             allowReportOnly: Bool) throws {
        let fm = FileManager.default
        let required = [
            FactoryRunFolder.configFile,
            FactoryRunFolder.datasetFile,
            FactoryRunFolder.baselineFile,
            FactoryRunFolder.candidateFile,
            FactoryRunFolder.decisionFile,
            FactoryRunFolder.reportFile,
            FactoryRunFolder.trainLogFile,
            "slice-metrics.json",
            "trace_review.md",
            "provenance.json",
        ]
        for name in required {
            let url = directory.appendingPathComponent(name)
            if !fm.fileExists(atPath: url.path) {
                throw PublishCheckError.missingFile(name)
            }
        }
        if !allowReportOnly && bundle.artifact == nil {
            throw PublishCheckError.missingFile(FactoryRunFolder.artifactFile)
        }
        if bundle.dataset.counts.heldoutRows <= 0 {
            throw PublishCheckError.invalidField("dataset.counts.heldout_rows must be > 0")
        }
        if bundle.baseline.command?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
            throw PublishCheckError.invalidField("eval-baseline.command is required")
        }
        if bundle.candidate.command?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
            throw PublishCheckError.invalidField("eval-candidate.command is required")
        }
        if bundle.decision.nextAction?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
            throw PublishCheckError.invalidField("decision.next_action is required")
        }
        let allowedConfidence = ["exact", "inferred", "missing-evidence", "not-applicable"]
        let confidence = bundle.decision.failureReasonConfidence?.trimmingCharacters(in: .whitespacesAndNewlines)
        if confidence == nil || !allowedConfidence.contains(confidence!) {
            throw PublishCheckError.invalidField("decision.failure_reason_confidence must be exact, inferred, missing-evidence, or not-applicable")
        }
        if bundle.decision.decision == .ship {
            if confidence != "not-applicable" {
                throw PublishCheckError.invalidField("ship decision must use decision.failure_reason_confidence=not-applicable")
            }
        } else {
            if bundle.decision.failureReason?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
                throw PublishCheckError.invalidField("non-ship decision.failure_reason is required")
            }
            if bundle.decision.lesson?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
                throw PublishCheckError.invalidField("non-ship decision.lesson is required")
            }
            if confidence == "not-applicable" {
                throw PublishCheckError.invalidField("non-ship decision requires real failure_reason_confidence")
            }
        }
        if bundle.decision.evidenceSources.isEmpty {
            throw PublishCheckError.invalidField("decision.evidence_sources must be a non-empty list")
        }

        let sliceURL = directory.appendingPathComponent("slice-metrics.json")
        let sliceData = try Data(contentsOf: sliceURL)
        let sliceJSON = try JSONSerialization.jsonObject(with: sliceData)
        guard let sliceDict = sliceJSON as? [String: Any],
              sliceDict["overall"] != nil,
              sliceDict["slices"] != nil else {
            throw PublishCheckError.invalidField("slice-metrics.json must contain overall and slices")
        }

        let provenanceURL = directory.appendingPathComponent("provenance.json")
        let provenanceData = try Data(contentsOf: provenanceURL)
        let provenanceJSON = try JSONSerialization.jsonObject(with: provenanceData)
        guard let provenance = provenanceJSON as? [String: Any],
              provenance["schema_version"] != nil,
              let renderer = provenance["renderer"] as? String,
              !renderer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let git = provenance["git"] as? [String: Any],
              let commit = git["commit"] as? String,
              !commit.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              let commands = provenance["commands"] as? [String: Any],
              commands["baseline"] as? String == bundle.baseline.command,
              commands["candidate"] as? String == bundle.candidate.command,
              let datasets = provenance["datasets"] as? [[String: Any]],
              !datasets.isEmpty else {
            throw PublishCheckError.invalidField("provenance.json must contain schema, renderer, git commit, matching commands, and dataset hashes")
        }
        for (idx, dataset) in datasets.enumerated() {
            let path = dataset["path"] as? String
            let sha = dataset["sha256"] as? String
            if path?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
                throw PublishCheckError.invalidField("provenance.datasets[\(idx)].path is required")
            }
            if sha?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
                throw PublishCheckError.invalidField("provenance.datasets[\(idx)].sha256 is required")
            }
        }

        let trace = try String(contentsOf: directory.appendingPathComponent("trace_review.md"), encoding: .utf8)
        if !trace.localizedCaseInsensitiveContains("trace review") {
            throw PublishCheckError.invalidField("trace_review.md must be a trace review")
        }

        let report = try String(contentsOf: directory.appendingPathComponent(FactoryRunFolder.reportFile), encoding: .utf8)
        for section in ["## Decision", "## Evidence / Exactness", "## Target", "## Data", "## Eval", "## Performance", "## Failures", "## Next Action"] {
            if !report.contains(section) {
                throw PublishCheckError.invalidField("report.md missing section \(section)")
            }
        }

        if bundle.decision.decision == .ship {
            guard let artifact = bundle.artifact else {
                throw FactoryRun.ValidationError.shipDecisionMissingArtifact
            }
            if artifact.packageDir?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true {
                throw PublishCheckError.invalidField("ship decision requires artifact.package_dir")
            }
            if !bundle.decision.blockedBy.isEmpty {
                throw PublishCheckError.invalidField("ship decision must not have blockers")
            }
        }
    }

    private static func read<T: Decodable>(_ type: T.Type, _ path: String) throws -> T {
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        return try FactoryRun.decode(type, from: data)
    }

    private static func value(_ args: [String], _ index: Int) -> String {
        guard index + 1 < args.count else { exitUsage() }
        return args[index + 1]
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage:
          tinygpt factory-run render --config config.json --dataset dataset.json \\
            --baseline eval-baseline.json --candidate eval-candidate.json \\
            --decision decision.json [--artifact artifact.json] \\
            [--train-log train.log] --out runs/<id>

          tinygpt factory-run validate runs/<id>

          tinygpt factory-run publish-check [--allow-report-only] runs/<id>

        Renders and validates the canonical factory run folder documented in
        docs/factory/run-schema.md. This command is metadata-only: it does not
        train, evaluate, load MLX, or touch checkpoints.
        """)
        exit(code)
    }

    enum PublishCheckError: Error, CustomStringConvertible {
        case missingFile(String)
        case invalidField(String)

        var description: String {
            switch self {
            case .missingFile(let name): return "missing required file: \(name)"
            case .invalidField(let message): return message
            }
        }
    }
}
