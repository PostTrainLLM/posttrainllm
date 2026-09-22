import Foundation
import MLXLMCommon
import MLXLLM

private final class LockedRunResult<Value>: @unchecked Sendable {
    private let lock = NSLock()
    private var result: Result<Value, Error>?

    func finish(_ result: Result<Value, Error>) {
        lock.lock()
        defer { lock.unlock() }
        guard self.result == nil else { return }
        self.result = result
    }

    func snapshot() -> Result<Value, Error>? {
        lock.lock()
        defer { lock.unlock() }
        return result
    }
}

/// MLX-Swift-LM runner for `model-run`. The synchronous CLI keeps the
/// main run loop live while the library loads and generates asynchronously.
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

    public static func sample(
        id: String, revision: String = "main", prompt: String,
        maxTokens: Int, timeout: TimeInterval = 1800
    ) throws -> SampleResult {
        let result = LockedRunResult<SampleResult>()
        Task.detached {
            do {
                let model = try await loadModel(
                    from: HubDownloader(),
                    using: HuggingFaceTokenizerLoader(),
                    id: id, revision: revision) { progress in
                        fputs("\r    downloading: \(Int(progress.fractionCompleted * 100))%", stderr)
                    }
                fputs("\n", stderr)
                let session = ChatSession(model)
                session.generateParameters = .init(maxTokens: maxTokens)
                var text = ""
                var promptTokens: Int?
                var generatedTokens: Int?
                var promptMS: Int?
                var generationMS: Int?
                for try await event in session.streamDetails(to: prompt) {
                    if let chunk = event.chunk { text += chunk }
                    if let info = event.info {
                        promptTokens = info.promptTokenCount
                        generatedTokens = info.generationTokenCount
                        promptMS = Int((info.promptTime * 1_000).rounded())
                        generationMS = Int((info.generateTime * 1_000).rounded())
                    }
                }
                result.finish(.success(SampleResult(
                    text: text, promptTokens: promptTokens,
                    generatedTokens: generatedTokens, promptMS: promptMS,
                    generationMS: generationMS)))
            } catch {
                result.finish(.failure(error))
            }
        }
        let deadline = Date().addingTimeInterval(timeout)
        while result.snapshot() == nil {
            if Date() > deadline { throw RunError.timedOut }
            RunLoop.main.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }
        return try result.snapshot()!.get()
    }

    public static func chat(id: String, revision: String = "main") throws {
        let result = LockedRunResult<String>()
        Task.detached {
            do {
                let model = try await loadModel(
                    from: HubDownloader(),
                    using: HuggingFaceTokenizerLoader(),
                    id: id, revision: revision)
                let session = ChatSession(model)
                print("(mlx-swift chat — empty line to exit)")
                while let line = readLine(strippingNewline: true), !line.isEmpty {
                    print(try await session.respond(to: line))
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
