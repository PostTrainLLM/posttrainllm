import Foundation
import TinyGPTModel

/// `tinygpt eval-review` (B35) — score a code-review run on issue detection:
/// recall/precision/F1 of reported vs planted issues. Scores a results file;
/// running the review agent over SWE-bench is the GPU step.
enum EvalReview {
    static func run(args: [String]) {
        var dataPath: String?, outPath: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--data": dataPath = args[i+1]; i += 2
            case "--out":  outPath = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                dataPath = args[i]; i += 1
            }
        }
        guard let dataPath = dataPath else { fputs("missing <results.jsonl> (or --data)\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: dataPath, encoding: .utf8) else {
            fputs("could not read \(dataPath)\n", stderr); exit(1)
        }
        var items: [(planted: Set<String>, found: Set<String>)] = []
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let planted = o["planted_issues"] as? [String],
                  let found = o["found_issues"] as? [String] else { continue }
            items.append((Set(planted), Set(found)))
        }
        guard !items.isEmpty else { fputs("no valid rows ({planted_issues:[], found_issues:[]})\n", stderr); exit(1) }
        let r = ReviewScoring.score(items)
        print(String(format: "review: recall=%.3f precision=%.3f f1=%.3f (n=%d)",
                     r.recall, r.precision, r.f1, r.n))
        if let outPath = outPath {
            let rows = [
                ["task": "review", "metric": "recall", "value": r.recall, "n": r.n],
                ["task": "review", "metric": "precision", "value": r.precision, "n": r.n],
                ["task": "review", "metric": "f1", "value": r.f1, "n": r.n],
            ]
            let s = rows.compactMap { try? String(data: JSONSerialization.data(withJSONObject: $0), encoding: .utf8) }
            try? (s.joined(separator: "\n") + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt eval-review <results.jsonl> [--out rows.jsonl]

        Score a code-review run on issue detection (B35). Rows:
          {planted_issues: [String], found_issues: [String]}
        Reports recall / precision / F1 (pooled). Running the reviewer over
        SWE-bench is the GPU step; this scores its output.
        """)
        exit(code)
    }
}
