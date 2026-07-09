import Foundation
import TinyGPTModel

/// `posttrainllm eval-milu` (B8) — per-language accuracy breakdown + macro-average
/// for a multilingual eval (MILU shape). Scores a results file; running the
/// model to produce the results is the trained-specialist step.
enum EvalMilu {
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
        var rows: [(language: String, correct: Bool)] = []
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let lang = o["language"] as? String else { continue }
            // accept either an explicit `correct: Bool` or predicted/gold pair
            if let c = o["correct"] as? Bool { rows.append((lang, c)) }
            else if let p = o["predicted"] as? String, let g = o["gold"] as? String { rows.append((lang, p == g)) }
        }
        guard !rows.isEmpty else { fputs("no valid rows ({language, correct} or {language, predicted, gold})\n", stderr); exit(1) }
        let (per, macro) = LanguageBreakdown.score(rows)
        for r in per {
            print("  \(r.language) accuracy=\(String(format: "%.3f", r.accuracy)) (n=\(r.n))")
        }
        print("macro-average=\(String(format: "%.3f", macro)) over \(per.count) languages")
        if let outPath = outPath {
            var lines = per.map { ["task": "milu", "subtask": $0.language, "metric": "accuracy",
                                   "value": $0.accuracy, "n": $0.n] as [String: Any] }
            lines.append(["task": "milu", "subtask": "macro", "metric": "accuracy", "value": macro, "n": per.count])
            let s = lines.compactMap { try? String(data: JSONSerialization.data(withJSONObject: $0), encoding: .utf8) }
            try? (s.joined(separator: "\n") + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm eval-milu <results.jsonl> [--out rows.jsonl]

        Per-language accuracy + macro-average (B8, MILU shape). Rows:
          {language, correct: Bool}  or  {language, predicted, gold}
        Macro-average weights each language equally.
        """)
        exit(code)
    }
}
