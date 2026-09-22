import Foundation

/// Versioned lifecycle metadata for a model artifact.
///
/// Weight formats answer how bytes are encoded. This sidecar answers what the
/// artifact is, which exact base/tokenizer it belongs to, how it was produced,
/// which runtimes accept it, and which actions are safe next. The contract is
/// model-free so training, loading, serving, and packaging share one source of
/// truth without initializing MLX.
public struct ArtifactLifecycleManifest: Codable, Hashable, Sendable {
    public static let schemaVersion = 1
    public static let directoryFilename = "artifact-manifest.json"
    public static let fileSuffix = ".artifact-manifest.json"

    public enum Kind: String, Codable, CaseIterable, Sendable {
        case baseModel = "base-model"
        case adapter
        case trainingCheckpoint = "training-checkpoint"
        case deployPackage = "deploy-package"
    }

    public enum Runtime: String, Codable, CaseIterable, Sendable {
        case nativeTinyGPT = "native-tinygpt"
        case nativeHFLoad = "native-hf-load"
        case pythonMLX = "python-mlx"
        case mlxLM = "mlx-lm"
        case ollama
    }

    public enum NextAction: String, Codable, CaseIterable, Sendable {
        case resumeExactly = "resume-exactly"
        case warmRestart = "warm-restart"
        case merge
        case convert
        case eval
        case serve
    }

    public struct Identity: Codable, Hashable, Sendable {
        public let id: String
        public let revision: String?
        public let checkpoint: String?

        public init(id: String, revision: String? = nil, checkpoint: String? = nil) {
            self.id = id
            self.revision = revision
            self.checkpoint = checkpoint
        }
    }

    public struct Tokenizer: Codable, Hashable, Sendable {
        public let id: String
        public let revision: String?
        public let chatTemplate: String?

        public init(id: String, revision: String? = nil, chatTemplate: String? = nil) {
            self.id = id
            self.revision = revision
            self.chatTemplate = chatTemplate
        }

        enum CodingKeys: String, CodingKey {
            case id, revision
            case chatTemplate = "chat_template"
        }
    }

    public struct HistoryStep: Codable, Hashable, Sendable {
        public let action: String
        public let tool: String
        public let detail: String?

        public init(action: String, tool: String, detail: String? = nil) {
            self.action = action
            self.tool = tool
            self.detail = detail
        }
    }

    public struct Receipt: Codable, Hashable, Sendable {
        public let kind: String
        public let path: String

        public init(kind: String, path: String) {
            self.kind = kind
            self.path = path
        }
    }

    public struct TrainingState: Codable, Hashable, Sendable {
        public let optimizer: Bool
        public let scheduler: Bool
        public let rng: Bool

        public init(optimizer: Bool, scheduler: Bool, rng: Bool) {
            self.optimizer = optimizer
            self.scheduler = scheduler
            self.rng = rng
        }

        public var supportsExactResume: Bool { optimizer && scheduler && rng }
    }

    public struct Diagnostic: Codable, Hashable, Sendable, CustomStringConvertible {
        public let field: String
        public let message: String

        public init(field: String, message: String) {
            self.field = field
            self.message = message
        }

        public var description: String { "\(field): \(message)" }
    }

    public let schemaVersion: Int
    public let artifact: Identity
    public let kind: Kind
    public let artifactPath: String
    public let base: Identity?
    public let tokenizer: Tokenizer
    public let history: [HistoryStep]
    public let runtimes: [Runtime]
    public let next: [NextAction]
    public let receipts: [Receipt]
    public let trainingState: TrainingState?
    public let createdAt: String

    public init(
        schemaVersion: Int = ArtifactLifecycleManifest.schemaVersion,
        artifact: Identity,
        kind: Kind,
        artifactPath: String,
        base: Identity? = nil,
        tokenizer: Tokenizer,
        history: [HistoryStep],
        runtimes: [Runtime],
        next: [NextAction],
        receipts: [Receipt] = [],
        trainingState: TrainingState? = nil,
        createdAt: String = ISO8601DateFormatter().string(from: Date())
    ) {
        self.schemaVersion = schemaVersion
        self.artifact = artifact
        self.kind = kind
        self.artifactPath = artifactPath
        self.base = base
        self.tokenizer = tokenizer
        self.history = history
        self.runtimes = runtimes
        self.next = next
        self.receipts = receipts
        self.trainingState = trainingState
        self.createdAt = createdAt
    }

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case artifact, kind
        case artifactPath = "artifact_path"
        case base, tokenizer, history, runtimes, next, receipts
        case trainingState = "training_state"
        case createdAt = "created_at"
    }

    public func diagnostics() -> [Diagnostic] {
        var issues: [Diagnostic] = []
        if schemaVersion != Self.schemaVersion {
            issues.append(.init(field: "schema_version", message: "expected \(Self.schemaVersion)"))
        }
        Self.require(artifact.id, field: "artifact.id", into: &issues)
        Self.validateBounded(artifact.revision, field: "artifact.revision", into: &issues)
        Self.validateBounded(artifact.checkpoint, field: "artifact.checkpoint", into: &issues)
        Self.require(tokenizer.id, field: "tokenizer.id", into: &issues)
        Self.validateBounded(tokenizer.revision, field: "tokenizer.revision", into: &issues)
        Self.validateBounded(tokenizer.chatTemplate, field: "tokenizer.chat_template", into: &issues)
        Self.validateRelative(artifactPath, field: "artifact_path", into: &issues)
        if ISO8601DateFormatter().date(from: createdAt) == nil {
            issues.append(.init(field: "created_at", message: "must be an ISO-8601 timestamp"))
        }
        if history.isEmpty {
            issues.append(.init(field: "history", message: "must contain at least one production step"))
        }
        if runtimes.isEmpty {
            issues.append(.init(field: "runtimes", message: "must name at least one compatible runtime"))
        }
        if next.isEmpty {
            issues.append(.init(field: "next", message: "must name at least one legal next action"))
        }
        if kind == .adapter {
            if let base {
                Self.require(base.id, field: "base.id", into: &issues)
                Self.validateBounded(base.revision, field: "base.revision", into: &issues)
                Self.validateBounded(base.checkpoint, field: "base.checkpoint", into: &issues)
                if Self.blank(base.revision) && Self.blank(base.checkpoint) {
                    issues.append(.init(
                        field: "base",
                        message: "adapter base must pin revision or checkpoint"
                    ))
                }
            } else {
                issues.append(.init(field: "base", message: "adapter requires a pinned base"))
            }
        }
        if next.contains(.resumeExactly), trainingState?.supportsExactResume != true {
            issues.append(.init(
                field: "next",
                message: "resume-exactly requires optimizer, scheduler, and RNG state"
            ))
        }
        if next.contains(.resumeExactly), Self.blank(artifact.checkpoint) {
            issues.append(.init(
                field: "artifact.checkpoint",
                message: "resume-exactly requires a pinned checkpoint identity"
            ))
        }
        if history.count > 64 {
            issues.append(.init(field: "history", message: "must contain at most 64 steps"))
        }
        if receipts.count > 64 {
            issues.append(.init(field: "receipts", message: "must contain at most 64 references"))
        }
        for (index, step) in history.enumerated() {
            Self.require(step.action, field: "history[\(index)].action", into: &issues)
            Self.require(step.tool, field: "history[\(index)].tool", into: &issues)
            Self.validateBounded(step.detail, field: "history[\(index)].detail", into: &issues)
        }
        for (index, receipt) in receipts.enumerated() {
            Self.require(receipt.kind, field: "receipts[\(index)].kind", into: &issues)
            Self.validateRelative(receipt.path, field: "receipts[\(index)].path", into: &issues)
        }
        return issues
    }

    public func allows(_ action: NextAction) -> Bool { next.contains(action) }

    public var summary: String {
        let actions = next.map(\.rawValue).joined(separator: ", ")
        return "\(kind.rawValue) \(artifact.id); next: \(actions)"
    }

    public static func adapterMismatch(
        adapter: ArtifactLifecycleManifest,
        base: ArtifactLifecycleManifest
    ) -> Diagnostic? {
        guard adapter.kind == .adapter, let expected = adapter.base else { return nil }
        if expected.id != base.artifact.id {
            return .init(
                field: "base.id",
                message: "adapter expects \(expected.id), selected \(base.artifact.id)"
            )
        }
        if let revision = expected.revision,
           let actual = base.artifact.revision,
           revision != actual {
            return .init(
                field: "base.revision",
                message: "adapter expects \(revision), selected \(actual)"
            )
        }
        if let checkpoint = expected.checkpoint,
           let actual = base.artifact.checkpoint,
           checkpoint != actual {
            return .init(
                field: "base.checkpoint",
                message: "adapter expects \(checkpoint), selected \(actual)"
            )
        }
        return nil
    }

    /// True only when every identity component pinned by the adapter is also
    /// present on the selected base. A false value is not proof of mismatch;
    /// consumers use it to emit the explicit legacy/unverifiable warning.
    public static func canVerifyAdapterBinding(
        adapter: ArtifactLifecycleManifest,
        base: ArtifactLifecycleManifest
    ) -> Bool {
        guard adapter.kind == .adapter, let expected = adapter.base,
              expected.id == base.artifact.id else { return false }
        if expected.revision != nil, base.artifact.revision == nil { return false }
        if expected.checkpoint != nil, base.artifact.checkpoint == nil { return false }
        return true
    }

    private static func require(
        _ value: String,
        field: String,
        into issues: inout [Diagnostic]
    ) {
        if blank(value) { issues.append(.init(field: field, message: "is required")) }
        validateBounded(value, field: field, into: &issues)
    }

    private static func validateBounded(
        _ value: String?,
        field: String,
        into issues: inout [Diagnostic]
    ) {
        guard let value else { return }
        if value.count > 512 {
            issues.append(.init(field: field, message: "must be at most 512 characters"))
        }
        let lowered = value.lowercased()
        let sensitive = [
            "bearer ", "token=", "password=", "secret=", "api_key=",
            "prompt=", "prompt:", "completion=", "completion:", "model_output", "model output",
        ]
        let hasHFToken = lowered.range(
            of: #"(?<![a-z0-9])hf_[a-z0-9]{16,}"#,
            options: .regularExpression
        ) != nil
        if hasHFToken || sensitive.contains(where: lowered.contains) {
            issues.append(.init(field: field, message: "contains sensitive or credential-like payload"))
        }
        if value.contains("\n") || value.contains("\r") {
            issues.append(.init(field: field, message: "must be a single bounded line"))
        }
    }

    private static func validateRelative(
        _ value: String,
        field: String,
        into issues: inout [Diagnostic]
    ) {
        require(value, field: field, into: &issues)
        let path = NSString(string: value)
        if path.isAbsolutePath || path.pathComponents.contains("..") {
            issues.append(.init(field: field, message: "must be a safe relative path"))
        }
    }

    private static func blank(_ value: String?) -> Bool {
        value?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true
    }
}

public enum ArtifactLifecycleStore {
    public struct Inspection: Sendable {
        public let base: ArtifactLifecycleManifest?
        public let adapters: [ArtifactLifecycleManifest?]
        public let warnings: [String]

        public init(
            base: ArtifactLifecycleManifest?,
            adapters: [ArtifactLifecycleManifest?],
            warnings: [String]
        ) {
            self.base = base
            self.adapters = adapters
            self.warnings = warnings
        }
    }

    public enum StoreError: Error, CustomStringConvertible, Sendable {
        case invalid([ArtifactLifecycleManifest.Diagnostic])
        case actionNotAllowed(
            ArtifactLifecycleManifest.NextAction,
            allowed: [ArtifactLifecycleManifest.NextAction]
        )
        case runtimeNotSupported(
            ArtifactLifecycleManifest.Runtime,
            supported: [ArtifactLifecycleManifest.Runtime]
        )

        public var description: String {
            switch self {
            case .invalid(let diagnostics):
                return diagnostics.map(\.description).joined(separator: "; ")
            case .actionNotAllowed(let action, let allowed):
                return "\(action.rawValue) is not allowed; next: "
                    + allowed.map(\.rawValue).joined(separator: ", ")
            case .runtimeNotSupported(let runtime, let supported):
                return "\(runtime.rawValue) is not supported; runtimes: "
                    + supported.map(\.rawValue).joined(separator: ", ")
            }
        }
    }

    public static func sidecarURL(for artifact: URL) -> URL {
        var isDirectory: ObjCBool = false
        if FileManager.default.fileExists(atPath: artifact.path, isDirectory: &isDirectory),
           isDirectory.boolValue {
            return artifact.appendingPathComponent(ArtifactLifecycleManifest.directoryFilename)
        }
        return URL(fileURLWithPath: artifact.path + ArtifactLifecycleManifest.fileSuffix)
    }

    public static func load(for artifact: URL) throws -> ArtifactLifecycleManifest? {
        let sidecar = sidecarURL(for: artifact)
        guard FileManager.default.fileExists(atPath: sidecar.path) else { return nil }
        let manifest = try JSONDecoder().decode(
            ArtifactLifecycleManifest.self,
            from: Data(contentsOf: sidecar)
        )
        try validate(manifest, adjacentTo: artifact)
        return manifest
    }

    public static func requireUse(
        _ manifest: ArtifactLifecycleManifest,
        action: ArtifactLifecycleManifest.NextAction,
        runtime: ArtifactLifecycleManifest.Runtime
    ) throws {
        guard manifest.allows(action) else {
            throw StoreError.actionNotAllowed(action, allowed: manifest.next)
        }
        try requireRuntime(manifest, runtime: runtime)
    }

    public static func requireRuntime(
        _ manifest: ArtifactLifecycleManifest,
        runtime: ArtifactLifecycleManifest.Runtime
    ) throws {
        guard manifest.runtimes.contains(runtime) else {
            throw StoreError.runtimeNotSupported(runtime, supported: manifest.runtimes)
        }
    }

    /// Inspect a base plus optional adapters before any model bytes are loaded.
    /// Missing sidecars are legacy warnings; malformed manifests, illegal
    /// actions/runtimes, and proven adapter/base mismatches throw.
    public static func inspect(
        base baseURL: URL,
        adapters adapterURLs: [URL] = [],
        action: ArtifactLifecycleManifest.NextAction? = nil,
        runtime: ArtifactLifecycleManifest.Runtime
    ) throws -> Inspection {
        let base = try load(for: baseURL)
        var warnings: [String] = []
        if let base {
            if base.kind == .adapter {
                throw StoreError.invalid([.init(
                    field: "kind",
                    message: "selected base artifact cannot be an adapter"
                )])
            }
            if let action {
                try requireUse(base, action: action, runtime: runtime)
            } else {
                try requireRuntime(base, runtime: runtime)
            }
        } else {
            warnings.append(
                "legacy base has no artifact lifecycle manifest; lifecycle/base verification is unavailable"
            )
        }

        var adapters: [ArtifactLifecycleManifest?] = []
        adapters.reserveCapacity(adapterURLs.count)
        for adapterURL in adapterURLs {
            guard let adapter = try load(for: adapterURL) else {
                warnings.append(
                    "legacy adapter \(adapterURL.lastPathComponent) has no lifecycle manifest; base binding is unverified"
                )
                adapters.append(nil)
                continue
            }
            if adapter.kind != .adapter {
                throw StoreError.invalid([.init(
                    field: "kind",
                    message: "adapter input must declare kind=adapter"
                )])
            }
            if let action {
                try requireUse(adapter, action: action, runtime: runtime)
            } else {
                try requireRuntime(adapter, runtime: runtime)
            }
            if let base, let mismatch = ArtifactLifecycleManifest.adapterMismatch(
                adapter: adapter,
                base: base
            ) {
                throw StoreError.invalid([mismatch])
            }
            if let base {
                if !ArtifactLifecycleManifest.canVerifyAdapterBinding(
                    adapter: adapter,
                    base: base
                ) {
                    warnings.append(
                        "adapter \(adapterURL.lastPathComponent) binding is not fully verifiable from the selected base manifest"
                    )
                }
            } else {
                warnings.append(
                    "adapter \(adapterURL.lastPathComponent) binding cannot be verified against a legacy base"
                )
            }
            adapters.append(adapter)
        }
        return Inspection(base: base, adapters: adapters, warnings: warnings)
    }

    @discardableResult
    public static func write(
        _ manifest: ArtifactLifecycleManifest,
        for artifact: URL
    ) throws -> URL {
        try validate(manifest, adjacentTo: artifact)
        let sidecar = sidecarURL(for: artifact)
        try FileManager.default.createDirectory(
            at: sidecar.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        try encoder.encode(manifest).write(to: sidecar, options: .atomic)
        return sidecar
    }

    private static func validate(
        _ manifest: ArtifactLifecycleManifest,
        adjacentTo artifact: URL
    ) throws {
        var diagnostics = manifest.diagnostics()
        let expectedPath = expectedArtifactPath(for: artifact)
        if manifest.artifactPath != expectedPath {
            diagnostics.append(.init(
                field: "artifact_path",
                message: "expected \(expectedPath) for adjacent artifact"
            ))
        }
        guard diagnostics.isEmpty else { throw StoreError.invalid(diagnostics) }
    }

    private static func expectedArtifactPath(for artifact: URL) -> String {
        var isDirectory: ObjCBool = false
        if FileManager.default.fileExists(atPath: artifact.path, isDirectory: &isDirectory),
           isDirectory.boolValue {
            return "."
        }
        return artifact.lastPathComponent
    }
}
