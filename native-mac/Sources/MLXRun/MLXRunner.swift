import Foundation
import MLXLMCommon
import MLXLLM
import MLXHuggingFace
import HuggingFace
import Tokenizers

/// MLX-Swift-LM runner for `model-run` — Apple's maintained HF model
/// implementations loaded in-process. Covers the archs our own loader
/// doesn't (MoE, VLM, wider quant table) without shelling to a python
/// install that may or may not be healthy.
///
/// The CLI is synchronous; `loadModel`/`ChatSession.respond` are async —
/// we park the calling thread on a semaphore and report through a box.
public enum MLXRunner {

    public enum RunError: Error, LocalizedError {
        case timedOut
        public var errorDescription: String? { "mlx-swift run timed out" }
    }

    /// Load `id` (auto-downloads to the HF cache; honors HF_TOKEN) and
    /// generate a bounded response. Returns the generated text.
    public static func sample(id: String, prompt: String, maxTokens: Int,
                              timeout: TimeInterval = 1800) throws -> String {
        final class Box { var text: String?; var error: Error?; var done = false }
        let box = Box()
        Task.detached {
            defer { box.done = true }
            do {
                // HubClient() auto-detects HF_ENDPOINT + reads HF_TOKEN.
                let model = try await loadModel(
                    from: #hubDownloader(),
                    using: #huggingFaceTokenizerLoader(),
                    id: id) { progress in
                        fputs("\r    downloading: \(Int(progress.fractionCompleted * 100))%", stderr)
                    }
                fputs("\n", stderr)
                var session = ChatSession(model)
                session.generateParameters = .init(maxTokens: maxTokens)
                box.text = try await session.respond(to: prompt)
            } catch {
                box.error = error
            }
        }
        // NOT a semaphore wait — MLXLMCommon hops to the MainActor for
        // parts of load/generate, so the main run loop must keep turning.
        let deadline = Date().addingTimeInterval(timeout)
        while !box.done {
            if Date() > deadline { throw RunError.timedOut }
            RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        if let err = box.error { throw err }
        return box.text ?? ""
    }

    /// Interactive chat loop — blocks on stdin until an empty line.
    public static func chat(id: String) throws {
        final class Box { var error: Error?; var done = false }
        let box = Box()
        Task.detached {
            defer { box.done = true }
            do {
                let model = try await loadModel(
                    from: #hubDownloader(),
                    using: #huggingFaceTokenizerLoader(),
                    id: id)
                let session = ChatSession(model)
                print("(mlx-swift chat — empty line to exit)")
                while let line = readLine(strippingNewline: true), !line.isEmpty {
                    let out = try await session.respond(to: line)
                    print(out)
                }
            } catch {
                box.error = error
            }
        }
        while !box.done {
            RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        if let err = box.error { throw err }
    }
}
