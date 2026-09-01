import Foundation

/// Parked research CLIs. Implementations stay in-tree as learning assets;
/// they are not part of the default factory surface.
///
/// Official path: `posttrainllm experimental <command>`.
/// Hidden top-level aliases still dispatch here so existing scripts keep
/// working; they are omitted from default `--help`.
enum ExperimentalCommands {
    static var names: Set<String> { Set(runners.keys) }

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

    private static let runners: [String: ([String]) -> Void] = [
        "rome": { ROME.run(args: $0) },
        "memit": { MEMIT.run(args: $0) },
        "patch": { Patch.run(args: $0) },
        "sae": { SAE.run(args: $0) },
        "sae-explore": { SaeExplore.run(args: $0) },
        "sae-to-saelens": { SaeToSaelens.run(args: $0) },
        "interp-replay": { InterpReplay.run(args: $0) },
        "tuned-lens": { TunedLens.run(args: $0) },
        "linear-probe": { LinearProbe.run(args: $0) },
        "causal-trace": { CausalTrace.run(args: $0) },
        "laser": { LASER.run(args: $0) },
        "gptq": { GPTQWorker.run(args: $0) },
        "hqq": { HQQ.run(args: $0) },
        "prune-unstructured": { PruneUnstructured.run(args: $0) },
        "prune-structured": { PruneStructured.run(args: $0) },
        "magpie": { Magpie.run(args: $0) },
        "automix": { AutoMix.run(args: $0) },
        "compress": { Compress.run(args: $0) },
        "bon": { BestOfN.run(args: $0) },
        "train-heads": { TrainHeads.run(args: $0) },
    ]

    static func dispatch(_ cmd: String, args: [String]) {
        if cmd == "-h" || cmd == "--help" {
            printUsage()
            return
        }
        guard let run = runners[cmd] else {
            fputs("experimental: unknown command \(cmd)\n\n", stderr)
            printUsage()
            exit(2)
        }
        run(args)
    }

    static func printUsage() {
        print("""
        posttrainllm experimental — parked research CLIs

        The retained CLI centers the factory loop
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
