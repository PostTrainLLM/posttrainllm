import Foundation
import TinyGPTIO

// `posttrainllm corrections-to-data` — Phase 2 of the continual-learning loop:
// turn captured corrections into training JSONL ready for `posttrainllm sft`/`dpo`.
// Optional replay mix folds in a sample of the base SFT data to resist
// catastrophic forgetting. See docs/prds/continual-learning-loop.md.
enum CorrectionsToData {

    static func run(args: [String]) {
        var storeDir: String?
        var outPath: String?
        var format: CorrectionCorpusFormat = .sft
        var intentFilter: String?
        var replayPath: String?
        var replayRatio: Double = 0.0

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--store-dir":
                guard i+1 < args.count else { fail("--store-dir requires a value") }
                storeDir = args[i+1]; i += 2
            case "--out":
                guard i+1 < args.count else { fail("--out requires a value") }
                outPath = args[i+1]; i += 2
            case "--format":
                guard i+1 < args.count, let f = CorrectionCorpusFormat(rawValue: args[i+1]) else {
                    fail("--format requires sft|dpo")
                }
                format = f; i += 2
            case "--intent":
                guard i+1 < args.count else { fail("--intent requires a value") }
                intentFilter = args[i+1]; i += 2
            case "--replay":
                guard i+1 < args.count else { fail("--replay requires a path to base SFT jsonl") }
                replayPath = args[i+1]; i += 2
            case "--replay-ratio":
                guard i+1 < args.count, let r = Double(args[i+1]), r >= 0 else {
                    fail("--replay-ratio requires a non-negative number (replay:corrections)")
                }
                replayRatio = r; i += 2
            case "-h", "--help":
                printUsage(); return
            default:
                fputs("unknown arg: \(args[i])\n", stderr); printUsage(); exit(2)
            }
        }

        guard let outPath else { fputs("corrections-to-data requires --out\n", stderr); printUsage(); exit(2) }

        let store = storeDir.map { CorrectionStore(directory: URL(fileURLWithPath: $0)) }
            ?? CorrectionStore(directory: CorrectionStore.defaultDirectory())

        let all: [CorrectionEvent]
        do { all = try store.loadAll() }
        catch { fputs("failed to read store: \(error)\n", stderr); exit(1) }

        let events = intentFilter.map { f in all.filter { $0.intentKind == f } } ?? all
        if events.isEmpty {
            fputs("no corrections to convert in \(store.url.path)\(intentFilter.map { " (intent=\($0))" } ?? "")\n", stderr)
            exit(1)
        }

        let result = CorrectionCurator.curate(events, format: format)
        var lines = result.lines

        // Replay mix: append a stride-sampled subset of the base SFT jsonl so
        // the refresh doesn't forget the base behaviour. Stride (not random)
        // keeps it deterministic + spread across the file. Only valid for SFT
        // output (same row shape).
        var replayAdded = 0
        if let replayPath, replayRatio > 0 {
            if format != .sft {
                fputs("warning: --replay is only applied to --format sft; ignoring for \(format.rawValue)\n", stderr)
            } else {
                let base = (try? String(contentsOfFile: replayPath, encoding: .utf8))?
                    .split(separator: "\n", omittingEmptySubsequences: true)
                    .map(String.init) ?? []
                let want = min(base.count, Int((Double(result.emitted) * replayRatio).rounded()))
                if want > 0 {
                    let stride = max(1, base.count / want)
                    var picked: [String] = []
                    var idx = 0
                    while idx < base.count && picked.count < want { picked.append(base[idx]); idx += stride }
                    lines.append(contentsOf: picked)
                    replayAdded = picked.count
                }
            }
        }

        // Fail loudly rather than write a blank-line file that would feed the
        // trainer as 0 records silently. All-skipped means no correction had
        // an `input` to ground a pair (and no replay rows were added).
        if lines.isEmpty {
            fputs("corrections-to-data: nothing to write — \(result.emitted) emitted, \(result.skipped) skipped (no `input`), \(replayAdded) replay. Not writing \(outPath).\n", stderr)
            exit(1)
        }

        do {
            try lines.joined(separator: "\n").appending("\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        } catch {
            fputs("failed to write \(outPath): \(error)\n", stderr); exit(1)
        }

        print("""
        corrections-to-data (\(format.rawValue)):
          input events:   \(events.count)\(intentFilter.map { " (intent=\($0))" } ?? "")
          emitted pairs:   \(result.emitted)
          skipped (no input / no signal): \(result.skipped)
          replay rows added: \(replayAdded)
          → \(outPath)  (\(lines.count) rows)
        """)
    }

    private static func fail(_ msg: String) -> Never {
        fputs("\(msg)\n", stderr); exit(2)
    }

    private static func printUsage() {
        print("""
        usage: posttrainllm corrections-to-data --out <data.jsonl> [options]

        Convert captured corrections (Phase 1 store) into training JSONL for
        `posttrainllm sft` (default) or `posttrainllm dpo`. Only corrections that carry an
        `input` produce a grounded pair; the rest are skipped and reported.

        --out <file>         output JSONL  (required)
        --store-dir <dir>    correction store (default: ~/.tinygpt/corrections)
        --format sft|dpo     sft: messages[user=input, assistant=corrected];
                             dpo: prompt=input, chosen=corrected, rejected=original
                             (default: sft)
        --intent <kind>      only convert corrections with this intent label
        --replay <base.jsonl>      mix in base SFT rows (sft only) to resist forgetting
        --replay-ratio <r>   replay:corrections ratio (e.g. 1.0 = equal count)
        """)
    }
}
