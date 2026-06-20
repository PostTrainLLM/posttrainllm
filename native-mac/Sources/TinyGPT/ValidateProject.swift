import Foundation
import TinyGPTModel

/// `tinygpt validate-project [<tinygpt.project.json>]` (B31) — structurally
/// validate per-project pins: unique model ids, and every adapter declares an
/// `applies_to` that points at a pinned base. (Resolving each pin against the
/// live gallery is the V2 check.)
enum ValidateProject {
    static func run(args: [String]) {
        var path = "tinygpt.project.json"
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--file": path = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                path = args[i]; i += 1
            }
        }
        do {
            let m = try ProjectManifest.load(path: path)
            try m.validate()
            print("✓ \(path): valid — \(m.models.count) model pins, \(m.datasets?.count ?? 0) dataset pins")
        } catch {
            fputs("✗ \(path): \(error)\n", stderr); exit(1)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt validate-project [<tinygpt.project.json>]

        Structurally validate per-project pins (B31): unique model ids; every
        adapter declares applies_to pointing at a pinned base. Exit 0 = valid,
        non-zero with the first error otherwise. Gallery-resolve checks are V2.
        """)
        exit(code)
    }
}
