import Foundation
import TinyGPTModel

/// `tinygpt eval-escalate` (B5) — score a defer-to-cloud classifier.
///
/// Input JSONL rows: `{defer_pred: Bool, local_wrong: Bool}` (the model's
/// defer decision vs whether local was actually wrong). Emits precision,
/// recall, and over-escalation rate via `EscalationLabeling.metrics`. Pure —
/// the predictions come from a serve/eval run; this just scores them.
enum EvalEscalate {
    static func run(args: [String]) {
        var inPath: String?, outPath: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--out": outPath = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                inPath = args[i]; i += 1
            }
        }
        guard let inPath = inPath else { fputs("missing <predictions.jsonl>\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: inPath, encoding: .utf8) else {
            fputs("could not read \(inPath)\n", stderr); exit(1)
        }
        var preds: [Bool] = [], wrong: [Bool] = []
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let p = o["defer_pred"] as? Bool, let w = o["local_wrong"] as? Bool else { continue }
            preds.append(p); wrong.append(w)
        }
        guard !preds.isEmpty else { fputs("no valid prediction rows\n", stderr); exit(1) }
        let m = EscalationLabeling.metrics(predictions: preds, localWrong: wrong)
        print(String(format: "escalation: precision=%.3f recall=%.3f over-escalation=%.3f (n=%d)",
                     m.precision, m.recall, m.overEscalation, m.n))
        if let outPath = outPath {
            let row: [String: Any] = ["task": "escalate", "precision": m.precision,
                                      "recall": m.recall, "over_escalation": m.overEscalation, "n": m.n]
            if let d = try? JSONSerialization.data(withJSONObject: row) {
                try? (String(data: d, encoding: .utf8)! + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
            }
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt eval-escalate <predictions.jsonl> [--out result.json]

        Score a defer-to-cloud classifier (B5). Input rows:
          {defer_pred: Bool, local_wrong: Bool}
        Reports precision (deferred & truly wrong), recall (of wrong cases
        flagged), and over-escalation (deferred when local was right).
        """)
        exit(code)
    }
}
