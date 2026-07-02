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

        Renders and validates the canonical factory run folder documented in
        docs/factory/run-schema.md. This command is metadata-only: it does not
        train, evaluate, load MLX, or touch checkpoints.
        """)
        exit(code)
    }
}
