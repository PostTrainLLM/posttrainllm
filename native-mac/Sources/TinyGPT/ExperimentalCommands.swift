import Foundation

/// Parked research CLIs. Implementations stay in-tree as learning assets;
/// they are not part of the default factory surface.
///
/// Official path: `posttrainllm experimental <command>`.
/// Hidden top-level aliases still dispatch here so existing scripts keep
/// working; they are omitted from default `--help`.
enum ExperimentalCommands {
    static let names: Set<String> = [
        "rome", "memit", "patch",
        "sae", "sae-explore", "sae-to-saelens", "interp-replay",
        "tuned-lens", "linear-probe", "causal-trace",
        "laser", "gptq", "hqq",
        "prune-unstructured", "prune-structured",
        "magpie", "automix", "compress", "bon", "train-heads",
    ]

    static func run(args: [String]) {
        guard let cmd = args.first else {
            printUsage()
            exit(2)
        }
        if cmd == "-h" || cmd == "--help" {
            printUsage()
            exit(0)
        }
        dispatch(cmd, args: Array(args.dropFirst()))
    }

    static func dispatch(_ cmd: String, args: [String]) {
        switch cmd {
        case "rome":
            ROME.run(args: args)
        case "memit":
            MEMIT.run(args: args)
        case "patch":
            Patch.run(args: args)
        case "sae":
            SAE.run(args: args)
        case "sae-explore":
            SaeExplore.run(args: args)
        case "sae-to-saelens":
            SaeToSaelens.run(args: args)
        case "interp-replay":
            InterpReplay.run(args: args)
        case "tuned-lens":
            TunedLens.run(args: args)
        case "linear-probe":
            LinearProbe.run(args: args)
        case "causal-trace":
            CausalTrace.run(args: args)
        case "laser":
            LASER.run(args: args)
        case "gptq":
            GPTQWorker.run(args: args)
        case "hqq":
            HQQ.run(args: args)
        case "prune-unstructured":
            PruneUnstructured.run(args: args)
        case "prune-structured":
            PruneStructured.run(args: args)
        case "magpie":
            Magpie.run(args: args)
        case "automix":
            AutoMix.run(args: args)
        case "compress":
            Compress.run(args: args)
        case "bon":
            BestOfN.run(args: args)
        case "train-heads":
            TrainHeads.run(args: args)
        case "-h", "--help":
            printUsage()
        default:
            fputs("experimental: unknown command \(cmd)\n\n", stderr)
            printUsage()
            exit(2)
        }
    }

    static func printUsage() {
        print("""
        posttrainllm experimental — parked research CLIs

        The default CLI is the factory loop
        (target -> data -> post-training -> eval -> package -> report).
        These commands stay in-tree as learning assets and are not part of
        that surface. Do not delete the implementations.

        usage:
          posttrainllm experimental <command> [flags]
          posttrainllm experimental --help

        Editing / interpretability:
          rome                 surgical rank-1 fact edit
          memit                batched rank-K fact edit
          patch                activation patching
          sae                  sparse autoencoder on residuals
          sae-explore          inspect a trained .sae sidecar
          sae-to-saelens       export .sae to SAELens layout
          interp-replay        replay probes across checkpoints
          tuned-lens           per-layer logit probes
          linear-probe         train a linear probe on hidden states
          causal-trace         Meng et al. fact localization

        Compression / surgery:
          laser                SVD rank reduction
          gptq                 Hessian-calibrated quantization
          hqq                  half-quadratic quantization
          prune-unstructured   magnitude pruning
          prune-structured     drop heads or layers

        Other experiments:
          magpie               synthetic SFT bootstrap
          automix              pretrain mix search
          compress             extractive context compression
          bon                  best-of-N sampling
          train-heads          Medusa / EAGLE speculative heads

        Hidden top-level aliases (`posttrainllm rome …`) still work so
        existing scripts keep running; they are omitted from default help.
        """)
    }
}
