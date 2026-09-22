import Foundation

private struct SampleStats: Encodable {
    let promptTokens: Int?
    let generatedTokens: Int?
    let promptMS: Int?
    let generationMS: Int?

    enum CodingKeys: String, CodingKey {
        case promptTokens = "prompt_tokens"
        case generatedTokens = "generated_tokens"
        case promptMS = "prompt_ms"
        case generationMS = "generation_ms"
    }
}

/// `posttrainllm-mlxrun` — sibling executable invoked by
/// `posttrainllm model-run` for the MLX-Swift-LM runner. Lives in its
/// own process so a model load failure or a runtime quirk is a captured
/// subprocess result, not a crash of the orchestrating CLI.
///
/// usage: posttrainllm-mlxrun <model-id> [--prompt "…"] [--max-tokens N] [--chat]
var id: String? = nil
var prompt = "Say hello in one sentence."
var maxTokens = 32
var chat = false
var revision = "main"
var i = 1
let argv = CommandLine.arguments
while i < argv.count {
    switch argv[i] {
    case "--prompt":
        guard i + 1 < argv.count else {
            fputs("mlxrun: --prompt needs a value\n", stderr); exit(2)
        }
        prompt = argv[i + 1]; i += 2
    case "--max-tokens":
        guard i + 1 < argv.count,
              let n = Int(argv[i + 1]),
              (1 ... 4096).contains(n) else {
            fputs("mlxrun: --max-tokens must be 1...4096\n", stderr); exit(2)
        }
        maxTokens = n; i += 2
    case "--chat":       chat = true; i += 1
    case "--revision":
        guard i + 1 < argv.count, !argv[i + 1].isEmpty else {
            fputs("mlxrun: --revision needs a value\n", stderr); exit(2)
        }
        revision = argv[i + 1]; i += 2
    default:
        if argv[i].hasPrefix("-") {
            fputs("mlxrun: unknown flag \(argv[i])\n", stderr); exit(2)
        }
        guard id == nil else {
            fputs("mlxrun: expected exactly one <model-id>\n", stderr); exit(2)
        }
        id = argv[i]; i += 1
    }
}
guard let id else { fputs("mlxrun: missing <model-id>\n", stderr); exit(2) }

do {
    if chat {
        try MLXRunner.chat(id: id, revision: revision)
    } else {
        let sample = try MLXRunner.sample(
            id: id, revision: revision, prompt: prompt, maxTokens: maxTokens)
        print(sample.text)
        let stats = SampleStats(
            promptTokens: sample.promptTokens,
            generatedTokens: sample.generatedTokens,
            promptMS: sample.promptMS,
            generationMS: sample.generationMS)
        if let data = try? JSONEncoder().encode(stats),
           let json = String(data: data, encoding: .utf8) {
            fputs("__POSTTRAINLLM_SAMPLE_STATS__\(json)\n", stderr)
        }
    }
} catch {
    fputs("mlxrun failed: \(error)\n", stderr)
    exit(1)
}
