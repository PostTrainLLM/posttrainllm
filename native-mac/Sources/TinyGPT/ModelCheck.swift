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

    private struct Options {
        var input: String?
        var json = false
        var chip: String?
        var ramGB: Int?
        var diskGB: Int?
        var macOS: String?
    }

    static func run(args: [String]) {
        var options = Options()
        var i = 0
        while i < args.count {
            if consumeOption(args: args, index: &i, options: &options) { continue }
            if options.input != nil {
                fputs("model-check takes exactly one model argument\n", stderr); exit(2)
            }
            options.input = args[i]
            i += 1
        }

        guard let target = options.input else {
            fputs("model-check: a Hugging Face URL or owner/repo is required\n\n", stderr)
            printUsage(); exit(2)
        }

        let envOverride: MacEnvironment? =
            (options.chip != nil || options.ramGB != nil
                || options.diskGB != nil || options.macOS != nil)
            ? .manual(chip: options.chip, ramGB: options.ramGB,
                      diskGB: options.diskGB, macOS: options.macOS)
            : nil

        do {
            let report = try ModelCheckService.check(
                input: target, environment: envOverride
            ) { stage in
                // Progress to stderr so --json stdout stays a clean report.
                fputs("… \(stage.rawValue)\n", stderr)
            }
            if options.json {
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

    private static func consumeOption(
        args: [String], index: inout Int, options: inout Options
    ) -> Bool {
        let flag = args[index]
        switch flag {
        case "--json":
            options.json = true
            index += 1
        case "--chip", "--macos":
            guard index + 1 < args.count else { argumentError("\(flag) needs value") }
            if flag == "--chip" { options.chip = args[index + 1] }
            else { options.macOS = args[index + 1] }
            index += 2
        case "--ram-gb", "--disk-gb":
            guard index + 1 < args.count,
                  let value = Int(args[index + 1]), value > 0,
                  value <= Int64.max / 1_073_741_824 else {
                argumentError("\(flag) needs a positive, representable integer")
            }
            if flag == "--ram-gb" { options.ramGB = value }
            else { options.diskGB = value }
            index += 2
        case "-h", "--help":
            printUsage()
            exit(0)
        default:
            guard flag.hasPrefix("-") else { return false }
            argumentError("unknown flag: \(flag)")
        }
        return true
    }

    private static func argumentError(_ message: String) -> Never {
        fputs("\(message)\n", stderr)
        exit(2)
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
