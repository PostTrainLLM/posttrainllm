import Foundation
import TinyGPTIO

// `posttrainllm record-correction` — Phase 1 of the on-device continual-learning
// loop: ingest a user correction into the local append-only store. No model,
// no training; this only captures the signal. Clients (serve/agent/Pace) can
// call this, or it can be driven by hand for testing.
// See docs/prds/continual-learning-loop.md.
enum RecordCorrection {

    static func run(args: [String]) {
        var intent: String?
        var input: String?
        var original: String?
        var corrected: String?
        var model: String?
        var source = "cli"
        var storeDir: String?
        var listOnly = false

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--intent":
                guard i+1 < args.count else { fail("--intent requires a value") }
                intent = args[i+1]; i += 2
            case "--input":
                guard i+1 < args.count else { fail("--input requires a value") }
                input = args[i+1]; i += 2
            case "--original":
                guard i+1 < args.count else { fail("--original requires a value") }
                original = args[i+1]; i += 2
            case "--corrected":
                guard i+1 < args.count else { fail("--corrected requires a value") }
                corrected = args[i+1]; i += 2
            case "--model":
                guard i+1 < args.count else { fail("--model requires a value") }
                model = args[i+1]; i += 2
            case "--source":
                guard i+1 < args.count else { fail("--source requires a value") }
                source = args[i+1]; i += 2
            case "--store-dir":
                guard i+1 < args.count else { fail("--store-dir requires a value") }
                storeDir = args[i+1]; i += 2
            case "--list":
                listOnly = true; i += 1
            case "-h", "--help":
                printUsage(); return
            default:
                fputs("unknown arg: \(args[i])\n", stderr); printUsage(); exit(2)
            }
        }

        let store = storeDir.map { CorrectionStore(directory: URL(fileURLWithPath: $0)) }
            ?? CorrectionStore(directory: CorrectionStore.defaultDirectory())

        if listOnly {
            do {
                let events = try store.loadAll()
                print("\(events.count) correction(s) in \(store.url.path)")
                for e in events.suffix(10) {
                    let when = ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: e.timestamp))
                    print("  [\(e.intentKind)] \(when)  \(snippet(e.original)) → \(snippet(e.corrected))")
                }
            } catch {
                fputs("failed to read store: \(error)\n", stderr); exit(1)
            }
            return
        }

        guard let intent, let original, let corrected else {
            fputs("record-correction requires --intent, --original, and --corrected\n", stderr)
            printUsage(); exit(2)
        }

        let event = CorrectionEvent(intentKind: intent, input: input,
                                    original: original, corrected: corrected,
                                    modelFingerprint: model, source: source)
        do {
            try store.append(event)
            print("recorded correction \(event.id) → \(store.url.path)")
        } catch {
            fputs("failed to record correction: \(error)\n", stderr); exit(1)
        }
    }

    private static func snippet(_ s: String, _ n: Int = 32) -> String {
        let one = s.replacingOccurrences(of: "\n", with: " ")
        return one.count <= n ? one : String(one.prefix(n)) + "…"
    }

    private static func fail(_ msg: String) -> Never {
        fputs("\(msg)\n", stderr); exit(2)
    }

    private static func printUsage() {
        print("""
        usage: posttrainllm record-correction --intent <kind> --original <text> --corrected <text> [options]
               posttrainllm record-correction --list

        Capture a user correction into the local continual-learning store
        (Phase 1: capture only — no training). Defaults to ~/.tinygpt/corrections.

        --intent <kind>     intent label: dictation | tool_call | action | …  (required)
        --original <text>   the model output that was corrected  (required)
        --corrected <text>  the user's corrected version  (required)
        --input <text>      the prompt/context that produced the output  (optional)
        --model <id>        which model produced the original  (optional)
        --source <name>     provenance (default: cli)
        --store-dir <path>  store directory (default: ~/.tinygpt/corrections)
        --list              print the stored events instead of recording
        """)
    }
}
