import CryptoKit
import Foundation
import MLX
import TinyGPTModel

/// Bounded, exact-token diagnostic for Python/native specialist conversion.
/// This does one forward pass, without tokenization or generation.
enum DebugHFLogits {
    private struct Probe: Decodable {
        let tokens: [Int32]
        let labels: [Int]
    }
    private struct Provenance: Decodable {
        let base_files: [String: String]
        let native_adapter_sha256: String
    }

    private static func invalid(_ message: String) -> NSError {
        NSError(domain: "HFLogitProbe", code: 2,
                userInfo: [NSLocalizedDescriptionKey: message])
    }

    private static func sha256(_ url: URL) throws -> String {
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        var hash = SHA256()
        while let data = try file.read(upToCount: 1024 * 1024), !data.isEmpty {
            hash.update(data: data)
        }
        return hash.finalize().map { String(format: "%02x", $0) }.joined()
    }

    private static func verify(_ adapter: URL, base: URL) throws {
        let metadata = try JSONDecoder().decode(Provenance.self,
            from: Data(contentsOf: URL(fileURLWithPath: adapter.path + ".json")))
        guard !metadata.base_files.isEmpty,
              try sha256(adapter) == metadata.native_adapter_sha256 else {
            throw invalid("native adapter provenance mismatch")
        }
        let files = try FileManager.default.contentsOfDirectory(at: base,
            includingPropertiesForKeys: nil).filter {
                ["json", "safetensors"].contains($0.pathExtension)
            }.map(\.lastPathComponent)
        guard Set(files) == Set(metadata.base_files.keys) else {
            throw invalid("native base file set changed")
        }
        for (name, expected) in metadata.base_files {
            guard URL(fileURLWithPath: name).lastPathComponent == name,
                  ["json", "safetensors"].contains(URL(fileURLWithPath: name).pathExtension),
                  try sha256(base.appendingPathComponent(name)) == expected else {
                throw invalid("native base identity mismatch: \(name)")
            }
        }
    }

    static func run(args: [String]) throws {
        func value(_ flag: String) throws -> String {
            guard let i = args.firstIndex(of: flag), i + 1 < args.count else {
                throw invalid("debug-logits --hf <base> --probe <json> [--lora <adapter>]")
            }
            return args[i + 1]
        }
        let base = URL(fileURLWithPath: try value("--hf"))
        let probe = try JSONDecoder().decode(Probe.self,
            from: Data(contentsOf: URL(fileURLWithPath: try value("--probe"))))
        let adapter = args.contains("--lora")
            ? URL(fileURLWithPath: try value("--lora")) : nil
        if let adapter { try verify(adapter, base: base) }
        let loaded = try HFModelLoader.load(from: base)
        guard !probe.tokens.isEmpty, probe.tokens.count <= min(256, loaded.config.contextLength),
              !probe.labels.isEmpty, probe.labels.count <= 26,
              probe.tokens.allSatisfy({ $0 >= 0 && $0 < loaded.config.vocabSize }),
              probe.labels.allSatisfy({ $0 >= 0 && $0 < loaded.config.vocabSize }) else {
            throw invalid("invalid or oversized exact-token probe")
        }
        if let adapter {
            try LoraAdapterHFReader.apply(LoraAdapterReader.read(adapter), to: loaded.model)
        }
        let input = MLXArray(probe.tokens, [1, probe.tokens.count])
        let logits = loaded.model(input)[0, probe.tokens.count - 1, 0...].asType(.float32)
        eval(logits)
        let all = logits.asArray(Float.self)
        let selected = probe.labels.map { all[$0] }
        guard selected.allSatisfy({ $0.isFinite }) else { throw invalid("nonfinite logits") }
        let output: [String: Any] = ["schema": "native-exact-token-logits-v1",
            "tokens": probe.tokens.count, "labels": probe.labels, "logits": selected]
        let data = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    }
}
