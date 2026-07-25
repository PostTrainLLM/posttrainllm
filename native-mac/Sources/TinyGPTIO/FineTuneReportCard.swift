import Foundation

/// Typed representation of the Fine-Tune Report Card documented in
/// `docs/factory/report-card.md`.
///
/// The report card is a *derived* artifact: `FactoryRun` fragments and
/// specialist packages stay canonical, and the compiler
/// (`scripts/build_fine_tune_report_card.py`) joins them into one versioned
/// payload where every value carries an explicit measurement state.
///
/// This type lives in the pure IO target for the same reason `FactoryRun` does:
/// the CLI, the Mac app, and report tooling can validate a published card
/// without loading MLX, a checkpoint, or a model server. It is the canonical
/// schema boundary — `evals/fine-tune-report-card-smoke.sh` decodes the
/// compiler's real output through this type so the Python and Swift contracts
/// cannot silently diverge.
public enum FineTuneReportCard {

    public static let schemaVersion = 1

    // MARK: - Measurement states

    /// Why a bare `null` is not enough: a missing latency number, a check that
    /// was deliberately skipped, a legacy import, and an inapplicable gate are
    /// four different claims, and a public report must not blur them.
    public enum MeasurementState: String, Codable, Sendable, CaseIterable {
        /// Read directly from a source artifact for this candidate.
        case measured
        /// Computed from other recorded values (for example a delta).
        case derived
        /// Imported from a legacy record without current canonical provenance.
        case historical
        /// Deliberately not run for this candidate.
        case skipped
        /// Evidence should exist but does not. No value is implied.
        case missing
        /// The check does not apply to this candidate.
        case notApplicable = "not-applicable"

        /// States that must carry a value and at least one source.
        public static let valued: Set<MeasurementState> = [.measured, .derived, .historical]

        /// States that must carry a null value and an explanatory note.
        public static let unvalued: Set<MeasurementState> = [.skipped, .missing, .notApplicable]

        /// Provenance weaker than a current measurement. A ship decision that
        /// leans on one of these cannot be labeled fully verified.
        public static let weak: Set<MeasurementState> = [.historical, .skipped, .missing]

        public var isWeak: Bool { MeasurementState.weak.contains(self) }
    }

    /// A JSON value that may be a number, string, or boolean.
    ///
    /// Report-card values are heterogeneous — a score is a `Double`, a leakage
    /// verdict is a `String`, a gate result is a `Bool` — so the wrapper keeps
    /// one field shape across all of them instead of one type per metric.
    public enum Value: Codable, Hashable, Sendable {
        case number(Double)
        case string(String)
        case bool(Bool)

        public init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            // Bool first: `try Double(from:)` would happily decode `true`.
            if let value = try? container.decode(Bool.self) {
                self = .bool(value)
            } else if let value = try? container.decode(Double.self) {
                self = .number(value)
            } else if let value = try? container.decode(String.self) {
                self = .string(value)
            } else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "report-card value must be a number, string, or boolean"
                )
            }
        }

        public func encode(to encoder: Encoder) throws {
            var container = encoder.singleValueContainer()
            switch self {
            case .number(let value): try container.encode(value)
            case .string(let value): try container.encode(value)
            case .bool(let value): try container.encode(value)
            }
        }

        public var double: Double? {
            if case .number(let value) = self { return value }
            return nil
        }

        public var text: String? {
            if case .string(let value) = self { return value }
            return nil
        }

        public var boolean: Bool? {
            if case .bool(let value) = self { return value }
            return nil
        }
    }

    /// One observation plus its provenance and measurement state.
    public struct Field: Codable, Hashable, Sendable {
        public let state: MeasurementState
        public let value: Value?
        public let unit: String?
        public let sources: [String]
        public let derivedFrom: [String]?
        public let note: String?

        public init(state: MeasurementState,
                    value: Value? = nil,
                    unit: String? = nil,
                    sources: [String] = [],
                    derivedFrom: [String]? = nil,
                    note: String? = nil) {
            self.state = state
            self.value = value
            self.unit = unit
            self.sources = sources
            self.derivedFrom = derivedFrom
            self.note = note
        }

        /// True when this field carries a usable value.
        public var hasValue: Bool {
            MeasurementState.valued.contains(state) && value != nil
        }

        public var isWeak: Bool { state.isWeak }

        public func validate(_ path: String) throws {
            if MeasurementState.valued.contains(state) {
                guard value != nil else {
                    throw ValidationError.missingValue(path: path, state: state.rawValue)
                }
                guard !sources.isEmpty else {
                    throw ValidationError.missingSource(path: path, state: state.rawValue)
                }
                if state == .historical, isBlank(note) {
                    throw ValidationError.missingNote(path: path, state: state.rawValue)
                }
                if state == .derived, (derivedFrom ?? []).isEmpty {
                    throw ValidationError.missingDerivedFrom(path: path)
                }
            } else {
                guard value == nil else {
                    throw ValidationError.unexpectedValue(path: path, state: state.rawValue)
                }
                if isBlank(note) {
                    throw ValidationError.missingNote(path: path, state: state.rawValue)
                }
            }
        }
    }

    // MARK: - Decision vocabulary

    /// Public outcome labels. Only a `ship` decision may produce a ship-shaped
    /// label, so a report-only or rejected candidate can never read as shipped.
    public enum OutcomeLabel: String, Codable, Sendable, CaseIterable {
        case shippedSpecialist = "shipped-specialist"
        case routedShip = "routed-ship"
        case reportOnly = "report-only"
        case rejected = "rejected"

        public static let shipLabels: Set<OutcomeLabel> = [.shippedSpecialist, .routedShip]

        public var claimsShip: Bool { OutcomeLabel.shipLabels.contains(self) }
    }

    public enum GateRole: String, Codable, Sendable, CaseIterable {
        case primary
        case regression
        case breadth
    }

    // MARK: - Payload

    public struct CompiledFrom: Codable, Hashable, Sendable {
        public enum SourceKind: String, Codable, Sendable, CaseIterable {
            case factoryRun = "factory-run"
            case specialistPackage = "specialist-package"
        }

        public struct DatasetHash: Codable, Hashable, Sendable {
            public let path: String
            public let rows: Int?
            public let sha256: String

            public init(path: String, rows: Int? = nil, sha256: String) {
                self.path = path
                self.rows = rows
                self.sha256 = sha256
            }
        }

        public let compiler: String
        public let compilerVersion: String
        public let sourceKind: SourceKind
        public let sourceId: String
        public let datasetHashes: [DatasetHash]

        public init(compiler: String,
                    compilerVersion: String,
                    sourceKind: SourceKind,
                    sourceId: String,
                    datasetHashes: [DatasetHash] = []) {
            self.compiler = compiler
            self.compilerVersion = compilerVersion
            self.sourceKind = sourceKind
            self.sourceId = sourceId
            self.datasetHashes = datasetHashes
        }
    }

    public struct ArtifactRef: Codable, Hashable, Sendable {
        public let artifactId: String
        public let kind: String
        public let path: String?
        public let packageDir: String?
        public let shipped: Bool
        /// The named route or task envelope the artifact is safe inside. A
        /// shipped candidate that regressed a breadth gate may only publish
        /// with this set.
        public let routingConstraint: Field

        public init(artifactId: String,
                    kind: String,
                    path: String? = nil,
                    packageDir: String? = nil,
                    shipped: Bool,
                    routingConstraint: Field) {
            self.artifactId = artifactId
            self.kind = kind
            self.path = path
            self.packageDir = packageDir
            self.shipped = shipped
            self.routingConstraint = routingConstraint
        }
    }

    public struct Subject: Codable, Hashable, Sendable {
        public let target: Field
        public let ownerGoal: Field
        public let baseModel: Field
        public let candidateModel: Field
        public let method: Field
        public let artifact: ArtifactRef
    }

    public struct DecisionBlock: Codable, Hashable, Sendable {
        public let decision: FactoryRun.Decision
        public let outcomeLabel: OutcomeLabel
        public let verified: Bool
        public let verificationBlockers: [String]
        public let reason: String
        public let failureReason: String?
        public let failureReasonConfidence: String
        public let lesson: String?
        public let nextAction: Field
        public let blockedBy: [String]
        public let evidenceSources: [String]
    }

    public struct EvalIdentity: Codable, Hashable, Sendable {
        public let suite: String
        public let command: Field
        public let date: Field
        public let frozen: Field
    }

    public struct Gate: Codable, Hashable, Sendable {
        public let role: GateRole
        public let name: String
        public let metric: String
        public let baseline: Field
        public let candidate: Field
        public let delta: Field
        public let threshold: Field
        public let passed: Field
        public let sampleSize: Field
        public let frontierCeiling: Field
        public let evalIdentity: EvalIdentity

        /// True when the gate is recorded as failing. A `missing` result is not
        /// a pass: it is simply unknown.
        public var didFail: Bool {
            passed.hasValue && passed.value?.boolean == false
        }
    }

    public struct Slice: Codable, Hashable, Sendable {
        public let name: String
        public let metric: String
        public let baseline: Field
        public let candidate: Field
        public let delta: Field
        public let passed: Field
        public let sampleSize: Field
    }

    public struct Performance: Codable, Hashable, Sendable {
        public let latencyMs: Field
        public let peakRssMb: Field
        public let tokensPerSecond: Field
        public let trainingTimeSeconds: Field
        public let trainingCostUsd: Field
        public let evalTimeSeconds: Field

        public var allFields: [(String, Field)] {
            [("latency_ms", latencyMs),
             ("peak_rss_mb", peakRssMb),
             ("tokens_per_second", tokensPerSecond),
             ("training_time_seconds", trainingTimeSeconds),
             ("training_cost_usd", trainingCostUsd),
             ("eval_time_seconds", evalTimeSeconds)]
        }
    }

    public struct EvalValidity: Codable, Hashable, Sendable {
        public let frontierCeiling: Field
        public let frozenEval: Field
        public let leakage: Field
        public let knownLimitations: [String]

        public static let noOverlap = "no-overlap"
        public static let overlapDetected = "overlap-detected"

        public var overlapDetected: Bool {
            leakage.hasValue && leakage.value?.text == EvalValidity.overlapDetected
        }
    }

    public struct Evidence: Codable, Hashable, Sendable {
        public let label: String
        public let path: String
        public let kind: String
        public let sha256: String?
        public let note: String?
    }

    public struct Card: Codable, Hashable, Sendable {
        public let schemaVersion: Int
        public let reportCardId: String
        public let title: String
        public let compiledFrom: CompiledFrom
        public let subject: Subject
        public let decision: DecisionBlock
        public let gates: [Gate]
        public let slices: [Slice]
        public let performance: Performance
        public let evalValidity: EvalValidity
        public let evidence: [Evidence]
        public let caveats: [String]

        public var primaryGate: Gate? {
            gates.first { $0.role == .primary }
        }

        /// Regression and breadth gates recorded as failing.
        public var regressedGates: [Gate] {
            gates.filter { $0.role != .primary && $0.didFail }
        }

        /// True when the candidate is recorded as missing its own target gate.
        /// Recording that failure as *measured* is not the same as passing it.
        public var primaryGateFailed: Bool {
            primaryGate?.didFail ?? false
        }

        /// Whether the evidence actually supports `decision.verified == true`.
        ///
        /// Recomputed from the payload rather than trusted, because the gate is
        /// exactly where a hand-edited or third-party card arrives. Mirrors
        /// `fine_tune_report_card.verification_blockers`; the substance, not the
        /// blocker wording, is the contract.
        public var verificationChainHolds: Bool {
            guard decision.decision == .ship, decision.blockedBy.isEmpty else { return false }
            guard let primary = primaryGate, !primary.didFail else { return false }
            for field in [primary.baseline, primary.candidate, primary.threshold, primary.passed] {
                guard field.hasValue, !field.isWeak else { return false }
            }
            guard let ceiling = primary.frontierCeiling.value?.double,
                  primary.frontierCeiling.hasValue,
                  !primary.frontierCeiling.isWeak,
                  ceiling >= 0.99 else { return false }
            guard evalValidity.frozenEval.hasValue, !evalValidity.frozenEval.isWeak else {
                return false
            }
            guard evalValidity.leakage.hasValue, !evalValidity.leakage.isWeak,
                  evalValidity.leakage.value?.text == EvalValidity.noOverlap else {
                return false
            }
            return true
        }

        /// Validate the schema, the per-field provenance rules, and the
        /// decision/publication policy.
        ///
        /// `allowReportOnly` permits a non-ship card with open blockers. Ship
        /// claims stay strict in both modes: an incomplete ship fails closed.
        public func validate(allowReportOnly: Bool = false) throws {
            guard schemaVersion == FineTuneReportCard.schemaVersion else {
                throw ValidationError.unsupportedSchemaVersion(schemaVersion)
            }
            try requireNonEmpty(reportCardId, "report_card_id")
            try requireNonEmpty(title, "title")
            try requireNonEmpty(compiledFrom.compiler, "compiled_from.compiler")
            try requireNonEmpty(compiledFrom.compilerVersion, "compiled_from.compiler_version")
            try requireNonEmpty(compiledFrom.sourceId, "compiled_from.source_id")
            for (index, hash) in compiledFrom.datasetHashes.enumerated() {
                try requireNonEmpty(hash.path, "compiled_from.dataset_hashes[\(index)].path")
                guard hash.sha256.count == 64 else {
                    throw ValidationError.invalidField(
                        "compiled_from.dataset_hashes[\(index)].sha256 must be a sha256 hex digest")
                }
            }

            try subject.target.validate("subject.target")
            try subject.ownerGoal.validate("subject.owner_goal")
            try subject.baseModel.validate("subject.base_model")
            try subject.candidateModel.validate("subject.candidate_model")
            try subject.method.validate("subject.method")
            try requireNonEmpty(subject.artifact.artifactId, "subject.artifact.artifact_id")
            try requireNonEmpty(subject.artifact.kind, "subject.artifact.kind")
            try subject.artifact.routingConstraint.validate("subject.artifact.routing_constraint")

            try validateDecision()
            try validateGates()

            for (index, slice) in slices.enumerated() {
                let path = "slices[\(index)]"
                try requireNonEmpty(slice.name, "\(path).name")
                try requireNonEmpty(slice.metric, "\(path).metric")
                try slice.baseline.validate("\(path).baseline")
                try slice.candidate.validate("\(path).candidate")
                try slice.delta.validate("\(path).delta")
                try slice.passed.validate("\(path).passed")
                try slice.sampleSize.validate("\(path).sample_size")
                // A per-slice number is as publishable as a gate's, so it gets
                // the same consistency check.
                try requireConsistentDelta(
                    delta: slice.delta,
                    baseline: slice.baseline,
                    candidate: slice.candidate,
                    label: slice.name)
            }

            for (name, field) in performance.allFields {
                try field.validate("performance.\(name)")
            }
            try evalValidity.frontierCeiling.validate("eval_validity.frontier_ceiling")
            try evalValidity.frozenEval.validate("eval_validity.frozen_eval")
            try evalValidity.leakage.validate("eval_validity.leakage")
            if evalValidity.leakage.hasValue {
                let text = evalValidity.leakage.value?.text
                guard text == EvalValidity.noOverlap || text == EvalValidity.overlapDetected else {
                    throw ValidationError.invalidField(
                        "eval_validity.leakage value must be `no-overlap` or `overlap-detected`")
                }
            }

            guard !evidence.isEmpty else {
                throw ValidationError.invalidField("evidence must not be empty")
            }
            for (index, item) in evidence.enumerated() {
                try requireNonEmpty(item.label, "evidence[\(index)].label")
                try requireNonEmpty(item.path, "evidence[\(index)].path")
                try requireNonEmpty(item.kind, "evidence[\(index)].kind")
            }

            try validatePublicationPolicy(allowReportOnly: allowReportOnly)
        }

        private func validateDecision() throws {
            try requireNonEmpty(decision.reason, "decision.reason")
            try decision.nextAction.validate("decision.next_action")
            guard !decision.evidenceSources.isEmpty else {
                throw ValidationError.invalidField("decision.evidence_sources must not be empty")
            }
            let allowedConfidence = ["exact", "inferred", "missing-evidence", "not-applicable"]
            guard allowedConfidence.contains(decision.failureReasonConfidence) else {
                throw ValidationError.invalidField(
                    "decision.failure_reason_confidence must be one of \(allowedConfidence)")
            }
            let isShip = decision.decision == .ship
            if isShip {
                guard decision.failureReasonConfidence == "not-applicable" else {
                    throw ValidationError.invalidField(
                        "ship decision must use failure_reason_confidence=not-applicable")
                }
                guard decision.outcomeLabel.claimsShip else {
                    throw ValidationError.labelDecisionMismatch(
                        label: decision.outcomeLabel.rawValue,
                        decision: decision.decision.rawValue)
                }
            } else {
                if decision.outcomeLabel.claimsShip {
                    throw ValidationError.labelDecisionMismatch(
                        label: decision.outcomeLabel.rawValue,
                        decision: decision.decision.rawValue)
                }
                if isBlank(decision.failureReason) {
                    throw ValidationError.invalidField("non-ship decision.failure_reason is required")
                }
                if isBlank(decision.lesson) {
                    throw ValidationError.invalidField("non-ship decision.lesson is required")
                }
                guard decision.failureReasonConfidence != "not-applicable" else {
                    throw ValidationError.invalidField(
                        "non-ship decision requires a real failure_reason_confidence")
                }
                guard decision.nextAction.hasValue else {
                    throw ValidationError.invalidField(
                        "decision `\(decision.decision.rawValue)` requires exactly one next action with a value")
                }
            }
            if decision.verified && !decision.verificationBlockers.isEmpty {
                throw ValidationError.verifiedWithBlockers
            }
            if !decision.verified && decision.verificationBlockers.isEmpty {
                throw ValidationError.invalidField(
                    "decision.verified=false requires at least one verification blocker")
            }
            // Self-consistency is not enough: recompute from the evidence so a
            // payload cannot assert its own verification status.
            if decision.verified != verificationChainHolds {
                throw ValidationError.verificationMismatch(claimed: decision.verified)
            }
        }

        private func validateGates() throws {
            guard !gates.isEmpty else {
                throw ValidationError.invalidField("gates must not be empty")
            }
            let primaries = gates.filter { $0.role == .primary }
            guard primaries.count == 1 else {
                throw ValidationError.invalidField("exactly one gate must have role `primary`")
            }
            for (index, gate) in gates.enumerated() {
                let path = "gates[\(index)]"
                try requireNonEmpty(gate.name, "\(path).name")
                try requireNonEmpty(gate.metric, "\(path).metric")
                try gate.baseline.validate("\(path).baseline")
                try gate.candidate.validate("\(path).candidate")
                try gate.delta.validate("\(path).delta")
                try gate.threshold.validate("\(path).threshold")
                try gate.passed.validate("\(path).passed")
                try gate.sampleSize.validate("\(path).sample_size")
                try gate.frontierCeiling.validate("\(path).frontier_ceiling")
                try requireNonEmpty(gate.evalIdentity.suite, "\(path).eval_identity.suite")
                try gate.evalIdentity.command.validate("\(path).eval_identity.command")
                try gate.evalIdentity.date.validate("\(path).eval_identity.date")
                try gate.evalIdentity.frozen.validate("\(path).eval_identity.frozen")

                try requireConsistentDelta(
                    delta: gate.delta,
                    baseline: gate.baseline,
                    candidate: gate.candidate,
                    label: gate.name)
            }
        }

        /// A recorded delta must agree with its inputs: a report card may not
        /// carry a hand-typed delta that contradicts the measurements.
        private func requireConsistentDelta(delta: Field,
                                            baseline: Field,
                                            candidate: Field,
                                            label: String) throws {
            guard delta.hasValue, baseline.hasValue, candidate.hasValue else { return }
            guard let d = delta.value?.double,
                  let b = baseline.value?.double,
                  let c = candidate.value?.double else {
                throw ValidationError.invalidField(
                    "`\(label)`: baseline, candidate, and delta must be numbers to be comparable")
            }
            if abs(d - (c - b)) > 1e-6 {
                throw ValidationError.deltaMismatch(gate: label)
            }
        }

        private func validatePublicationPolicy(allowReportOnly: Bool) throws {
            if evalValidity.overlapDetected {
                throw ValidationError.leakageDetected(note: evalValidity.leakage.note)
            }
            if decision.decision == .ship {
                guard subject.artifact.shipped else {
                    throw ValidationError.invalidField(
                        "ship decision requires subject.artifact.shipped=true")
                }
                guard !isBlank(subject.artifact.packageDir) else {
                    throw ValidationError.invalidField(
                        "ship decision requires subject.artifact.package_dir")
                }
                guard decision.blockedBy.isEmpty else {
                    throw ValidationError.invalidField("ship decision must not have open blockers")
                }
                guard let primary = primaryGate, primary.baseline.hasValue, primary.candidate.hasValue else {
                    throw ValidationError.incompleteShipClaim
                }
                if primary.didFail {
                    throw ValidationError.shipWithFailedPrimaryGate(gate: primary.name)
                }
                let regressed = regressedGates
                if !regressed.isEmpty && !subject.artifact.routingConstraint.hasValue {
                    throw ValidationError.undisclosedRoutedShip(
                        gates: regressed.map(\.name))
                }
            } else {
                if subject.artifact.shipped {
                    throw ValidationError.invalidField(
                        "decision `\(decision.decision.rawValue)` must not carry subject.artifact.shipped=true")
                }
                if !allowReportOnly && !decision.blockedBy.isEmpty {
                    throw ValidationError.blockersWithoutReportOnly(
                        decision: decision.decision.rawValue)
                }
            }
        }
    }

    // MARK: - Errors

    public enum ValidationError: Error, CustomStringConvertible, Equatable {
        case unsupportedSchemaVersion(Int)
        case invalidField(String)
        case missingValue(path: String, state: String)
        case missingSource(path: String, state: String)
        case missingNote(path: String, state: String)
        case missingDerivedFrom(path: String)
        case unexpectedValue(path: String, state: String)
        case labelDecisionMismatch(label: String, decision: String)
        case verifiedWithBlockers
        case deltaMismatch(gate: String)
        case incompleteShipClaim
        case shipWithFailedPrimaryGate(gate: String)
        case undisclosedRoutedShip(gates: [String])
        case leakageDetected(note: String?)
        case blockersWithoutReportOnly(decision: String)
        case verificationMismatch(claimed: Bool)
        case denylistedField(path: String)

        public var description: String {
            switch self {
            case .unsupportedSchemaVersion(let version):
                return "unsupported report-card schema_version \(version); expected \(FineTuneReportCard.schemaVersion)"
            case .invalidField(let message):
                return message
            case .missingValue(let path, let state):
                return "\(path): state `\(state)` requires a non-null value"
            case .missingSource(let path, let state):
                return "\(path): state `\(state)` requires at least one source"
            case .missingNote(let path, let state):
                return "\(path): state `\(state)` requires an explanatory note"
            case .missingDerivedFrom(let path):
                return "\(path): state `derived` requires derived_from"
            case .unexpectedValue(let path, let state):
                return "\(path): state `\(state)` must carry a null value"
            case .labelDecisionMismatch(let label, let decision):
                return "decision.outcome_label `\(label)` is inconsistent with decision `\(decision)`"
            case .verifiedWithBlockers:
                return "decision.verified=true contradicts a non-empty verification_blockers"
            case .deltaMismatch(let gate):
                return "gate `\(gate)` delta does not equal candidate - baseline"
            case .incompleteShipClaim:
                return "ship decision requires a primary gate with baseline and candidate values"
            case .shipWithFailedPrimaryGate(let gate):
                return "ship decision whose primary gate `\(gate)` is recorded as failing "
                    + "cannot publish: the candidate missed its own target"
            case .verificationMismatch(let claimed):
                return "decision.verified=\(claimed) does not match the evidence"
            case .denylistedField(let path):
                return "\(path): denylisted private field name"
            case .undisclosedRoutedShip(let gates):
                return "ship decision with failing gate(s) [\(gates.joined(separator: ", "))] requires a routing constraint"
            case .leakageDetected(let note):
                return "leakage check reports overlap-detected; publication is blocked"
                    + (note.map { " (\($0))" } ?? "")
            case .blockersWithoutReportOnly(let decision):
                return "decision `\(decision)` has open blockers; report-only publication must be explicit"
            }
        }
    }

    // MARK: - Coding

    /// Field names that must never appear in a public report card. Mirrors
    /// `fine_tune_report_card.DENYLISTED_KEYS`.
    ///
    /// A report card is a proof surface, not a data dump: prompts, completions,
    /// golds, predictions, weights, and credentials stay in the private run
    /// folder.
    public static let denylistedKeys: Set<String> = [
        "prompt", "prompts", "completion", "completions", "gold", "golds",
        "prediction", "predictions", "weights", "weights_bytes", "adapter_bytes",
        "optimizer_state", "checkpoint", "api_key", "secret", "password",
        "credential",
    ]

    /// Shares `FactoryRun`'s snake_case strategy so both contracts read and
    /// write the same JSON conventions.
    public static func decode(_ data: Data) throws -> Card {
        try FactoryRun.decode(Card.self, from: data)
    }

    public static func read(from url: URL) throws -> Card {
        try decode(try Data(contentsOf: url))
    }

    /// Reject a payload carrying a denylisted field name.
    ///
    /// This walks the raw JSON rather than the typed `Card`, because the typed
    /// decoder silently drops unknown keys — a private payload smuggled into an
    /// undeclared field would otherwise decode cleanly.
    public static func checkPublicSafety(_ data: Data) throws {
        let root = try JSONSerialization.jsonObject(with: data)
        try scanForDenylistedKeys(root, path: "report_card")
    }

    private static func scanForDenylistedKeys(_ node: Any, path: String) throws {
        if let object = node as? [String: Any] {
            for key in object.keys.sorted() {
                let lowered = key.lowercased()
                let isDenylisted = denylistedKeys.contains(lowered)
                    || denylistedKeys.contains(where: { lowered.hasSuffix("_" + $0) })
                if isDenylisted {
                    throw ValidationError.denylistedField(path: "\(path).\(key)")
                }
                try scanForDenylistedKeys(object[key] as Any, path: "\(path).\(key)")
            }
        } else if let array = node as? [Any] {
            for (index, value) in array.enumerated() {
                try scanForDenylistedKeys(value, path: "\(path)[\(index)]")
            }
        }
    }

    /// Read, public-safety scan, and validate a published report card.
    @discardableResult
    public static func validate(at url: URL, allowReportOnly: Bool = false) throws -> Card {
        let data = try Data(contentsOf: url)
        try checkPublicSafety(data)
        let card = try decode(data)
        try card.validate(allowReportOnly: allowReportOnly)
        return card
    }

    public static func encode(_ card: Card) throws -> Data {
        try FactoryRun.encode(card)
    }
}

// MARK: - Helpers

private func isBlank(_ value: String?) -> Bool {
    guard let value else { return true }
    return value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
}

private func requireNonEmpty(_ value: String?, _ field: String) throws {
    if isBlank(value) {
        throw FineTuneReportCard.ValidationError.invalidField("\(field) must not be empty")
    }
}
