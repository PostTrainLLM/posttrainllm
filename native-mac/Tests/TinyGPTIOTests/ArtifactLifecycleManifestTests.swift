import Foundation
import Testing
@testable import TinyGPTIO

@Suite("Artifact lifecycle manifest")
struct ArtifactLifecycleManifestTests {
    private func completeAdapter(
        next: [ArtifactLifecycleManifest.NextAction] = [.merge, .eval, .serve]
    ) -> ArtifactLifecycleManifest {
        ArtifactLifecycleManifest(
            artifact: .init(id: "pace-adapter", revision: "recipe-v1"),
            kind: .adapter,
            artifactPath: "pace-adapter.lora",
            base: .init(id: "Qwen/Qwen3-4B", revision: "abc123"),
            tokenizer: .init(id: "Qwen/Qwen3-4B", revision: "abc123", chatTemplate: "chatml"),
            history: [.init(action: "sft", tool: "posttrainllm", detail: "recipe-v1")],
            runtimes: [.nativeHFLoad],
            next: next,
            receipts: [.init(kind: "eval", path: "receipts/eval.json")],
            createdAt: "2026-09-22T00:00:00Z"
        )
    }

    @Test("round trips and relocates with a file artifact")
    func roundTripAndRelocation() throws {
        let first = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let moved = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: first, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: moved, withIntermediateDirectories: true)
        defer {
            try? FileManager.default.removeItem(at: first)
            try? FileManager.default.removeItem(at: moved)
        }

        let artifact = first.appendingPathComponent("pace-adapter.lora")
        try Data([0x54, 0x47, 0x4c, 0x41]).write(to: artifact)
        let sidecar = try ArtifactLifecycleStore.write(completeAdapter(), for: artifact)

        let movedArtifact = moved.appendingPathComponent(artifact.lastPathComponent)
        let movedSidecar = moved.appendingPathComponent(sidecar.lastPathComponent)
        try FileManager.default.copyItem(at: artifact, to: movedArtifact)
        try FileManager.default.copyItem(at: sidecar, to: movedSidecar)

        let discovered = try ArtifactLifecycleStore.load(for: movedArtifact)
        let loaded = try #require(discovered)
        #expect(loaded.artifact.id == "pace-adapter")
        #expect(loaded.allows(.serve))
    }

    @Test("discovers a directory sidecar after relocation")
    func directoryRelocation() throws {
        let original = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        let moved = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: original, withIntermediateDirectories: true)
        defer {
            try? FileManager.default.removeItem(at: original)
            try? FileManager.default.removeItem(at: moved)
        }
        let manifest = ArtifactLifecycleManifest(
            artifact: .init(id: "pace-deploy", revision: "abc123"),
            kind: .deployPackage,
            artifactPath: ".",
            base: .init(id: "Qwen/Qwen3-4B", revision: "abc123"),
            tokenizer: .init(id: "Qwen/Qwen3-4B", revision: "abc123"),
            history: [.init(action: "export-mlx", tool: "posttrainllm")],
            runtimes: [.mlxLM],
            next: [.serve],
            createdAt: "2026-09-22T00:00:00Z"
        )
        try ArtifactLifecycleStore.write(manifest, for: original)
        try FileManager.default.copyItem(at: original, to: moved)

        let discovered = try ArtifactLifecycleStore.load(for: moved)
        let loaded = try #require(discovered)
        #expect(loaded.kind == .deployPackage)
        #expect(loaded.allows(.serve))
    }

    @Test("atomically replaces an existing sidecar")
    func atomicReplacement() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let artifact = root.appendingPathComponent("pace-adapter.lora")
        try Data([0]).write(to: artifact)

        try ArtifactLifecycleStore.write(completeAdapter(next: [.eval]), for: artifact)
        try ArtifactLifecycleStore.write(completeAdapter(next: [.serve]), for: artifact)

        let loaded = try ArtifactLifecycleStore.load(for: artifact)
        #expect(loaded?.next == [.serve])
    }

    @Test("rejects malformed and incorrectly bound sidecars")
    func malformedAndWrongBinding() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let artifact = root.appendingPathComponent("actual.lora")
        try Data([0]).write(to: artifact)
        let sidecar = ArtifactLifecycleStore.sidecarURL(for: artifact)
        try Data("not-json".utf8).write(to: sidecar)
        #expect(throws: DecodingError.self) {
            try ArtifactLifecycleStore.load(for: artifact)
        }

        let wrong = ArtifactLifecycleManifest(
            artifact: .init(id: "pace-adapter"),
            kind: .adapter,
            artifactPath: "different.lora",
            base: .init(id: "Qwen/Qwen3-4B", revision: "abc123"),
            tokenizer: .init(id: "Qwen/Qwen3-4B", revision: "abc123"),
            history: [.init(action: "sft", tool: "posttrainllm")],
            runtimes: [.nativeHFLoad],
            next: [.eval],
            createdAt: "2026-09-22T00:00:00Z"
        )
        let encoded = try JSONEncoder().encode(wrong)
        try encoded.write(to: sidecar)
        #expect(throws: ArtifactLifecycleStore.StoreError.self) {
            try ArtifactLifecycleStore.load(for: artifact)
        }
    }

    @Test("reports all missing fields without guessing")
    func completeDiagnostics() {
        let manifest = ArtifactLifecycleManifest(
            artifact: .init(id: ""),
            kind: .adapter,
            artifactPath: "../escape.lora",
            tokenizer: .init(id: ""),
            history: [],
            runtimes: [],
            next: [],
            receipts: [.init(kind: "eval", path: "../outside.json")],
            createdAt: "2026-09-22T00:00:00Z"
        )
        let fields = Set(manifest.diagnostics().map(\.field))
        #expect(fields.contains("artifact.id"))
        #expect(fields.contains("artifact_path"))
        #expect(fields.contains("base"))
        #expect(fields.contains("tokenizer.id"))
        #expect(fields.contains("history"))
        #expect(fields.contains("runtimes"))
        #expect(fields.contains("next"))
        #expect(fields.contains("receipts[0].path"))
    }

    @Test("exact resume requires complete training state")
    func exactResumeRequiresState() {
        let manifest = ArtifactLifecycleManifest(
            artifact: .init(id: "checkpoint", checkpoint: "step-20"),
            kind: .trainingCheckpoint,
            artifactPath: "checkpoint.tinygpt",
            tokenizer: .init(id: "byte-v1"),
            history: [.init(action: "pretrain", tool: "posttrainllm")],
            runtimes: [.nativeTinyGPT],
            next: [.resumeExactly, .warmRestart],
            trainingState: .init(optimizer: true, scheduler: false, rng: true),
            createdAt: "2026-09-22T00:00:00Z"
        )
        #expect(manifest.diagnostics().contains { $0.field == "next" })
    }

    @Test("adapter base mismatch is explicit")
    func baseMismatch() throws {
        let base = ArtifactLifecycleManifest(
            artifact: .init(id: "Qwen/Qwen3-4B", revision: "different"),
            kind: .baseModel,
            artifactPath: ".",
            tokenizer: .init(id: "Qwen/Qwen3-4B", revision: "different"),
            history: [.init(action: "download", tool: "huggingface")],
            runtimes: [.nativeHFLoad],
            next: [.eval, .serve],
            createdAt: "2026-09-22T00:00:00Z"
        )
        let mismatch = try #require(
            ArtifactLifecycleManifest.adapterMismatch(adapter: completeAdapter(), base: base)
        )
        #expect(mismatch.field == "base.revision")
    }

    @Test("shared consumer inspection refuses a proven mismatch before load")
    func consumerMismatchRefusal() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let baseURL = root.appendingPathComponent("base.tinygpt")
        let adapterURL = root.appendingPathComponent("pace-adapter.lora")
        try Data([0]).write(to: baseURL)
        try Data([0]).write(to: adapterURL)
        let base = ArtifactLifecycleManifest(
            artifact: .init(id: "Qwen/Qwen3-4B", revision: "different"),
            kind: .baseModel,
            artifactPath: baseURL.lastPathComponent,
            tokenizer: .init(id: "Qwen/Qwen3-4B", revision: "different"),
            history: [.init(action: "download", tool: "huggingface")],
            runtimes: [.nativeTinyGPT],
            next: [.eval],
            createdAt: "2026-09-22T00:00:00Z"
        )
        var adapter = completeAdapter(next: [.eval])
        adapter = ArtifactLifecycleManifest(
            artifact: adapter.artifact,
            kind: adapter.kind,
            artifactPath: adapterURL.lastPathComponent,
            base: adapter.base,
            tokenizer: adapter.tokenizer,
            history: adapter.history,
            runtimes: [.nativeTinyGPT],
            next: adapter.next,
            receipts: adapter.receipts,
            createdAt: adapter.createdAt
        )
        try ArtifactLifecycleStore.write(base, for: baseURL)
        try ArtifactLifecycleStore.write(adapter, for: adapterURL)

        #expect(throws: ArtifactLifecycleStore.StoreError.self) {
            try ArtifactLifecycleStore.inspect(
                base: baseURL,
                adapters: [adapterURL],
                action: .eval,
                runtime: .nativeTinyGPT
            )
        }

        let misclassified = ArtifactLifecycleManifest(
            artifact: adapter.artifact,
            kind: .deployPackage,
            artifactPath: adapterURL.lastPathComponent,
            base: base.artifact,
            tokenizer: adapter.tokenizer,
            history: adapter.history,
            runtimes: [.nativeTinyGPT],
            next: [.eval],
            createdAt: adapter.createdAt
        )
        try ArtifactLifecycleStore.write(misclassified, for: adapterURL)
        #expect(throws: ArtifactLifecycleStore.StoreError.self) {
            try ArtifactLifecycleStore.inspect(
                base: baseURL,
                adapters: [adapterURL],
                action: .eval,
                runtime: .nativeTinyGPT
            )
        }
    }

    @Test("legacy artifact has no guessed manifest")
    func legacyArtifact() throws {
        let artifact = FileManager.default.temporaryDirectory
            .appendingPathComponent("legacy-\(UUID().uuidString).tinygpt")
        try Data([0]).write(to: artifact)
        defer { try? FileManager.default.removeItem(at: artifact) }
        #expect(try ArtifactLifecycleStore.load(for: artifact) == nil)
        let inspection = try ArtifactLifecycleStore.inspect(
            base: artifact,
            action: .eval,
            runtime: .nativeTinyGPT
        )
        #expect(inspection.warnings.contains { $0.contains("verification is unavailable") })
    }

    @Test("credential-like history is rejected")
    func sensitiveHistory() {
        let manifest = ArtifactLifecycleManifest(
            artifact: .init(id: "model"),
            kind: .baseModel,
            artifactPath: "model.tinygpt",
            tokenizer: .init(id: "byte-v1"),
            history: [.init(action: "download", tool: "posttrainllm", detail: "token=secret")],
            runtimes: [.nativeTinyGPT],
            next: [.eval],
            createdAt: "2026-09-22T00:00:00Z"
        )
        #expect(manifest.diagnostics().contains { $0.message.contains("credential") })
    }

    @Test("prompt payloads and multiline logs are rejected")
    func sensitivePayloads() {
        let manifest = ArtifactLifecycleManifest(
            artifact: .init(id: "model"),
            kind: .baseModel,
            artifactPath: "model.tinygpt",
            tokenizer: .init(id: "byte-v1"),
            history: [.init(
                action: "train",
                tool: "posttrainllm",
                detail: "prompt=private text\nfull log follows"
            )],
            runtimes: [.nativeTinyGPT],
            next: [.eval],
            createdAt: "2026-09-22T00:00:00Z"
        )
        let detailIssues = manifest.diagnostics().filter { $0.field == "history[0].detail" }
        #expect(detailIssues.count == 2)
    }

    @Test("consumer action and runtime gates are explicit")
    func useGates() throws {
        let manifest = completeAdapter(next: [.eval])
        #expect(throws: ArtifactLifecycleStore.StoreError.self) {
            try ArtifactLifecycleStore.requireUse(
                manifest,
                action: .serve,
                runtime: .nativeHFLoad
            )
        }
        #expect(throws: ArtifactLifecycleStore.StoreError.self) {
            try ArtifactLifecycleStore.requireUse(
                manifest,
                action: .eval,
                runtime: .ollama
            )
        }
        try ArtifactLifecycleStore.requireUse(
            manifest,
            action: .eval,
            runtime: .nativeHFLoad
        )
    }
}
