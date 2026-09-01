import Foundation

/// Stable, side-effect-free discovery metadata for the CLI.
///
/// Keep this catalog in step with the dispatch table in `TinyGPT.swift` and
/// the parked runners in `ExperimentalCommands.swift`. The repository-level
/// CLI surface smoke test enforces that contract without loading a model.
enum CLICommandCatalog {
    static let version = "0.1.0"

    enum Category: String, CaseIterable, Codable {
        case start = "Start here"
        case data = "Data"
        case postTraining = "Post-training"
        case evaluation = "Evaluation"
        case packaging = "Models and packaging"
        case runtime = "Inference and runtime"
        case platform = "Mac platform"
        case diagnostics = "Diagnostics"
        case research = "Parked research"
        case compatibility = "Compatibility"
    }

    enum Status: String, Codable {
        case retained
        case supporting
        case diagnostic
        case experimental
        case deprecated
    }

    struct Command: Codable {
        let name: String
        let category: Category
        let summary: String
        let status: Status
        let invocation: String

        init(_ name: String, _ category: Category, _ summary: String, _ status: Status = .supporting) {
            self.name = name
            self.category = category
            self.summary = summary
            self.status = status
            invocation = "posttrainllm \(name)"
        }
    }

    private struct JSONCatalog: Codable {
        let schemaVersion: Int
        let cliVersion: String
        let labLoop: [String]
        let commands: [Command]

        enum CodingKeys: String, CodingKey {
            case schemaVersion = "schema_version"
            case cliVersion = "cli_version"
            case labLoop = "lab_loop"
            case commands
        }
    }

    // This is intentionally explicit: the catalog is a user-facing contract,
    // while the dispatch switch remains the executable contract. A static
    // validator compares the two so neither can drift silently.
    private static func startCommands() -> [Command] {
        [
        Command("quickstart", .start, "Inspect a dataset and resolve a safe first specialist recipe.", .retained),
        Command("factory-run", .start, "Create, validate, inspect, and transition reproducible factory runs.", .retained),
        Command("train", .start, "Train a tiny language model from scratch.", .retained),
        Command("commands", .start, "List the complete CLI surface; add --json for tooling.", .retained),
        Command("help", .start, "Show the overview or side-effect-free help for one command.", .retained),
        Command("version", .start, "Print the CLI version.", .retained),
        ]
    }

    private static func dataCommands() -> [Command] {
        [
        Command("download-dataset", .data, "Download a supported dataset and convert it for local use."),
        Command("list-datasets", .data, "List the built-in dataset registry."),
        Command("fetch-github", .data, "Fetch repository text into a bounded local corpus."),
        Command("prep-data", .data, "Prepare local source data for training."),
        Command("dedupe", .data, "Remove exact and near-duplicate training examples."),
        Command("filter", .data, "Filter and normalize JSONL training rows."),
        Command("tokenize-train", .data, "Train a tokenizer from a local corpus."),
        Command("synthesize", .data, "Generate supervised rows from a teacher endpoint."),
        Command("train-quality-classifier", .data, "Train a lightweight data-quality classifier."),
        Command("quality-filter", .data, "Apply a trained quality classifier to a corpus."),
        Command("build-escalate-data", .data, "Convert escalation traces into supervised data."),
        Command("reasoning-classify", .data, "Train or apply the reasoning-complexity classifier."),
        Command("traces-to-data", .data, "Convert retained agent trajectories into training rows."),
        Command("record-correction", .data, "Record one correction in the local feedback ledger."),
        Command("corrections-to-data", .data, "Compile recorded corrections into a training dataset."),
        Command("extractor-data", .data, "Build structured-extraction training data."),
        ]
    }

    private static func postTrainingCommands() -> [Command] {
        [
        Command("sft", .postTraining, "Supervised fine-tune a base model with LoRA.", .retained),
        Command("dpo", .postTraining, "Run direct preference optimization.", .retained),
        Command("distill", .postTraining, "Distill a teacher into a smaller local student.", .retained),
        Command("finetune", .postTraining, "Fine-tune a native .tinygpt model with an adapter.", .retained),
        Command("es", .postTraining, "Run the evolution-strategy training experiment."),
        Command("rerank-train", .postTraining, "Train a compact reranking model."),
        Command("train-extractor", .postTraining, "Train the structured-extraction specialist."),
        ]
    }

    private static func evaluationCommands() -> [Command] {
        [
        Command("eval", .evaluation, "Evaluate loss or perplexity on a local corpus.", .retained),
        Command("eval-gate", .evaluation, "Apply a frozen regression gate against a baseline.", .retained),
        Command("eval-compare", .evaluation, "Compare normalized E0 result rows."),
        Command("run-bench", .evaluation, "Run the retained benchmark driver."),
        Command("eval-bfcl", .evaluation, "Evaluate function calling with the BFCL-compatible harness."),
        Command("eval-tau-bench", .evaluation, "Evaluate multi-turn tool use with the tau-bench harness."),
        Command("eval-humaneval", .evaluation, "Evaluate code generation with HumanEval."),
        Command("run-lm-eval", .evaluation, "Run selected lm-evaluation-harness tasks."),
        Command("eval-mteb", .evaluation, "Evaluate an embedding model on selected MTEB tasks."),
        Command("eval-indic", .evaluation, "Run MILU or IndicGenBench evaluation."),
        Command("eval-milu", .evaluation, "Normalize MILU predictions into E0 rows."),
        Command("eval-sql", .evaluation, "Score SQL predictions against local databases."),
        Command("eval-router", .evaluation, "Score routing predictions."),
        Command("eval-review", .evaluation, "Normalize review results into E0 rows."),
        Command("eval-escalate", .evaluation, "Score escalation-policy predictions."),
        Command("eval-scaledown", .evaluation, "Measure retained quality under scale-down policies."),
        Command("rerank-eval", .evaluation, "Evaluate a trained reranker."),
        Command("judge", .evaluation, "Apply a local judge model to JSONL predictions."),
        Command("compare", .evaluation, "Compare a base model and adapter on the same prompts."),
        ]
    }

    private static func packagingCommands() -> [Command] {
        [
        Command("inspect", .packaging, "Print a .tinygpt file manifest and tensor inventory.", .retained),
        Command("validate", .packaging, "Round-trip validate a .tinygpt artifact.", .retained),
        Command("validate-project", .packaging, "Validate a pinned posttrainllm project file."),
        Command("merge", .packaging, "Merge compatible checkpoints or adapters.", .retained),
        Command("bake-lora", .packaging, "Fold a LoRA adapter into base safetensors.", .retained),
        Command("export-mlx", .packaging, "Package a model or adapter for MLX consumers.", .retained),
        Command("to-safetensors", .packaging, "Convert .tinygpt weights to safetensors."),
        Command("to-coreml", .packaging, "Generate the Core ML conversion handoff."),
        Command("gguf-inspect", .packaging, "Inspect GGUF metadata and tensor layout."),
        Command("gguf-load", .packaging, "Load and validate a GGUF model."),
        Command("gguf-extract", .packaging, "Extract GGUF tensors into a local directory."),
        Command("hf-inspect", .packaging, "Inspect a local Hugging Face model directory."),
        Command("hf-load", .packaging, "Load a Hugging Face model through the native runtime."),
        ]
    }

    private static func runtimeCommands() -> [Command] {
        [
        Command("generate", .runtime, "Generate predictions for JSONL inputs."),
        Command("sample", .runtime, "Sample text from a local model."),
        Command("serve", .runtime, "Serve a model through an OpenAI-compatible local endpoint."),
        Command("agent", .runtime, "Run the multi-turn local tool-using agent."),
        Command("extract", .runtime, "Run the structured-extraction specialist."),
        Command("escalate", .runtime, "Send an explicitly requested prompt to a configured cloud provider."),
        Command("push", .runtime, "Push a local artifact to the configured model store."),
        Command("pull", .runtime, "Pull an artifact from the configured model store."),
        Command("cloud", .runtime, "Inspect configured cloud artifact state."),
        ]
    }

    private static func platformCommands() -> [Command] {
        [
        Command("screen", .platform, "Capture a Mac window, accessibility tree, or both."),
        Command("ax-capture", .platform, "Capture the macOS accessibility tree."),
        Command("coreml-serve", .platform, "Serve a stateful Core ML package locally."),
        Command("coreml-chunked-smoke", .platform, "Run one bounded chunked Core ML smoke."),
        Command("ane-validate", .platform, "Compare MLX and Core ML outputs for ANE conversion."),
        Command("ane-bench-smoke", .platform, "Run one bounded ANE decode-rate smoke."),
        Command("vlm-smoke", .platform, "Run the parked vision-encoder load and forward smoke."),
        ]
    }

    private static func diagnosticCommands() -> [Command] {
        [
        Command("bench", .diagnostics, "Measure inference latency and throughput.", .diagnostic),
        Command("bench-train", .diagnostics, "Measure native training throughput.", .diagnostic),
        Command("infer-heatmap", .diagnostics, "Render inference traces as a heatmap.", .diagnostic),
        Command("debug-names", .diagnostics, "Inspect checkpoint tensor names.", .diagnostic),
        Command("debug-load", .diagnostics, "Compare loaded checkpoint tensors.", .diagnostic),
        Command("debug-logits", .diagnostics, "Inspect logits for a checkpoint.", .diagnostic),
        Command("debug-dtypes", .diagnostics, "Inspect checkpoint dtypes.", .diagnostic),
        Command("debug-loss", .diagnostics, "Run a loss sanity check.", .diagnostic),
        ]
    }

    private static func researchCommands() -> [Command] {
        [
        Command("experimental", .research, "List parked research commands kept as learning assets.", .experimental),
        Command("experimental rome", .research, "Apply a surgical rank-one fact edit.", .experimental),
        Command("experimental memit", .research, "Apply batched rank-K fact edits.", .experimental),
        Command("experimental patch", .research, "Run activation patching.", .experimental),
        Command("experimental sae", .research, "Train a sparse autoencoder on residual activations.", .experimental),
        Command("experimental sae-explore", .research, "Inspect a trained sparse-autoencoder sidecar.", .experimental),
        Command("experimental sae-to-saelens", .research, "Export a sparse autoencoder to SAELens layout.", .experimental),
        Command("experimental interp-replay", .research, "Replay probes across saved checkpoints.", .experimental),
        Command("experimental tuned-lens", .research, "Train or inspect per-layer logit probes.", .experimental),
        Command("experimental linear-probe", .research, "Train a linear probe on hidden states.", .experimental),
        Command("experimental causal-trace", .research, "Localize factual recall with causal tracing.", .experimental),
        Command("experimental laser", .research, "Apply SVD rank reduction to selected weights.", .experimental),
        Command("experimental gptq", .research, "Run Hessian-calibrated quantization.", .experimental),
        Command("experimental hqq", .research, "Run half-quadratic quantization.", .experimental),
        Command("experimental prune-unstructured", .research, "Apply unstructured magnitude pruning.", .experimental),
        Command("experimental prune-structured", .research, "Drop selected heads or layers.", .experimental),
        Command("experimental magpie", .research, "Bootstrap synthetic supervised data.", .experimental),
        Command("experimental automix", .research, "Search pretraining-corpus mixtures.", .experimental),
        Command("experimental compress", .research, "Run extractive context compression.", .experimental),
        Command("experimental bon", .research, "Run best-of-N sampling.", .experimental),
        Command("experimental train-heads", .research, "Train Medusa or EAGLE speculative heads.", .experimental),
        ]
    }

    private static func compatibilityCommands() -> [Command] {
        [
            Command("score-bench", .compatibility, "Deprecated alias for run-bench.", .deprecated),
        ]
    }

    static let commands = startCommands() + dataCommands() + postTrainingCommands()
        + evaluationCommands() + packagingCommands() + runtimeCommands()
        + platformCommands() + diagnosticCommands() + researchCommands()
        + compatibilityCommands()

    /// Handle metadata-only commands before the model command switch. Success
    /// exits here, which keeps discovery from increasing the already-large
    /// compatibility dispatcher's branch count.
    static func runDiscoveryIfRequested(args: [String]) {
        guard let command = args.first else { return }
        let remaining = Array(args.dropFirst())
        switch command {
        case "commands":
            runCommands(args: remaining)
            exit(0)
        case "help":
            runHelp(args: remaining)
            exit(0)
        case "version", "--version":
            guard remaining.isEmpty else {
                fputs("version: unexpected arguments\n", stderr)
                exit(2)
            }
            print("posttrainllm \(version)")
            exit(0)
        default:
            return
        }
    }

    static func runCommands(args: [String]) {
        if args.isEmpty {
            printCatalog()
            return
        }
        if args == ["--json"] {
            printJSON()
            return
        }
        if args == ["-h"] || args == ["--help"] {
            print("usage: posttrainllm commands [--json]\n  Lists every supported command without loading a model.")
            return
        }
        fputs("commands: expected no arguments or --json\n", stderr)
        exit(2)
    }

    static func runHelp(args: [String]) {
        guard !args.isEmpty else {
            printOverview()
            return
        }
        if args == ["-h"] || args == ["--help"] {
            print("usage: posttrainllm help [command]\n  Shows side-effect-free command discovery.")
            return
        }

        let requested = args.joined(separator: " ")
        guard let command = commands.first(where: { $0.name == requested }) else {
            fputs("help: unknown command \(requested)\n", stderr)
            fputs("Run `posttrainllm commands` for the complete catalog.\n", stderr)
            exit(2)
        }

        print("\(command.invocation) — \(command.summary)")
        print("category: \(command.category.rawValue)")
        print("status:   \(command.status.rawValue)")
        if command.name == "experimental" {
            print("\nRun `posttrainllm experimental --help` for the parked command groups.")
        } else if command.name.hasPrefix("experimental ") {
            print("\nusage: \(command.invocation) [arguments]")
            print("The historical top-level alias remains compatible but is intentionally hidden.")
        } else {
            print("\nusage: \(command.invocation) [arguments]")
            print("Run `\(command.invocation) --help` for command-specific flags when available.")
        }
    }

    static func printOverview() {
        print("""
        posttrainllm — Mac-local specialist learning lab

        Retained lab loop: target -> data -> post-training -> eval -> package -> report

        usage:
          posttrainllm quickstart <data>  inspect data and resolve a first recipe
          posttrainllm factory-run <sub> manage a reproducible run lifecycle
          posttrainllm train [flags]      train from scratch
          posttrainllm sft [flags]        supervised fine-tune with LoRA
          posttrainllm dpo [flags]        preference post-training
          posttrainllm distill [flags]    distill a local student
          posttrainllm eval-gate [flags]  frozen-suite gate vs a baseline
          posttrainllm export-mlx <model> package a model for MLX
          posttrainllm commands           list every supported command
          posttrainllm commands --json    emit the catalog for tooling
          posttrainllm help <command>     inspect one command without running it
          posttrainllm --version          print the CLI version

        The complete lab includes supporting data, eval, packaging, runtime,
        Mac-platform, and diagnostic commands. Use `posttrainllm commands` to
        discover them. Parked research commands remain under `experimental`.

        Factory contract: docs/factory/run-schema.md
        Learning paths:  docs/learn/path-registry.json
        """)
    }

    private static func printCatalog() {
        print("posttrainllm \(version) — complete command catalog")
        print("Retained lab loop: target -> data -> post-training -> eval -> package -> report")
        for category in Category.allCases {
            let matches = commands.filter { $0.category == category }
            guard !matches.isEmpty else { continue }
            print("\n\(category.rawValue):")
            let width = matches.map(\.name.count).max() ?? 0
            for command in matches {
                let padding = String(repeating: " ", count: width - command.name.count)
                print("  \(command.name)\(padding)  \(command.summary) [\(command.status.rawValue)]")
            }
        }
        print("\nUse `posttrainllm help <command>` for a side-effect-free summary.")
    }

    private static func printJSON() {
        let payload = JSONCatalog(
            schemaVersion: 1,
            cliVersion: version,
            labLoop: ["target", "data", "post-training", "eval", "package", "report"],
            commands: commands
        )
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        do {
            let data = try encoder.encode(payload)
            print(String(decoding: data, as: UTF8.self))
        } catch {
            fputs("commands: could not encode catalog: \(error)\n", stderr)
            exit(1)
        }
    }
}
