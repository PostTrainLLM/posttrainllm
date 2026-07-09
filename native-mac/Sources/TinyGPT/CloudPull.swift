import Foundation
import TinyGPTIO
import TinyGPTModel

/// `posttrainllm pull --tag <name> [--out path]` — download a checkpoint from R2.
/// B31: with no `--tag`, resolves the base model pin from `posttrainllm.project.json`.
enum CloudPull {
    static func run(args: [String]) {
        var tag: String?
        var out: String?
        var dryRun = false
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--tag":     tag = args[i+1]; i += 2
            case "--out":     out = args[i+1]; i += 2
            case "--dry-run": dryRun = true; i += 1
            case "-h", "--help": exitUsage(0)
            default:
                fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }
        // B31 — no --tag: resolve the base model pin from the project file.
        if tag == nil,
           let manifest = try? ProjectManifest.load(path: "posttrainllm.project.json"),
           let base = manifest.basePin {
            tag = base.id
            print("pull: no --tag — using base pin '\(base.id)' from posttrainllm.project.json")
        }
        guard let tag = tag else {
            fputs("pull: --tag <name> required (or a posttrainllm.project.json with a base pin)\n", stderr); exitUsage()
        }
        let remoteKey = tag.hasSuffix(".tinygpt") ? tag : "\(tag).tinygpt"
        // Default output: same filename in current dir
        let localPath = out ?? URL(fileURLWithPath: remoteKey).lastPathComponent

        do {
            try R2Client.verifyAwsCli()
            let creds = try R2Client.resolveCredentials()
            print("→ pulling s3://\(creds.bucket)/\(remoteKey) → \(localPath)")
            try R2Client.pull(remoteKey: remoteKey, localPath: localPath,
                              creds: creds, dryRun: dryRun)
            if !dryRun {
                print("✓ downloaded")
            }
        } catch {
            fputs("\(error)\n", stderr)
            exit(1)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm pull --tag <name> [--out path] [--dry-run]

        Download a checkpoint from Cloudflare R2. Same credential
        resolution as `posttrainllm push`.
        """)
        exit(code)
    }
}
