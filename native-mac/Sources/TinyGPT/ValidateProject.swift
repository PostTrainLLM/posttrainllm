import Foundation
import TinyGPTModel

/// `tinygpt validate-project [<tinygpt.project.json>]` (B31) — structurally
/// validate per-project pins: unique model ids, and every adapter declares an
/// `applies_to` that points at a pinned base. (Resolving each pin against the
/// live gallery is the V2 check.)
enum ValidateProject {
    static func run(args: [String]) {
        var path = "tinygpt.project.json"
        var galleryPath: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--file":    path = args[i+1]; i += 2
            case "--gallery": galleryPath = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                path = args[i]; i += 1
            }
        }
        do {
            let m = try ProjectManifest.load(path: path)
            try m.validate()
            // B31 gallery-resolve: with --gallery, every model pin must exist
            // in the gallery manifest's id set.
            if let galleryPath {
                let gallery = try GalleryManifest.load(path: galleryPath)
                let ids = Set(gallery.models.map(\.id))
                let unresolved = m.unresolvedPins(galleryIds: ids)
                guard unresolved.isEmpty else {
                    fputs("✗ \(path): pins not in gallery \(galleryPath): \(unresolved.joined(separator: ", "))\n", stderr)
                    exit(1)
                }
                print("✓ \(path): valid — \(m.models.count) model pins (all resolve in \(galleryPath)), \(m.datasets?.count ?? 0) dataset pins")
            } else {
                print("✓ \(path): valid — \(m.models.count) model pins, \(m.datasets?.count ?? 0) dataset pins")
            }
        } catch {
            fputs("✗ \(path): \(error)\n", stderr); exit(1)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt validate-project [<tinygpt.project.json>] [--gallery <manifest.json>]

        Structurally validate per-project pins (B31): unique model ids; every
        adapter declares applies_to pointing at a pinned base. With --gallery,
        also checks every model pin resolves to an id in that gallery manifest.
        Exit 0 = valid, non-zero with the first error otherwise.
        """)
        exit(code)
    }
}
