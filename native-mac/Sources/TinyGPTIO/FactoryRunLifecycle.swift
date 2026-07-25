import Darwin
import Foundation

/// Durable, model-free operational state for a factory run.
///
/// `run-status.json` is authoritative for lifecycle state. `decision.json`
/// remains authoritative for the run's quality/product outcome.
public enum FactoryRunLifecycle {
    public static let schemaVersion = 1
    public static let statusFile = "run-status.json"
    public static let currentPointerFile = "current-run.json"
    public static let latestPointerFile = "latest-run.json"
    public static let lockDirectory = ".run-status.lock"
    public static let lockOwnerFile = "owner.json"
    public static let staleAfter: TimeInterval = 24 * 60 * 60

    public enum Phase: String, Codable, CaseIterable, Sendable {
        case created
        case dataReady = "data-ready"
        case training
        case trained
        case evaluating
        case evaluated
        case packaging
        case packaged
        case reporting
        case decided
        case failed

        public var isTerminal: Bool {
            self == .decided || self == .failed
        }
    }

    public struct TransitionProvenance: Codable, Hashable, Sendable {
        public let source: String
        public let command: String
        public let reason: String?

        public init(source: String, command: String, reason: String? = nil) {
            self.source = source
            self.command = command
            self.reason = reason
        }
    }

    public struct Failure: Codable, Hashable, Sendable {
        public let code: String
        public let summary: String

        public init(code: String, summary: String) {
            self.code = code
            self.summary = summary
        }
    }

    public struct Status: Codable, Hashable, Sendable {
        public let schemaVersion: Int
        public let runId: String
        public let revision: Int
        public let phase: Phase
        public let updatedAt: String
        public let lastTransition: TransitionProvenance
        public let parentRunId: String?
        public let successorRunId: String?
        public let failure: Failure?
        public let imported: Bool
        public let importEvidence: [String]

        public init(schemaVersion: Int = FactoryRunLifecycle.schemaVersion,
                    runId: String,
                    revision: Int,
                    phase: Phase,
                    updatedAt: String,
                    lastTransition: TransitionProvenance,
                    parentRunId: String? = nil,
                    successorRunId: String? = nil,
                    failure: Failure? = nil,
                    imported: Bool = false,
                    importEvidence: [String] = []) {
            self.schemaVersion = schemaVersion
            self.runId = runId
            self.revision = revision
            self.phase = phase
            self.updatedAt = updatedAt
            self.lastTransition = lastTransition
            self.parentRunId = parentRunId
            self.successorRunId = successorRunId
            self.failure = failure
            self.imported = imported
            self.importEvidence = importEvidence
        }
    }

    public struct Pointer: Codable, Hashable, Sendable {
        public let schemaVersion: Int
        public let relativeRunPath: String
        public let runId: String
        public let lifecycleRevision: Int
        public let phase: Phase
        public let updatedAt: String

        public init(relativeRunPath: String, status: Status) {
            self.schemaVersion = FactoryRunLifecycle.schemaVersion
            self.relativeRunPath = relativeRunPath
            self.runId = status.runId
            self.lifecycleRevision = status.revision
            self.phase = status.phase
            self.updatedAt = status.updatedAt
        }
    }

    public struct RunRecord: Codable, Hashable, Sendable, Identifiable {
        public let relativeRunPath: String
        public let status: Status
        public let warnings: [String]

        public var id: String { status.runId }
        public var isStale: Bool { warnings.contains { $0.hasPrefix("stale-active:") } }

        public init(relativeRunPath: String, status: Status, warnings: [String]) {
            self.relativeRunPath = relativeRunPath
            self.status = status
            self.warnings = warnings
        }
    }

    public enum Filter: String, Sendable {
        case all
        case active
        case terminal
        case failed
        case imported
        case stale
    }

    public struct Diagnostic: Codable, Hashable, Sendable {
        public let kind: String
        public let path: String
        public let message: String

        public init(kind: String, path: String, message: String) {
            self.kind = kind
            self.path = path
            self.message = message
        }
    }

    public struct ReconciliationReport: Codable, Hashable, Sendable {
        public let dryRun: Bool
        public let diagnostics: [Diagnostic]
        public let repairs: [String]
        public let current: Pointer?
        public let latest: Pointer?

        public init(dryRun: Bool,
                    diagnostics: [Diagnostic],
                    repairs: [String],
                    current: Pointer?,
                    latest: Pointer?) {
            self.dryRun = dryRun
            self.diagnostics = diagnostics
            self.repairs = repairs
            self.current = current
            self.latest = latest
        }
    }

    public struct LockDiagnostic: Codable, Hashable, Sendable {
        public let pid: Int32?
        public let acquiredAt: String?
        public let stale: Bool
    }

    private struct LockOwner: Codable {
        let pid: Int32
        let acquiredAt: String
    }

    public enum LifecycleError: Error, CustomStringConvertible, Equatable {
        case alreadyInitialized
        case missingStatus
        case unsupportedSchema(Int)
        case invalidField(String)
        case identityMismatch(status: String, config: String)
        case invalidTransition(from: Phase, to: Phase)
        case alternateReasonRequired(from: Phase, to: Phase)
        case terminalState(Phase)
        case staleRevision(expected: Int, actual: Int)
        case lockConflict(String)
        case decisionRequired
        case privateField(String)
        case pathEscapesRoot(String)
        case pointerMismatch(String)

        public var description: String {
            switch self {
            case .alreadyInitialized:
                return "\(statusFile) already exists"
            case .missingStatus:
                return "missing \(statusFile)"
            case .unsupportedSchema(let version):
                return "unsupported lifecycle schema_version \(version)"
            case .invalidField(let field):
                return "invalid lifecycle field: \(field)"
            case .identityMismatch(let status, let config):
                return "run-status run_id '\(status)' does not match config run_id '\(config)'"
            case .invalidTransition(let from, let to):
                return "illegal lifecycle transition \(from.rawValue) -> \(to.rawValue)"
            case .alternateReasonRequired(let from, let to):
                return "transition \(from.rawValue) -> \(to.rawValue) requires a machine-readable --reason"
            case .terminalState(let phase):
                return "\(phase.rawValue) is terminal; create a new run linked with --parent-run-id"
            case .staleRevision(let expected, let actual):
                return "stale lifecycle revision \(expected); current revision is \(actual)"
            case .lockConflict(let message):
                return "lifecycle lock conflict: \(message)"
            case .decisionRequired:
                return "transition to decided requires a valid canonical decision.json"
            case .privateField(let field):
                return "lifecycle metadata contains forbidden private field '\(field)'"
            case .pathEscapesRoot(let path):
                return "run pointer escapes configured root: \(path)"
            case .pointerMismatch(let message):
                return "stale or invalid run pointer: \(message)"
            }
        }
    }

    private static let normalEdges: [Phase: Phase] = [
        .created: .dataReady,
        .dataReady: .training,
        .training: .trained,
        .trained: .evaluating,
        .evaluating: .evaluated,
        .evaluated: .packaging,
        .packaging: .packaged,
        .packaged: .reporting,
        .reporting: .decided,
    ]

    private static let alternateEdges: Set<String> = [
        edge(.created, .evaluating),
        edge(.dataReady, .evaluating),
        edge(.created, .reporting),
        edge(.dataReady, .reporting),
        edge(.trained, .reporting),
        edge(.evaluated, .reporting),
    ]

    private static let privateFieldFragments = [
        "prompt", "completion", "gold", "prediction", "trajectory", "raw_log",
        "checkpoint", "weights", "optimizer", "api_key", "secret", "password",
        "credential", "dataset_content", "output_text", "token",
    ]

    @discardableResult
    public static func initialize(directory: URL,
                                  source: String = "operator",
                                  command: String = "factory-run init",
                                  reason: String? = nil,
                                  parentRunId: String? = nil,
                                  now: Date = Date()) throws -> Status {
        try withLock(directory: directory, now: now) {
            let statusURL = directory.appendingPathComponent(statusFile)
            guard !FileManager.default.fileExists(atPath: statusURL.path) else {
                throw LifecycleError.alreadyInitialized
            }
            let config = try readConfig(directory: directory)
            let status = Status(
                runId: config.runId,
                revision: 1,
                phase: .created,
                updatedAt: timestamp(now),
                lastTransition: .init(source: source, command: command, reason: reason),
                parentRunId: parentRunId
            )
            try validate(status)
            try writeStatus(status, directory: directory)
            try refreshPointers(root: directory.deletingLastPathComponent(), now: now)
            return status
        }
    }

    @discardableResult
    public static func importLegacy(directory: URL,
                                    source: String = "operator",
                                    now: Date = Date()) throws -> Status {
        try withLock(directory: directory, now: now) {
            let statusURL = directory.appendingPathComponent(statusFile)
            guard !FileManager.default.fileExists(atPath: statusURL.path) else {
                throw LifecycleError.alreadyInitialized
            }
            let config = try readConfig(directory: directory)
            let fm = FileManager.default
            var phase: Phase = .created
            var evidence = [FactoryRunFolder.configFile]

        let datasetURL = directory.appendingPathComponent(FactoryRunFolder.datasetFile)
        if fm.fileExists(atPath: datasetURL.path),
           let dataset = try? decodeFile(FactoryRun.DatasetManifest.self, at: datasetURL),
           (try? FactoryRun.validate(dataset)) != nil {
            phase = .dataReady
            evidence.append(FactoryRunFolder.datasetFile)
        }

        let baselineURL = directory.appendingPathComponent(FactoryRunFolder.baselineFile)
        let candidateURL = directory.appendingPathComponent(FactoryRunFolder.candidateFile)
        if fm.fileExists(atPath: baselineURL.path),
           fm.fileExists(atPath: candidateURL.path),
           let baseline = try? decodeFile(FactoryRun.EvalResult.self, at: baselineURL),
           let candidate = try? decodeFile(FactoryRun.EvalResult.self, at: candidateURL),
           (try? FactoryRun.validate(baseline)) != nil,
           (try? FactoryRun.validate(candidate)) != nil {
            phase = .evaluated
            evidence.append(contentsOf: [FactoryRunFolder.baselineFile,
                                         FactoryRunFolder.candidateFile])
        }

        let artifactURL = directory.appendingPathComponent(FactoryRunFolder.artifactFile)
        if fm.fileExists(atPath: artifactURL.path),
           let artifact = try? decodeFile(FactoryRun.Artifact.self, at: artifactURL),
           (try? FactoryRun.validate(artifact)) != nil {
            phase = .packaged
            evidence.append(FactoryRunFolder.artifactFile)
        }

        let reportURL = directory.appendingPathComponent(FactoryRunFolder.reportFile)
        if fm.fileExists(atPath: reportURL.path),
           let report = try? String(contentsOf: reportURL, encoding: .utf8),
           !report.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            phase = .reporting
            evidence.append(FactoryRunFolder.reportFile)
        }

        if (try? FactoryRunFolder.validate(directory: directory)) != nil {
            phase = .decided
            evidence.append(FactoryRunFolder.decisionFile)
        }

            let status = Status(
                runId: config.runId,
                revision: 1,
                phase: phase,
                updatedAt: timestamp(now),
                lastTransition: .init(
                    source: source,
                    command: "factory-run init --import-legacy",
                    reason: "legacy-evidence-import"
                ),
                imported: true,
                importEvidence: Array(Set(evidence)).sorted()
            )
            try validate(status)
            if phase == .decided {
                try validateDecision(directory: directory)
            }
            try writeStatus(status, directory: directory)
            try refreshPointers(root: directory.deletingLastPathComponent(), now: now)
            return status
        }
    }

    public static func readStatus(directory: URL) throws -> Status {
        let url = directory.appendingPathComponent(statusFile)
        guard FileManager.default.fileExists(atPath: url.path) else {
            throw LifecycleError.missingStatus
        }
        let data = try Data(contentsOf: url)
        try validatePrivateFields(data)
        let status = try FactoryRun.decode(Status.self, from: data)
        try validate(status)
        let config = try readConfig(directory: directory)
        guard status.runId == config.runId else {
            throw LifecycleError.identityMismatch(status: status.runId, config: config.runId)
        }
        if status.phase == .decided {
            try validateDecision(directory: directory)
        }
        return status
    }

    public static func validate(_ status: Status) throws {
        guard status.schemaVersion == schemaVersion else {
            throw LifecycleError.unsupportedSchema(status.schemaVersion)
        }
        try requireIdentifier(status.runId, field: "run_id", max: 160)
        guard status.revision >= 1 else {
            throw LifecycleError.invalidField("revision must be >= 1")
        }
        guard parseTimestamp(status.updatedAt) != nil else {
            throw LifecycleError.invalidField("updated_at must be ISO8601")
        }
        try requireMetadata(status.lastTransition.source,
                            field: "last_transition.source", max: 64)
        try requireMetadata(status.lastTransition.command,
                            field: "last_transition.command", max: 160)
        if let reason = status.lastTransition.reason {
            try requireMetadata(reason, field: "last_transition.reason", max: 128)
        }
        if let parent = status.parentRunId {
            try requireIdentifier(parent, field: "parent_run_id", max: 160)
        }
        if let successor = status.successorRunId {
            try requireIdentifier(successor, field: "successor_run_id", max: 160)
        }
        for item in status.importEvidence {
            try requireMetadata(item, field: "import_evidence", max: 128)
        }
        if status.imported && status.importEvidence.isEmpty {
            throw LifecycleError.invalidField("imported status requires import_evidence")
        }
        if status.phase == .failed {
            guard let failure = status.failure else {
                throw LifecycleError.invalidField("failed phase requires failure")
            }
            try validate(failure)
        } else if status.failure != nil {
            throw LifecycleError.invalidField("failure is allowed only in failed phase")
        }
    }

    public static func validate(_ failure: Failure) throws {
        try requireReasonCode(failure.code, field: "failure.code")
        let summary = failure.summary.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !summary.isEmpty, summary.count <= 240,
              !summary.contains("\n"), !summary.contains("\r"),
              !privateFieldFragments.contains(where: {
                  summary.lowercased().contains($0.replacingOccurrences(of: "_", with: " "))
              }) else {
            throw LifecycleError.invalidField(
                "failure.summary must be one bounded line without private payload markers"
            )
        }
    }

    @discardableResult
    public static func transition(directory: URL,
                                  to target: Phase,
                                  expectedRevision: Int,
                                  source: String = "operator",
                                  command: String = "factory-run transition",
                                  reason: String? = nil,
                                  parentRunId: String? = nil,
                                  successorRunId: String? = nil,
                                  failure: Failure? = nil,
                                  dryRun: Bool = false,
                                  now: Date = Date()) throws -> Status {
        try withLock(directory: directory, now: now) {
            let current = try readStatus(directory: directory)
            guard current.revision == expectedRevision else {
                throw LifecycleError.staleRevision(expected: expectedRevision,
                                                   actual: current.revision)
            }
            guard !current.phase.isTerminal else {
                throw LifecycleError.terminalState(current.phase)
            }
            let alternate = try validateTransition(from: current.phase,
                                                   to: target,
                                                   reason: reason)
            if alternate, let reason {
                try requireReasonCode(reason, field: "last_transition.reason")
            }
            if target == .failed {
                guard let failure else {
                    throw LifecycleError.invalidField(
                        "transition to failed requires failure code and summary"
                    )
                }
                try validate(failure)
            } else if failure != nil {
                throw LifecycleError.invalidField("failure is allowed only for failed")
            }
            if target == .decided {
                try validateDecision(directory: directory)
            }

            let next = Status(
                runId: current.runId,
                revision: current.revision + 1,
                phase: target,
                updatedAt: timestamp(now),
                lastTransition: .init(source: source, command: command, reason: reason),
                parentRunId: try mergeRelationship(
                    current.parentRunId, parentRunId, field: "parent_run_id"
                ),
                successorRunId: try mergeRelationship(
                    current.successorRunId, successorRunId, field: "successor_run_id"
                ),
                failure: failure,
                imported: current.imported,
                importEvidence: current.importEvidence
            )
            try validate(next)
            if !dryRun {
                try writeStatus(next, directory: directory)
                try refreshPointers(root: directory.deletingLastPathComponent(), now: now)
            }
            return next
        }
    }

    public static func list(root: URL,
                            filter: Filter = .all,
                            now: Date = Date()) throws -> [RunRecord] {
        let records = try scan(root: root, now: now).records
        return records.filter { record in
            switch filter {
            case .all: return true
            case .active: return !record.status.phase.isTerminal
            case .terminal: return record.status.phase.isTerminal
            case .failed: return record.status.phase == .failed
            case .imported: return record.status.imported
            case .stale: return record.isStale
            }
        }
    }

    public static func validatedPointer(root: URL, fileName: String) throws -> Pointer? {
        let url = root.appendingPathComponent(fileName)
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let data = try Data(contentsOf: url)
        let pointer = try FactoryRun.decode(Pointer.self, from: data)
        guard pointer.schemaVersion == schemaVersion else {
            throw LifecycleError.pointerMismatch("unsupported schema")
        }
        let directory = try resolve(pointer.relativeRunPath, within: root)
        let status = try readStatus(directory: directory)
        guard status.runId == pointer.runId,
              status.revision == pointer.lifecycleRevision,
              status.phase == pointer.phase,
              status.updatedAt == pointer.updatedAt else {
            throw LifecycleError.pointerMismatch("\(fileName) disagrees with \(statusFile)")
        }
        return pointer
    }

    public static func reconcile(root: URL,
                                 write: Bool = false,
                                 now: Date = Date(),
                                 staleInterval: TimeInterval = staleAfter) throws
        -> ReconciliationReport {
        let fm = FileManager.default
        let scanned = try scan(root: root, now: now, staleInterval: staleInterval)
        var diagnostics = scanned.diagnostics
        var repairs: [String] = []

        for directory in scanned.directories {
            let lock = lockDiagnostic(directory: directory,
                                      now: now,
                                      staleInterval: staleInterval)
            if let lock, lock.stale {
                diagnostics.append(.init(
                    kind: "stale-lock",
                    path: relativePath(directory.appendingPathComponent(lockDirectory),
                                       from: root),
                    message: "metadata lock is stale; no process was killed"
                ))
                if write {
                    try? fm.removeItem(at: directory.appendingPathComponent(lockDirectory))
                    repairs.append("removed stale lock for \(relativePath(directory, from: root))")
                }
            }

            let files = (try? fm.contentsOfDirectory(at: directory,
                                                     includingPropertiesForKeys: nil)) ?? []
            let temporary = files.filter {
                $0.lastPathComponent.hasPrefix(".run-status.")
                    && $0.pathExtension == "tmp"
            }
            for file in temporary where lock == nil || lock?.stale == true {
                diagnostics.append(.init(
                    kind: "abandoned-temporary",
                    path: relativePath(file, from: root),
                    message: "temporary lifecycle snapshot is not authoritative"
                ))
                if write, lock == nil || lock?.stale == true {
                    try? fm.removeItem(at: file)
                    repairs.append("removed \(relativePath(file, from: root))")
                }
            }
        }

        let desired = desiredPointers(records: scanned.records)
        for (file, pointer) in [(currentPointerFile, desired.current),
                                (latestPointerFile, desired.latest)] {
            let existing: Pointer?
            var invalid = false
            do {
                existing = try validatedPointer(root: root, fileName: file)
            } catch {
                existing = nil
                invalid = true
                diagnostics.append(.init(kind: "invalid-pointer",
                                         path: file,
                                         message: String(describing: error)))
            }
            if existing != pointer || invalid {
                if existing == nil,
                   fm.fileExists(atPath: root.appendingPathComponent(file).path),
                   !diagnostics.contains(where: { $0.kind == "invalid-pointer" && $0.path == file }) {
                    diagnostics.append(.init(kind: "stale-pointer",
                                             path: file,
                                             message: "pointer does not match selected run"))
                } else if existing != nil {
                    diagnostics.append(.init(kind: "stale-pointer",
                                             path: file,
                                             message: "pointer does not match selected run"))
                } else if pointer != nil {
                    diagnostics.append(.init(kind: "missing-pointer",
                                             path: file,
                                             message: "pointer can be rebuilt from run statuses"))
                }
                if write {
                    try writeOptionalPointer(pointer, fileName: file, root: root)
                    repairs.append(pointer == nil ? "removed \(file)" : "rebuilt \(file)")
                }
            }
        }

        return ReconciliationReport(dryRun: !write,
                                    diagnostics: diagnostics,
                                    repairs: repairs,
                                    current: desired.current,
                                    latest: desired.latest)
    }

    public static func lockDiagnostic(directory: URL,
                                      now: Date = Date(),
                                      staleInterval: TimeInterval = staleAfter)
        -> LockDiagnostic? {
        let lockURL = directory.appendingPathComponent(lockDirectory)
        guard FileManager.default.fileExists(atPath: lockURL.path) else { return nil }
        let ownerURL = lockURL.appendingPathComponent(lockOwnerFile)
        guard let data = try? Data(contentsOf: ownerURL),
              let owner = try? FactoryRun.decode(LockOwner.self, from: data),
              let acquired = parseTimestamp(owner.acquiredAt) else {
            return LockDiagnostic(pid: nil, acquiredAt: nil, stale: true)
        }
        return LockDiagnostic(pid: owner.pid,
                              acquiredAt: owner.acquiredAt,
                              stale: now.timeIntervalSince(acquired) > staleInterval)
    }

    private struct ScanResult {
        let records: [RunRecord]
        let diagnostics: [Diagnostic]
        let directories: [URL]
    }

    private static func scan(root: URL,
                             now: Date,
                             staleInterval: TimeInterval = staleAfter) throws -> ScanResult {
        let fm = FileManager.default
        guard fm.fileExists(atPath: root.path) else {
            return ScanResult(records: [], diagnostics: [], directories: [])
        }
        let candidates = try fm.contentsOfDirectory(
            at: root,
            includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        ).filter { url in
            (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true
        }.sorted { $0.lastPathComponent < $1.lastPathComponent }

        var records: [RunRecord] = []
        var diagnostics: [Diagnostic] = []
        for directory in candidates {
            let statusURL = directory.appendingPathComponent(statusFile)
            guard fm.fileExists(atPath: statusURL.path) else { continue }
            do {
                let status = try readStatus(directory: directory)
                var warnings: [String] = []
                if !status.phase.isTerminal,
                   let updated = parseTimestamp(status.updatedAt),
                   now.timeIntervalSince(updated) > staleInterval {
                    warnings.append(
                        "stale-active: status is older than \(Int(staleInterval)) seconds; "
                            + "it remains active until an explicit operator transition"
                    )
                }
                records.append(.init(relativeRunPath: relativePath(directory, from: root),
                                     status: status,
                                     warnings: warnings))
            } catch {
                diagnostics.append(.init(kind: "invalid-status",
                                         path: relativePath(statusURL, from: root),
                                         message: String(describing: error)))
            }
        }
        records.sort {
            if $0.status.updatedAt == $1.status.updatedAt {
                return $0.relativeRunPath < $1.relativeRunPath
            }
            return $0.status.updatedAt > $1.status.updatedAt
        }
        return ScanResult(records: records,
                          diagnostics: diagnostics,
                          directories: candidates)
    }

    private static func refreshPointers(root: URL, now: Date) throws {
        let records = try scan(root: root, now: now).records
        let desired = desiredPointers(records: records)
        try writeOptionalPointer(desired.current,
                                 fileName: currentPointerFile,
                                 root: root)
        try writeOptionalPointer(desired.latest,
                                 fileName: latestPointerFile,
                                 root: root)
    }

    private static func desiredPointers(records: [RunRecord])
        -> (current: Pointer?, latest: Pointer?) {
        let current = records.first { !$0.status.phase.isTerminal }
        let latest = records.first { $0.status.phase.isTerminal }
        return (
            current.map { Pointer(relativeRunPath: $0.relativeRunPath, status: $0.status) },
            latest.map { Pointer(relativeRunPath: $0.relativeRunPath, status: $0.status) }
        )
    }

    private static func writeOptionalPointer(_ pointer: Pointer?,
                                             fileName: String,
                                             root: URL) throws {
        let url = root.appendingPathComponent(fileName)
        if let pointer {
            try atomicWrite(FactoryRun.encode(pointer),
                            to: url,
                            temporaryPrefix: ".\(fileName).")
        } else if FileManager.default.fileExists(atPath: url.path) {
            try FileManager.default.removeItem(at: url)
        }
    }

    private static func validateTransition(from: Phase,
                                           to: Phase,
                                           reason: String?) throws -> Bool {
        if to == .failed { return false }
        if normalEdges[from] == to { return false }
        if alternateEdges.contains(edge(from, to)) {
            guard let reason, !reason.isEmpty else {
                throw LifecycleError.alternateReasonRequired(from: from, to: to)
            }
            return true
        }
        throw LifecycleError.invalidTransition(from: from, to: to)
    }

    private static func validateDecision(directory: URL) throws {
        let url = directory.appendingPathComponent(FactoryRunFolder.decisionFile)
        guard FileManager.default.fileExists(atPath: url.path),
              let decision = try? decodeFile(FactoryRun.DecisionRecord.self, at: url),
              (try? FactoryRun.validate(decision)) != nil else {
            throw LifecycleError.decisionRequired
        }
    }

    private static func readConfig(directory: URL) throws -> FactoryRun.Config {
        let config = try decodeFile(
            FactoryRun.Config.self,
            at: directory.appendingPathComponent(FactoryRunFolder.configFile)
        )
        try FactoryRun.validate(config)
        return config
    }

    private static func decodeFile<T: Decodable>(_ type: T.Type, at url: URL) throws -> T {
        try FactoryRun.decode(type, from: Data(contentsOf: url))
    }

    private static func writeStatus(_ status: Status, directory: URL) throws {
        try atomicWrite(FactoryRun.encode(status),
                        to: directory.appendingPathComponent(statusFile),
                        temporaryPrefix: ".run-status.")
    }

    private static func atomicWrite(_ data: Data,
                                    to destination: URL,
                                    temporaryPrefix: String) throws {
        try FileManager.default.createDirectory(
            at: destination.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let temporary = destination.deletingLastPathComponent()
            .appendingPathComponent("\(temporaryPrefix)\(UUID().uuidString).tmp")
        do {
            try data.write(to: temporary)
            let result = temporary.path.withCString { source in
                destination.path.withCString { target in
                    Darwin.rename(source, target)
                }
            }
            guard result == 0 else {
                throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
            }
        } catch {
            try? FileManager.default.removeItem(at: temporary)
            throw error
        }
    }

    private static func withLock<T>(directory: URL,
                                    now: Date,
                                    body: () throws -> T) throws -> T {
        let fm = FileManager.default
        let lockURL = directory.appendingPathComponent(lockDirectory)
        do {
            try fm.createDirectory(at: lockURL, withIntermediateDirectories: false)
        } catch {
            let diagnostic = lockDiagnostic(directory: directory, now: now)
            let detail: String
            if let diagnostic {
                detail = diagnostic.stale
                    ? "stale lock detected; run factory-run reconcile --write"
                    : "held by pid \(diagnostic.pid.map(String.init) ?? "unknown")"
            } else {
                detail = "lock already exists"
            }
            throw LifecycleError.lockConflict(detail)
        }
        let owner = LockOwner(pid: ProcessInfo.processInfo.processIdentifier,
                              acquiredAt: timestamp(now))
        do {
            try FactoryRun.encode(owner).write(
                to: lockURL.appendingPathComponent(lockOwnerFile),
                options: [.atomic]
            )
        } catch {
            try? fm.removeItem(at: lockURL)
            throw error
        }
        defer { try? fm.removeItem(at: lockURL) }
        return try body()
    }

    private static func validatePrivateFields(_ data: Data) throws {
        let object = try JSONSerialization.jsonObject(with: data)
        try walkPrivateFields(object)
    }

    private static func walkPrivateFields(_ value: Any) throws {
        if let dictionary = value as? [String: Any] {
            for (key, child) in dictionary {
                let lowered = key.lowercased()
                if privateFieldFragments.contains(where: { lowered.contains($0) }) {
                    throw LifecycleError.privateField(key)
                }
                try walkPrivateFields(child)
            }
        } else if let array = value as? [Any] {
            for child in array { try walkPrivateFields(child) }
        }
    }

    private static func requireIdentifier(_ value: String,
                                          field: String,
                                          max: Int) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, trimmed.count <= max,
              !trimmed.contains("\n"), !trimmed.contains("\r") else {
            throw LifecycleError.invalidField("\(field) must be one bounded line")
        }
    }

    private static func requireMetadata(_ value: String,
                                        field: String,
                                        max: Int) throws {
        try requireIdentifier(value, field: field, max: max)
    }

    private static func requireReasonCode(_ value: String, field: String) throws {
        guard value.count <= 64,
              value.range(of: #"^[a-z0-9][a-z0-9._-]*$"#,
                          options: .regularExpression) != nil else {
            throw LifecycleError.invalidField(
                "\(field) must be a lowercase machine-readable code"
            )
        }
    }

    private static func mergeRelationship(_ current: String?,
                                          _ requested: String?,
                                          field: String) throws -> String? {
        guard let requested else { return current }
        if let current, current != requested {
            throw LifecycleError.invalidField("\(field) cannot be rewritten")
        }
        return requested
    }

    private static func resolve(_ relative: String, within root: URL) throws -> URL {
        guard !relative.hasPrefix("/") else {
            throw LifecycleError.pathEscapesRoot(relative)
        }
        let rootURL = root.standardizedFileURL.resolvingSymlinksInPath()
        let candidate = root.appendingPathComponent(relative)
            .standardizedFileURL.resolvingSymlinksInPath()
        let prefix = rootURL.path.hasSuffix("/") ? rootURL.path : rootURL.path + "/"
        guard candidate.path.hasPrefix(prefix) else {
            throw LifecycleError.pathEscapesRoot(relative)
        }
        return candidate
    }

    private static func relativePath(_ url: URL, from root: URL) -> String {
        let rootPath = root.standardizedFileURL.path
        let path = url.standardizedFileURL.path
        let prefix = rootPath.hasSuffix("/") ? rootPath : rootPath + "/"
        return path.hasPrefix(prefix) ? String(path.dropFirst(prefix.count)) : path
    }

    private static func edge(_ from: Phase, _ to: Phase) -> String {
        "\(from.rawValue)->\(to.rawValue)"
    }

    private static func timestamp(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }

    private static func parseTimestamp(_ value: String) -> Date? {
        ISO8601DateFormatter().date(from: value)
    }
}
