import Foundation
import TinyGPTRun

/// `posttrainllm model-run <hf-url>` — check → pick installed runtime →
/// download → run → verify. The executor half of `model-check` (issue
/// #157): the checker's verdict is a prediction, model-run turns it into
/// measured evidence with a real load + bounded sample, then prints the
/// command that keeps the session going.
///
/// USAGE
///   posttrainllm model-run Qwen/Qwen3-0.6B
///   posttrainllm model-run <gguf-repo> --runtime ollama
///   posttrainllm model-run <url> --chat --prompt "hi" --max-tokens 64
///
/// FLAGS
///   --runtime auto|native|mlx-lm|ollama|lms|llama-cli   force one runner (default auto)
///   --chat             hand the terminal to the runtime's interactive session
///   --prompt "…"       sample prompt (default: a one-sentence hello)
///   --max-tokens N     bound the sample (default 32)
///
/// Runner choice (auto): safetensors + checked-path-OK → native hf-load;
/// GGUF → ollama, else lms; other safetensors → mlx-lm. Gated repos
/// without HF_TOKEN stop with the named fix. All logic lives in the
/// TinyGPTRun library; this file only parses arguments.
///
/// ENV
///   HF_TOKEN           required for gated/private repositories
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
                guard i + 1 < args.count, let n = Int(args[i + 1]) else {
                    fputs("--max-tokens needs an int\n", stderr); exit(2)
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
                } else if let r = Runner(rawValue: value) {
                    options.forcedRunner = r
                } else {
                    fputs("--runtime must be auto|native|mlx-lm|ollama|lms|llama-cli\n", stderr)
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
        download it, run a bounded sample, and print the command that
        keeps the session going. The verification is measured (a real
        load), not predicted — failed runners surface their real error
        and fall through to the next installed candidate.

        Flags:
          --runtime auto|native|mlx-lm|ollama|lms|llama-cli   force one runner
          --chat            interactive session instead of the bounded sample
          --prompt "…"      sample prompt
          --max-tokens N    bound the sample (default 32)

        Env:
          HF_TOKEN          needed for gated/private repositories
        """)
    }
}
