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

    public struct SampleResult: Sendable {
        public let text: String
        public let promptTokens: Int?
        public let generatedTokens: Int?
        public let promptMS: Int?
        public let generationMS: Int?
    }

    public enum RunError: Error, LocalizedError {
        case timedOut
        public var errorDescription: String? { "mlx-swift run timed out" }
    }

    /// Load `id` (auto-downloads to the HF cache; honors HF_TOKEN) and
    /// generate a bounded response. Returns text plus the runtime's exact
    /// prompt/generation counts for the parent model-run receipt.
    public static func sample(id: String, prompt: String, maxTokens: Int,
                              timeout: TimeInterval = 1800) throws -> SampleResult {
        final class Box { var result: SampleResult?; var error: Error?; var done = false }
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
                let session = ChatSession(model)
                session.generateParameters = .init(maxTokens: maxTokens)
                var text = ""
                var promptTokens: Int? = nil
                var generatedTokens: Int? = nil
                var promptMS: Int? = nil
                var generationMS: Int? = nil
                for try await event in session.streamDetails(to: prompt) {
                    if let chunk = event.chunk { text += chunk }
                    if let info = event.info {
                        promptTokens = info.promptTokenCount
                        generatedTokens = info.generationTokenCount
                        promptMS = Int((info.promptTime * 1_000).rounded())
                        generationMS = Int((info.generateTime * 1_000).rounded())
                    }
                }
                box.result = SampleResult(
                    text: text, promptTokens: promptTokens,
                    generatedTokens: generatedTokens, promptMS: promptMS,
                    generationMS: generationMS)
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
        return box.result ?? SampleResult(
            text: "", promptTokens: nil, generatedTokens: nil,
            promptMS: nil, generationMS: nil)
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
