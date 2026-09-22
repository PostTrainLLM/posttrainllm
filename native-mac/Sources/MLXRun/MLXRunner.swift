import Foundation
import MLXLMCommon
import MLXLLM

private final class LockedRunResult: @unchecked Sendable {
    private let lock = NSLock()
    private var result: Result<String, Error>?

    func finish(_ result: Result<String, Error>) {
        lock.lock()
        defer { lock.unlock() }
        guard self.result == nil else { return }
        self.result = result
    }

    func snapshot() -> Result<String, Error>? {
        lock.lock()
        defer { lock.unlock() }
        return result
    }
}

/// MLX-Swift-LM runner for `model-run` — Apple's maintained HF model
/// implementations loaded in-process. Covers the archs our own loader
/// doesn't (MoE, VLM, wider quant table) without shelling to a python
/// install that may or may not be healthy.
///
/// The CLI is synchronous; `loadModel`/`ChatSession.respond` are async.
/// A locked result box bridges them while the main run loop remains live.
public enum MLXRunner {

    public enum RunError: Error, LocalizedError {
        case timedOut
        public var errorDescription: String? { "mlx-swift run timed out" }
    }

    /// Load `id` (auto-downloads to the HF cache; honors HF_TOKEN) and
    /// generate a bounded response. Returns the generated text.
    public static func sample(id: String, revision: String = "main",
                              prompt: String, maxTokens: Int,
                              timeout: TimeInterval = 1800) throws -> String {
        let result = LockedRunResult()
        Task.detached {
            do {
                // HubClient() auto-detects HF_ENDPOINT + reads HF_TOKEN.
                let model = try await loadModel(
                    from: HubDownloader(),
                    using: HuggingFaceTokenizerLoader(),
                    id: id, revision: revision) { progress in
                        fputs("\r    downloading: \(Int(progress.fractionCompleted * 100))%", stderr)
                    }
                fputs("\n", stderr)
                let session = ChatSession(model)
                session.generateParameters = .init(maxTokens: maxTokens)
                result.finish(.success(try await session.respond(to: prompt)))
            } catch {
                result.finish(.failure(error))
            }
        }
        // NOT a semaphore wait — MLXLMCommon hops to the MainActor for
        // parts of load/generate, so the main run loop must keep turning.
        let deadline = Date().addingTimeInterval(timeout)
        while result.snapshot() == nil {
            if Date() > deadline { throw RunError.timedOut }
            RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        return try result.snapshot()!.get()
    }

    /// Interactive chat loop — blocks on stdin until an empty line.
    public static func chat(id: String, revision: String = "main") throws {
        let result = LockedRunResult()
        Task.detached {
            do {
                let model = try await loadModel(
                    from: HubDownloader(),
                    using: HuggingFaceTokenizerLoader(),
                    id: id, revision: revision)
                let session = ChatSession(model)
                print("(mlx-swift chat — empty line to exit)")
                while let line = readLine(strippingNewline: true), !line.isEmpty {
                    let out = try await session.respond(to: line)
                    print(out)
                }
                result.finish(.success(""))
            } catch {
                result.finish(.failure(error))
            }
        }
        while result.snapshot() == nil {
            RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        _ = try result.snapshot()!.get()
    }
}
