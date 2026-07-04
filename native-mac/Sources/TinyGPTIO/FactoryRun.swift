import Foundation

/// Typed representation of the factory run artifact documented in
/// `docs/factory/run-schema.md`.
///
/// This is deliberately model-free: it can validate and render run metadata
/// without loading MLX, starting a server, or touching a checkpoint. The CLI,
/// Mac app Factory Run Center, and report scripts can all share it.
public enum FactoryRun {

    public enum Decision: String, Codable, Sendable, CaseIterable {
        case ship
        case reject
        case retryData = "retry-data"
        case retryTraining = "retry-training"
        case retryEval = "retry-eval"
        case park
    }

    public struct BaseModel: Codable, Hashable, Sendable {
        public let id: String
        public let revision: String?
        public let precision: String?

        public init(id: String, revision: String? = nil, precision: String? = nil) {
            self.id = id
            self.revision = revision
            self.precision = precision
        }
    }

    public struct Candidate: Codable, Hashable, Sendable {
        public let method: String
        public let adapterFormat: String?
        public let trainingCommand: String?

        public init(method: String,
                    adapterFormat: String? = nil,
                    trainingCommand: String? = nil) {
            self.method = method
            self.adapterFormat = adapterFormat
            self.trainingCommand = trainingCommand
        }
    }

    public struct Threshold: Codable, Hashable, Sendable {
        public let primaryMin: Double?
        public let breadthDropMaxPp: Double?

        public init(primaryMin: Double? = nil, breadthDropMaxPp: Double? = nil) {
            self.primaryMin = primaryMin
            self.breadthDropMaxPp = breadthDropMaxPp
        }
    }

    public struct EvalSpec: Codable, Hashable, Sendable {
        public let primary: String
        public let regression: String?
        public let threshold: Threshold?

        public init(primary: String,
                    regression: String? = nil,
                    threshold: Threshold? = nil) {
            self.primary = primary
            self.regression = regression
            self.threshold = threshold
        }
    }

    public struct Config: Codable, Hashable, Sendable {
        public let runId: String
        public let target: String
        public let ownerGoal: String
        public let baseModel: BaseModel
        public let candidate: Candidate
        public let eval: EvalSpec

        public init(runId: String,
                    target: String,
                    ownerGoal: String,
                    baseModel: BaseModel,
                    candidate: Candidate,
                    eval: EvalSpec) {
            self.runId = runId
            self.target = target
            self.ownerGoal = ownerGoal
            self.baseModel = baseModel
            self.candidate = candidate
            self.eval = eval
        }
    }

    public struct DatasetSource: Codable, Hashable, Sendable {
        public let kind: String
        public let path: String
        public let rows: Int?

        public init(kind: String, path: String, rows: Int? = nil) {
            self.kind = kind
            self.path = path
            self.rows = rows
        }
    }

    public struct DatasetProcessing: Codable, Hashable, Sendable {
        public let dedupe: Bool
        public let qualityFilter: Bool
        public let heldoutSplit: String?

        public init(dedupe: Bool = false,
                    qualityFilter: Bool = false,
                    heldoutSplit: String? = nil) {
            self.dedupe = dedupe
            self.qualityFilter = qualityFilter
            self.heldoutSplit = heldoutSplit
        }
    }

    public struct DatasetCounts: Codable, Hashable, Sendable {
        public let trainRows: Int
        public let heldoutRows: Int
        public let droppedRows: Int

        public init(trainRows: Int = 0, heldoutRows: Int = 0, droppedRows: Int = 0) {
            self.trainRows = trainRows
            self.heldoutRows = heldoutRows
            self.droppedRows = droppedRows
        }
    }

    public struct DatasetManifest: Codable, Hashable, Sendable {
        public let datasetId: String
        public let sources: [DatasetSource]
        public let processing: DatasetProcessing
        public let counts: DatasetCounts

        public init(datasetId: String,
                    sources: [DatasetSource],
                    processing: DatasetProcessing = DatasetProcessing(),
                    counts: DatasetCounts = DatasetCounts()) {
            self.datasetId = datasetId
            self.sources = sources
            self.processing = processing
            self.counts = counts
        }
    }

    public struct EvalResult: Codable, Hashable, Sendable {
        public let modelId: String
        public let command: String?
        public let suite: String
        public let score: Double
        public let passed: Bool?
        public let date: String?
        public let latencyMs: Double?
        public let peakRssMb: Double?
        public let tokensPerSecond: Double?
        public let notes: String?

        public init(modelId: String,
                    command: String? = nil,
                    suite: String,
                    score: Double,
                    passed: Bool? = nil,
                    date: String? = nil,
                    latencyMs: Double? = nil,
                    peakRssMb: Double? = nil,
                    tokensPerSecond: Double? = nil,
                    notes: String? = nil) {
            self.modelId = modelId
            self.command = command
            self.suite = suite
            self.score = score
            self.passed = passed
            self.date = date
            self.latencyMs = latencyMs
            self.peakRssMb = peakRssMb
            self.tokensPerSecond = tokensPerSecond
            self.notes = notes
        }
    }

    public struct Artifact: Codable, Hashable, Sendable {
        public let artifactId: String
        public let kind: String
        public let path: String
        public let baseModel: String
        public let format: String?
        public let packageDir: String?
        public let shipped: Bool

        public init(artifactId: String,
                    kind: String,
                    path: String,
                    baseModel: String,
                    format: String? = nil,
                    packageDir: String? = nil,
                    shipped: Bool = false) {
            self.artifactId = artifactId
            self.kind = kind
            self.path = path
            self.baseModel = baseModel
            self.format = format
            self.packageDir = packageDir
            self.shipped = shipped
        }
    }

    public struct DecisionRecord: Codable, Hashable, Sendable {
        public let decision: Decision
        public let reason: String
        public let failureReason: String?
        public let failureReasonConfidence: String?
        public let lesson: String?
        public let nextAction: String?
        public let evidenceSources: [String]
        public let blockedBy: [String]

        public init(decision: Decision,
                    reason: String,
                    failureReason: String? = nil,
                    failureReasonConfidence: String? = nil,
                    lesson: String? = nil,
                    nextAction: String? = nil,
                    evidenceSources: [String] = [],
                    blockedBy: [String] = []) {
            self.decision = decision
            self.reason = reason
            self.failureReason = failureReason
            self.failureReasonConfidence = failureReasonConfidence
            self.lesson = lesson
            self.nextAction = nextAction
            self.evidenceSources = evidenceSources
            self.blockedBy = blockedBy
        }
    }

    public struct Bundle: Codable, Hashable, Sendable {
        public let config: Config
        public let dataset: DatasetManifest
        public let baseline: EvalResult
        public let candidate: EvalResult
        public let artifact: Artifact?
        public let decision: DecisionRecord

        public init(config: Config,
                    dataset: DatasetManifest,
                    baseline: EvalResult,
                    candidate: EvalResult,
                    artifact: Artifact? = nil,
                    decision: DecisionRecord) {
            self.config = config
            self.dataset = dataset
            self.baseline = baseline
            self.candidate = candidate
            self.artifact = artifact
            self.decision = decision
        }

        public var scoreDelta: Double {
            candidate.score - baseline.score
        }

        public func validate() throws {
            try FactoryRun.validate(config)
            try FactoryRun.validate(dataset)
            try FactoryRun.validate(baseline)
            try FactoryRun.validate(candidate)
            try FactoryRun.validate(decision)
            if let artifact {
                try FactoryRun.validate(artifact)
            }
            if decision.decision == .ship {
                guard let artifact else {
                    throw ValidationError.shipDecisionMissingArtifact
                }
                if !artifact.shipped {
                    throw ValidationError.shipDecisionWithUnshippedArtifact(id: artifact.artifactId)
                }
            }
        }

        public func markdownReport() -> String {
            var lines: [String] = []
            lines.append("# \(config.target) — \(config.candidate.method)")
            lines.append("")
            lines.append("## Decision")
            lines.append("")
            lines.append("Decision: \(decision.decision.rawValue)")
            lines.append("")
            lines.append("Reason: \(decision.reason)")
            lines.append("")
            lines.append("## Evidence / Exactness")
            lines.append("")
            lines.append("- Failure reason: \(decision.failureReason ?? "n/a")")
            lines.append("- Failure reason confidence: \(decision.failureReasonConfidence ?? "n/a")")
            lines.append("- Lesson: \(decision.lesson ?? "n/a")")
            lines.append("- Evidence sources:")
            if decision.evidenceSources.isEmpty {
                lines.append("  - n/a")
            } else {
                for source in decision.evidenceSources {
                    lines.append("  - `\(source)`")
                }
            }
            lines.append("")
            lines.append("## Target")
            lines.append("")
            lines.append("- Target: \(config.target)")
            lines.append("- Base model: \(config.baseModel.id)")
            lines.append("- Candidate: \(candidate.modelId)")
            lines.append("- Training method: \(config.candidate.method)")
            if let artifact {
                lines.append("- Artifact: \(artifact.path)")
            }
            lines.append("")
            lines.append("## Data")
            lines.append("")
            lines.append("- Dataset: \(dataset.datasetId)")
            lines.append("- Train rows: \(dataset.counts.trainRows)")
            lines.append("- Heldout rows: \(dataset.counts.heldoutRows)")
            lines.append("- Dropped rows: \(dataset.counts.droppedRows)")
            lines.append("")
            lines.append("## Eval")
            lines.append("")
            lines.append("| Metric | Baseline | Candidate | Delta | Pass |")
            lines.append("|---|---:|---:|---:|---|")
            lines.append("| \(candidate.suite) | \(fmt(baseline.score)) | \(fmt(candidate.score)) | \(fmt(scoreDelta)) | \(candidate.passed.map { $0 ? "yes" : "no" } ?? "n/a") |")
            lines.append("")
            lines.append("## Performance")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|---|---:|")
            lines.append("| Latency ms | \(optional(candidate.latencyMs)) |")
            lines.append("| tok/s | \(optional(candidate.tokensPerSecond)) |")
            lines.append("| RAM / peak RSS MB | \(optional(candidate.peakRssMb)) |")
            lines.append("")
            lines.append("## Failures")
            lines.append("")
            lines.append("- What failed: \(decision.failureReason ?? "n/a")")
            lines.append("- Lesson: \(decision.lesson ?? "n/a")")
            lines.append("")
            lines.append("## Next Action")
            lines.append("")
            lines.append(decision.nextAction ?? "None recorded.")
            lines.append("")
            return lines.joined(separator: "\n")
        }
    }

    public enum ValidationError: Error, CustomStringConvertible, Equatable {
        case emptyField(String)
        case emptySources
        case nonFiniteScore(String)
        case shipDecisionMissingArtifact
        case shipDecisionWithUnshippedArtifact(id: String)

        public var description: String {
            switch self {
            case .emptyField(let field): return "\(field) must not be empty"
            case .emptySources: return "dataset sources must not be empty"
            case .nonFiniteScore(let field): return "\(field) score must be finite"
            case .shipDecisionMissingArtifact: return "ship decision requires an artifact"
            case .shipDecisionWithUnshippedArtifact(let id):
                return "ship decision requires artifact '\(id)' to have shipped=true"
            }
        }
    }

    public static let jsonEncoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }()

    public static let jsonDecoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    public static func encode<T: Encodable>(_ value: T) throws -> Data {
        try jsonEncoder.encode(value)
    }

    public static func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        try jsonDecoder.decode(type, from: data)
    }

    public static func validate(_ config: Config) throws {
        try nonEmpty(config.runId, "config.run_id")
        try nonEmpty(config.target, "config.target")
        try nonEmpty(config.ownerGoal, "config.owner_goal")
        try nonEmpty(config.baseModel.id, "config.base_model.id")
        try nonEmpty(config.candidate.method, "config.candidate.method")
        try nonEmpty(config.eval.primary, "config.eval.primary")
    }

    public static func validate(_ dataset: DatasetManifest) throws {
        try nonEmpty(dataset.datasetId, "dataset.dataset_id")
        guard !dataset.sources.isEmpty else { throw ValidationError.emptySources }
        for (idx, source) in dataset.sources.enumerated() {
            try nonEmpty(source.kind, "dataset.sources[\(idx)].kind")
            try nonEmpty(source.path, "dataset.sources[\(idx)].path")
        }
    }

    public static func validate(_ result: EvalResult) throws {
        try nonEmpty(result.modelId, "eval.model_id")
        try nonEmpty(result.suite, "eval.suite")
        guard result.score.isFinite else {
            throw ValidationError.nonFiniteScore(result.modelId)
        }
    }

    public static func validate(_ artifact: Artifact) throws {
        try nonEmpty(artifact.artifactId, "artifact.artifact_id")
        try nonEmpty(artifact.kind, "artifact.kind")
        try nonEmpty(artifact.path, "artifact.path")
        try nonEmpty(artifact.baseModel, "artifact.base_model")
    }

    public static func validate(_ decision: DecisionRecord) throws {
        try nonEmpty(decision.reason, "decision.reason")
    }

    private static func nonEmpty(_ value: String, _ field: String) throws {
        if value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw ValidationError.emptyField(field)
        }
    }

    private static func fmt(_ value: Double) -> String {
        String(format: "%.4f", value)
    }

    private static func optional(_ value: Double?) -> String {
        guard let value else { return "n/a" }
        return fmt(value)
    }
}
