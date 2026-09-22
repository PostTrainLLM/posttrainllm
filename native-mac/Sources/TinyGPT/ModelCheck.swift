import Foundation
import TinyGPTCheck

/// `posttrainllm model-check <hf-url-or-owner/repo> [--json]` — report
/// whether a Hugging Face model can run on this Mac, without touching
/// the machine.
///
/// Read-only: fetches Hub metadata and small config files, probes local
/// environment + runtime versions, and emits a structured verdict
/// (expected_to_work / changes_required / unsupported_on_checked_path /
/// unknown) plus a copy-ready agent prompt for cases it can't close.
/// Never downloads weights, installs, converts, or executes anything.
///
/// FLAGS
///   <url-or-id>          huggingface.co model URL or owner/repo (positional)
///   --json               emit the machine-readable report (same schema the
///                        app renders) instead of the text rendering
///   --chip <name>        check against a different Mac's chip
///   --ram-gb <n>         check against a different Mac's RAM
///   --disk-gb <n>        check against a different Mac's free disk
///   --macos <ver>        check against a different macOS version
///
/// Manual environment flags mark the report `environment.source: manual` —
/// the machine doing the checking is never confused with the target.
///
/// EXAMPLES
///   posttrainllm model-check https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
///   posttrainllm model-check Qwen/Qwen3-0.6B --json
///   posttrainllm model-check black-forest-labs/FLUX.1-dev --ram-gb 16
///
/// ENV
///   HF_TOKEN             optional; required to inspect gated/private repos
enum ModelCheck {

    static func run(args: [String]) {
        var input: String? = nil
        var json = false
        var chip: String? = nil
        var ramGB: Int? = nil
        var diskGB: Int? = nil
        var macOS: String? = nil

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--json": json = true; i += 1
            case "--chip":
                guard i+1 < args.count else { fputs("--chip needs value\n", stderr); exit(2) }
                chip = args[i+1]; i += 2
            case "--ram-gb":
                guard i+1 < args.count, let n = Int(args[i+1]) else { fputs("--ram-gb needs int\n", stderr); exit(2) }
                ramGB = n; i += 2
            case "--disk-gb":
                guard i+1 < args.count, let n = Int(args[i+1]) else { fputs("--disk-gb needs int\n", stderr); exit(2) }
                diskGB = n; i += 2
            case "--macos":
                guard i+1 < args.count else { fputs("--macos needs value\n", stderr); exit(2) }
                macOS = args[i+1]; i += 2
            case "-h", "--help":
                printUsage(); exit(0)
            default:
                if args[i].hasPrefix("-") {
                    fputs("unknown flag: \(args[i])\n", stderr); exit(2)
                }
                if input != nil {
                    fputs("model-check takes exactly one model argument\n", stderr); exit(2)
                }
                input = args[i]; i += 1
            }
        }

        guard let target = input else {
            fputs("model-check: a Hugging Face URL or owner/repo is required\n\n", stderr)
            printUsage(); exit(2)
        }

        let envOverride: MacEnvironment? =
            (chip != nil || ramGB != nil || diskGB != nil || macOS != nil)
            ? .manual(chip: chip, ramGB: ramGB, diskGB: diskGB, macOS: macOS)
            : nil

        do {
            let report = try ModelCheckService.check(
                input: target, environment: envOverride
            ) { stage in
                // Progress to stderr so --json stdout stays a clean report.
                fputs("… \(stage.rawValue)\n", stderr)
            }
            if json {
                print(try report.encoded())
            } else {
                print(report.renderText())
            }
        } catch let e as ModelCheckService.CheckError {
            fputs("model-check: \(e)\n", stderr)
            exit(2)
        } catch {
            fputs("model-check failed: \(error)\n", stderr)
            exit(1)
        }
    }

    private static func printUsage() {
        print("""
        usage: posttrainllm model-check <hf-url-or-owner/repo> [--json]

        Check whether a Hugging Face model can run on this Mac. Read-only:
        fetches Hub metadata + config.json, probes the local environment,
        and reports a verdict — expected_to_work / changes_required /
        unsupported_on_checked_path / unknown — with evidence and next
        steps. Nothing is downloaded, installed, converted, or executed.

        Flags:
          --json            machine-readable report (same schema the app renders)
          --chip <name>     evaluate against a different Mac's chip
          --ram-gb <n>      evaluate against a different Mac's RAM
          --disk-gb <n>     evaluate against a different Mac's free disk
          --macos <ver>     evaluate against a different macOS version

        Env:
          HF_TOKEN          needed for gated/private repositories
        """)
    }
}
