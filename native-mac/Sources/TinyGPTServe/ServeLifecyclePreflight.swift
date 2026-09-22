import Darwin
import Foundation
import TinyGPTIO
import TinyGPTModel

/// Resolves and validates lifecycle metadata before the server loads model or
/// adapter bytes. Kept separate from the socket implementation so the safety
/// boundary stays small and independently reviewable.
enum ServeLifecyclePreflight {
    static func load(
        modelPath: String,
        loraPaths: [String]
    ) throws -> ModelLoader.LoadResult {
        let modelURL = URL(fileURLWithPath: modelPath)
        var isDirectory: ObjCBool = false
        _ = FileManager.default.fileExists(atPath: modelURL.path, isDirectory: &isDirectory)
        let runtime: ArtifactLifecycleManifest.Runtime = isDirectory.boolValue
            ? .nativeHFLoad : .nativeTinyGPT
        let lifecycle = try ArtifactLifecycleStore.inspect(
            base: modelURL,
            adapters: loraPaths.map { URL(fileURLWithPath: $0) },
            action: .serve,
            runtime: runtime
        )
        if let base = lifecycle.base {
            fputs("serve lifecycle: \(base.summary)\n", stderr)
        }
        for adapter in lifecycle.adapters.compactMap({ $0 }) {
            fputs("serve adapter lifecycle: \(adapter.summary)\n", stderr)
        }
        for warning in lifecycle.warnings {
            fputs("warning: \(warning).\n", stderr)
        }
        return try ModelLoader.load(modelPath)
    }
}
