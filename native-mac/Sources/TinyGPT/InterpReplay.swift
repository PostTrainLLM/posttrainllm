import Foundation
import TinyGPTModel

/// `tinygpt interp-replay <history-dir>` (B13) — replay an interp probe across
/// a training run's saved checkpoints, emitting one timeline JSONL row per
/// (probe, layer, checkpoint) in the shared schema the `/sae-timeline.astro`
/// viewer consumes. `--dry-run` emits a deterministic synthetic metric per
/// checkpoint so the walk + schema + merge are CI-verifiable without loading
/// models; real probe execution (SAE/MEMIT/…) is the per-checkpoint heavy step
/// (the SAE slice already ships as `sae --checkpoint-dir`).
enum InterpReplay {
    static func run(args: [String]) {
        var historyDir: String?, outPath = "timeline.jsonl", probe = "sae", layersSpec = "0"
        var dryRun = false
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--probe":  probe = args[i+1]; i += 2
            case "--layers": layersSpec = args[i+1]; i += 2
            case "--out":    outPath = args[i+1]; i += 2
            case "--dry-run": dryRun = true; i += 1
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                historyDir = args[i]; i += 1
            }
        }
        guard let historyDir = historyDir else { fputs("missing <history-dir>\n", stderr); exitUsage() }
        let layers = layersSpec.split(separator: ",").compactMap { Int($0) }
        guard !layers.isEmpty else { fputs("--layers must be a comma list, e.g. 0,4,8\n", stderr); exitUsage() }

        let fm = FileManager.default
        guard let names = try? fm.contentsOfDirectory(atPath: historyDir) else {
            fputs("could not list \(historyDir)\n", stderr); exit(1)
        }
        let ckpts = CheckpointBatchLoader.ordered(names.filter { $0.hasSuffix(".tinygpt") })
        guard !ckpts.isEmpty else { fputs("no step-N checkpoints (*.step-N.tinygpt) in \(historyDir)\n", stderr); exit(1) }

        if !dryRun {
            fputs("note: V1 interp-replay only implements --dry-run (schema/orchestration); for real SAE timelines use `tinygpt sae --checkpoint-dir`. Emitting dry-run rows.\n", stderr)
        }
        let outURL = URL(fileURLWithPath: outPath)
        try? fm.removeItem(at: outURL); fm.createFile(atPath: outURL.path, contents: nil)
        let fh = try? FileHandle(forWritingTo: outURL); defer { try? fh?.close() }

        var rows = 0
        for c in ckpts {
            let hash = String(UInt64(abs(c.file.hashValue)) % 0xFFFFFF, radix: 16)
            for layer in layers {
                // dry-run synthetic metric: a smooth, deterministic curve in
                // (step, layer) so the viewer renders something sensible.
                let value = 1.0 / (1.0 + Double(c.step) / 1000.0) + Double(layer) * 0.01
                let row: [String: Any] = ["step": c.step, "ckpt_hash": hash, "probe": probe,
                                          "layer": layer, "metric": probe == "sae" ? "mse" : "metric",
                                          "value": value, "extra": ["dry_run": true]]
                if let d = try? JSONSerialization.data(withJSONObject: row),
                   let line = String(data: d, encoding: .utf8) {
                    fh?.write(Data((line + "\n").utf8)); rows += 1
                }
            }
        }
        print("interp-replay: \(ckpts.count) checkpoints × \(layers.count) layers → \(rows) rows in \(outPath)")
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt interp-replay <history-dir> --probe sae --layers 0,4,8 \\
                                     --out timeline.jsonl [--dry-run]

        Replay an interp probe across a run's *.step-N.tinygpt checkpoints,
        emitting timeline rows {step, ckpt_hash, probe, layer, metric, value,
        extra} for /sae-timeline.astro. V1 implements --dry-run (synthetic
        metric — verifies the walk + schema); for real SAE timelines use
        `tinygpt sae --checkpoint-dir`.
        """)
        exit(code)
    }
}
