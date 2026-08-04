import Foundation

/// Model-free persistence at live train/eval command boundaries.
///
/// Commands opt in with an existing lifecycle-managed run directory. This
/// helper validates frozen context, writes only evidence the caller measured,
/// and advances lifecycle state after durable validation succeeds.
public enum FactoryRunEvidence {
    public static let costFile = "cost.json"
    public static let sliceMetricsFile = "slice-metrics.json"

    public enum EvidenceError: Error, CustomStringConvertible, Equatable {
        case invalidPhase(expected: FactoryRunLifecycle.Phase,
                          actual: FactoryRunLifecycle.Phase)
        case invalidDuration(String)
        case invalidTrainingLog
        case invalidSlice(String)

        public var description: String {
            switch self {
            case .invalidPhase(let expected, let actual):
                return "factory run must be \(expected.rawValue), found \(actual.rawValue)"
            case .invalidDuration(let field):
                return "\(field) must be finite and non-negative"
            case .invalidTrainingLog:
                return "training summary must be one bounded non-empty line"
            case .invalidSlice(let reason):
                return "invalid slice evidence: \(reason)"
            }
        }
    }

    public struct Context: Sendable {
        public let config: FactoryRun.Config
        public let dataset: FactoryRun.DatasetManifest
        public let status: FactoryRunLifecycle.Status
    }

    public struct Cost: Codable, Hashable, Sendable {
        public let trainingTimeSeconds: Double?
        public let trainingCostUsd: Double?
        public let trainingCostUsdNote: String?
        public let evalTimeSeconds: Double?

        public init(trainingTimeSeconds: Double? = nil,
                    trainingCostUsd: Double? = nil,
                    trainingCostUsdNote: String? = nil,
                    evalTimeSeconds: Double? = nil) {
            self.trainingTimeSeconds = trainingTimeSeconds
            self.trainingCostUsd = trainingCostUsd
            self.trainingCostUsdNote = trainingCostUsdNote
            self.evalTimeSeconds = evalTimeSeconds
        }
    }

    public struct SliceInput: Hashable, Sendable {
        public let name: String
        public let metric: String
        public let score: Double
        public let rows: Int
        public let baseline: Bool
        public let higherIsBetter: Bool

        public init(name: String,
                    metric: String,
                    score: Double,
                    rows: Int,
                    baseline: Bool,
                    higherIsBetter: Bool) {
            self.name = name
            self.metric = metric
            self.score = score
            self.rows = rows
            self.baseline = baseline
            self.higherIsBetter = higherIsBetter
        }
    }

    public struct Slice: Codable, Hashable, Sendable {
        public let rows: Int
        public let metric: String
        public let baseline: Double?
        public let candidate: Double?
        public let delta: Double?
        public let pass: Bool?
    }

    public struct SliceOverall: Codable, Hashable, Sendable {
        public let rows: Int
        public let note: String
    }

    public struct SliceMetrics: Codable, Hashable, Sendable {
        public let overall: SliceOverall
        public let slices: [String: Slice]
    }

    public static func inspect(directory: URL,
                               expectedPhase: FactoryRunLifecycle.Phase) throws -> Context {
        let config = try FactoryRunFolder.readJSON(
            FactoryRun.Config.self,
            from: directory.appendingPathComponent(FactoryRunFolder.configFile)
        )
        try FactoryRun.validate(config)
        let dataset = try FactoryRunFolder.readJSON(
            FactoryRun.DatasetManifest.self,
            from: directory.appendingPathComponent(FactoryRunFolder.datasetFile)
        )
        try FactoryRun.validate(dataset)
        let status = try FactoryRunLifecycle.readStatus(directory: directory)
        guard status.phase == expectedPhase else {
            throw EvidenceError.invalidPhase(expected: expectedPhase, actual: status.phase)
        }
        return Context(config: config, dataset: dataset, status: status)
    }

    @discardableResult
    public static func beginTraining(directory: URL,
                                     command: String = "posttrainllm sft") throws
        -> FactoryRunLifecycle.Status {
        let context = try inspect(directory: directory, expectedPhase: .dataReady)
        return try FactoryRunLifecycle.transition(
            directory: directory,
            to: .training,
            expectedRevision: context.status.revision,
            source: "live-command",
            command: boundedCommand(command)
        )
    }

    @discardableResult
    public static func finishTraining(directory: URL,
                                      artifact: FactoryRun.Artifact,
                                      summary: String,
                                      trainingTimeSeconds: Double,
                                      command: String = "posttrainllm sft") throws
        -> FactoryRunLifecycle.Status {
        try FactoryRun.validate(artifact)
        try validateDuration(trainingTimeSeconds, field: "training_time_seconds")
        let cleanSummary = summary.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanSummary.isEmpty, cleanSummary.count <= 512,
              !cleanSummary.contains("\n"), !cleanSummary.contains("\r") else {
            throw EvidenceError.invalidTrainingLog
        }

        let context = try inspect(directory: directory, expectedPhase: .training)
        let existingCost = try readCostIfPresent(directory: directory)
        let cost = Cost(
            trainingTimeSeconds: trainingTimeSeconds,
            trainingCostUsd: 0,
            trainingCostUsdNote: "Local Mac run; no paid model API was used.",
            evalTimeSeconds: existingCost?.evalTimeSeconds
        )
        try validate(cost)

        try FactoryRunFolder.writeJSON(
            artifact,
            to: directory.appendingPathComponent(FactoryRunFolder.artifactFile)
        )
        try (cleanSummary + "\n").write(
            to: directory.appendingPathComponent(FactoryRunFolder.trainLogFile),
            atomically: true,
            encoding: .utf8
        )
        try FactoryRunFolder.writeJSON(
            cost,
            to: directory.appendingPathComponent(costFile)
        )

        // Decode the durable copies before crossing the lifecycle boundary.
        let writtenArtifact = try FactoryRunFolder.readJSON(
            FactoryRun.Artifact.self,
            from: directory.appendingPathComponent(FactoryRunFolder.artifactFile)
        )
        try FactoryRun.validate(writtenArtifact)
        _ = try readCostIfPresent(directory: directory)

        return try FactoryRunLifecycle.transition(
            directory: directory,
            to: .trained,
            expectedRevision: context.status.revision,
            source: "live-command",
            command: boundedCommand(command)
        )
    }

    @discardableResult
    public static func beginEvaluation(directory: URL,
                                       command: String = "posttrainllm eval-gate") throws
        -> FactoryRunLifecycle.Status {
        let context = try inspect(directory: directory, expectedPhase: .trained)
        return try FactoryRunLifecycle.transition(
            directory: directory,
            to: .evaluating,
            expectedRevision: context.status.revision,
            source: "live-command",
            command: boundedCommand(command)
        )
    }

    @discardableResult
    public static func finishEvaluation(directory: URL,
                                        baseline: FactoryRun.EvalResult,
                                        candidate: FactoryRun.EvalResult,
                                        evalTimeSeconds: Double,
                                        command: String = "posttrainllm eval-gate") throws
        -> FactoryRunLifecycle.Status {
        try FactoryRun.validate(baseline)
        try FactoryRun.validate(candidate)
        guard baseline.suite == candidate.suite else {
            throw EvidenceError.invalidSlice("baseline and candidate suites differ")
        }
        try validateDuration(evalTimeSeconds, field: "eval_time_seconds")
        let context = try inspect(directory: directory, expectedPhase: .evaluating)
        let existingCost = try readCostIfPresent(directory: directory)
        let cost = Cost(
            trainingTimeSeconds: existingCost?.trainingTimeSeconds,
            trainingCostUsd: existingCost?.trainingCostUsd,
            trainingCostUsdNote: existingCost?.trainingCostUsdNote,
            evalTimeSeconds: evalTimeSeconds
        )
        try validate(cost)

        try FactoryRunFolder.writeJSON(
            baseline,
            to: directory.appendingPathComponent(FactoryRunFolder.baselineFile)
        )
        try FactoryRunFolder.writeJSON(
            candidate,
            to: directory.appendingPathComponent(FactoryRunFolder.candidateFile)
        )
        try FactoryRunFolder.writeJSON(
            cost,
            to: directory.appendingPathComponent(costFile)
        )

        let writtenBaseline = try FactoryRunFolder.readJSON(
            FactoryRun.EvalResult.self,
            from: directory.appendingPathComponent(FactoryRunFolder.baselineFile)
        )
        let writtenCandidate = try FactoryRunFolder.readJSON(
            FactoryRun.EvalResult.self,
            from: directory.appendingPathComponent(FactoryRunFolder.candidateFile)
        )
        try FactoryRun.validate(writtenBaseline)
        try FactoryRun.validate(writtenCandidate)
        _ = try readCostIfPresent(directory: directory)

        return try FactoryRunLifecycle.transition(
            directory: directory,
            to: .evaluated,
            expectedRevision: context.status.revision,
            source: "live-command",
            command: boundedCommand(command)
        )
    }

    public static func makeSliceMetrics(_ inputs: [SliceInput]) throws -> SliceMetrics {
        guard !inputs.isEmpty else { throw EvidenceError.invalidSlice("no rows") }
        for input in inputs {
            guard !input.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  !input.metric.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  input.score.isFinite,
                  input.rows > 0 else {
                throw EvidenceError.invalidSlice("row fields must be non-empty and finite")
            }
        }

        var slices: [String: Slice] = [:]
        var overallRows = 0
        for (name, group) in Dictionary(grouping: inputs, by: \.name) {
            let metrics = Set(group.map(\.metric))
            let directions = Set(group.map(\.higherIsBetter))
            guard metrics.count == 1, directions.count == 1 else {
                throw EvidenceError.invalidSlice("\(name) mixes metrics or score direction")
            }
            let baselineRows = group.filter(\.baseline)
            let candidateRows = group.filter { !$0.baseline }
            let baseline = weightedMean(baselineRows)
            let candidate = weightedMean(candidateRows)
            let baselineCount = baselineRows.map(\.rows).max()
            let candidateCount = candidateRows.map(\.rows).max()
            if let baselineCount, let candidateCount, baselineCount != candidateCount {
                throw EvidenceError.invalidSlice("\(name) uses different instance counts")
            }
            let rows = candidateCount ?? baselineCount ?? 0
            overallRows += rows
            let delta = baseline.flatMap { b in candidate.map { $0 - b } }
            let pass = baseline.flatMap { b in
                candidate.map { c in (directions.first ?? true) ? c >= b : c <= b }
            }
            slices[name] = Slice(
                rows: rows,
                metric: metrics.first!,
                baseline: baseline,
                candidate: candidate,
                delta: delta,
                pass: pass
            )
        }
        return SliceMetrics(
            overall: SliceOverall(
                rows: overallRows,
                note: "Derived deterministically from E0 eval rows by eval-compare."
            ),
            slices: slices
        )
    }

    public static func writeSliceMetrics(_ metrics: SliceMetrics,
                                         directory: URL) throws {
        let config = try FactoryRunFolder.readJSON(
            FactoryRun.Config.self,
            from: directory.appendingPathComponent(FactoryRunFolder.configFile)
        )
        try FactoryRun.validate(config)
        let dataset = try FactoryRunFolder.readJSON(
            FactoryRun.DatasetManifest.self,
            from: directory.appendingPathComponent(FactoryRunFolder.datasetFile)
        )
        try FactoryRun.validate(dataset)
        let status = try FactoryRunLifecycle.readStatus(directory: directory)
        guard [.trained, .evaluating, .evaluated].contains(status.phase) else {
            throw EvidenceError.invalidPhase(expected: .trained, actual: status.phase)
        }
        guard !metrics.slices.isEmpty else {
            throw EvidenceError.invalidSlice("no slices")
        }
        try FactoryRunFolder.writeJSON(
            metrics,
            to: directory.appendingPathComponent(sliceMetricsFile)
        )
        let written = try FactoryRunFolder.readJSON(
            SliceMetrics.self,
            from: directory.appendingPathComponent(sliceMetricsFile)
        )
        guard written == metrics else {
            throw EvidenceError.invalidSlice("durable round-trip mismatch")
        }
    }

    private static func weightedMean(_ rows: [SliceInput]) -> Double? {
        guard !rows.isEmpty else { return nil }
        let weight = rows.reduce(0) { $0 + $1.rows }
        guard weight > 0 else { return nil }
        return rows.reduce(0) { $0 + ($1.score * Double($1.rows)) } / Double(weight)
    }

    private static func readCostIfPresent(directory: URL) throws -> Cost? {
        let url = directory.appendingPathComponent(costFile)
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let cost = try FactoryRunFolder.readJSON(Cost.self, from: url)
        try validate(cost)
        return cost
    }

    private static func validate(_ cost: Cost) throws {
        if let value = cost.trainingTimeSeconds {
            try validateDuration(value, field: "training_time_seconds")
        }
        if let value = cost.evalTimeSeconds {
            try validateDuration(value, field: "eval_time_seconds")
        }
        if let value = cost.trainingCostUsd {
            try validateDuration(value, field: "training_cost_usd")
        }
    }

    private static func validateDuration(_ value: Double, field: String) throws {
        guard value.isFinite, value >= 0 else {
            throw EvidenceError.invalidDuration(field)
        }
    }

    private static func boundedCommand(_ command: String) -> String {
        let clean = command.trimmingCharacters(in: .whitespacesAndNewlines)
        return String(clean.prefix(160))
    }
}
