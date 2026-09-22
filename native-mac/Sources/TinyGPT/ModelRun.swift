import Foundation
import TinyGPTRun

/// `posttrainllm model-run <hf-url>` — check → pick installed runtime →
/// download → run → verify. The executor half of `model-check` (issues
/// #157 and #161): a check is a prediction, while model-run produces a
/// measured, device-specific receipt from a bounded execution.
///
/// USAGE
///   posttrainllm model-run Qwen/Qwen3-0.6B
///   posttrainllm model-run <gguf-repo> --runtime ollama
///   posttrainllm model-run <url> --chat --prompt "hi" --max-tokens 64
///
/// All execution and receipt logic lives in TinyGPTRun; this file only
/// validates CLI arguments.
enum ModelRun {
    static func run(args: [String]) {
        var input: String? = nil
        var options = ModelRunner.Options()

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--chat":
                options.chat = true; i += 1
            case "--max-tokens":
                guard i + 1 < args.count,
                      let n = Int(args[i + 1]),
                      (1 ... 4096).contains(n) else {
                    fputs("--max-tokens must be 1...4096\n", stderr); exit(2)
                }
                options.maxTokens = n; i += 2
            case "--prompt":
                guard i + 1 < args.count else {
                    fputs("--prompt needs a value\n", stderr); exit(2)
                }
                options.prompt = args[i + 1]; i += 2
            case "--runtime":
                guard i + 1 < args.count else {
                    fputs("--runtime needs a value\n", stderr); exit(2)
                }
                let value = args[i + 1]
                if value == "auto" {
                    options.forcedRunner = nil
                } else if let runner = Runner(rawValue: value) {
                    options.forcedRunner = runner
                } else {
                    fputs("--runtime must be auto|native|mlx-swift|mlx-lm|ollama|lms|llama-cli\n", stderr)
                    exit(2)
                }
                i += 2
            case "-h", "--help":
                printUsage(); exit(0)
            default:
                if args[i].hasPrefix("-") {
                    fputs("unknown flag: \(args[i])\n", stderr); exit(2)
                }
                if input != nil {
                    fputs("model-run takes exactly one model argument\n", stderr); exit(2)
                }
                input = args[i]; i += 1
            }
        }

        guard let target = input else {
            fputs("model-run: a Hugging Face URL or owner/repo is required\n\n", stderr)
            printUsage(); exit(2)
        }
        exit(ModelRunner.run(input: target, options: options))
    }

    private static func printUsage() {
        print("""
        usage: posttrainllm model-run <hf-url-or-owner/repo> [flags]

        Check a Hugging Face model, pick the best installed runtime,
        run a bounded sample, and persist a device-specific receipt.

        Flags:
          --runtime auto|native|mlx-swift|mlx-lm|ollama|lms|llama-cli
          --chat            interactive session instead of the bounded sample
          --prompt "…"      sample prompt
          --max-tokens N    bound the sample (default 32)

        Env:
          HF_TOKEN          needed for gated/private repositories
        """)
    }
}
