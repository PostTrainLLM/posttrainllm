import Foundation
import TinyGPTModel

/// `posttrainllm eval-router` (B2–B7) — router bake-off: per-method tool-selection
/// accuracy from a predictions file, naming the winner + its lead. Generating
/// the predictions (classifier vs FSM-only routers) is the trained-model step;
/// this scores their output.
enum EvalRouter {
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
        guard let dataPath = dataPath else { fputs("missing <preds.jsonl> (or --data)\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: dataPath, encoding: .utf8) else {
            fputs("could not read \(dataPath)\n", stderr); exit(1)
        }
        var rows: [(method: String, correct: Bool)] = []
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                  let method = o["method"] as? String,
                  let pred = o["predicted_tool"] as? String,
                  let gold = o["gold_tool"] as? String else { continue }
            rows.append((method, pred == gold))
        }
        guard !rows.isEmpty else { fputs("no valid router rows\n", stderr); exit(1) }
        let results = RouterBakeoff.score(rows)
        for r in results {
            print("  \(r.method) accuracy=\(String(format: "%.3f", r.accuracy)) (n=\(r.n))")
        }
        if let (best, delta) = RouterBakeoff.winner(results) {
            print("bake-off winner: \(best.method) (+\(String(format: "%.1f", delta))pp)")
        }
        if let outPath = outPath {
            let outRows = results.map { ["task": "router", "subtask": $0.method,
                                         "metric": "accuracy", "value": $0.accuracy, "n": $0.n] as [String: Any] }
            let lines = outRows.compactMap { try? String(data: JSONSerialization.data(withJSONObject: $0), encoding: .utf8) }
            try? (lines.joined(separator: "\n") + "\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        }
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm eval-router <preds.jsonl> [--out rows.jsonl]

        Router bake-off (B2–B7): per-method tool-selection accuracy. Rows:
          {method, predicted_tool, gold_tool}
        Reports accuracy per routing method and the winner's lead (pp).
        """)
        exit(code)
    }
}
