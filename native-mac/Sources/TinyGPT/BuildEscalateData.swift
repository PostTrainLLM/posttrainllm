import Foundation
import TinyGPTModel

/// `posttrainllm build-escalate-data` (B5) — turn labeled rollouts into SFT data
/// that teaches a specialist when to emit `{"defer_to_cloud": true, ...}`.
///
/// Input JSONL rows: `{instruction|prompt, response, local_correct: Bool,
/// cloud_correct?: Bool, reason?: String}`. The labeling rule
/// (`EscalationLabeling.label`) keeps "local right → don't defer" and "local
/// wrong, cloud fixed → defer" examples and drops the ambiguous rest. The SFT
/// run on the output is the GPU step (not here).
enum BuildEscalateData {
    static func run(args: [String]) {
        var inPath: String?, outPath: String?
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--in":  inPath = args[i+1]; i += 2
            case "--out": outPath = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                inPath = args[i]; i += 1
            }
        }
        guard let inPath = inPath else { fputs("missing <in.jsonl>\n", stderr); exitUsage() }
        guard let outPath = outPath else { fputs("--out required\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: inPath, encoding: .utf8) else {
            fputs("could not read \(inPath)\n", stderr); exit(1)
        }

        var rows: [String] = []
        var nEsc = 0, nKeep = 0, nDrop = 0
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { continue }
            let instr = (o["instruction"] as? String) ?? (o["prompt"] as? String) ?? ""
            let resp = (o["response"] as? String) ?? ""
            guard let localCorrect = o["local_correct"] as? Bool else { continue }
            let cloudCorrect = o["cloud_correct"] as? Bool
            switch EscalationLabeling.label(localCorrect: localCorrect, cloudCorrect: cloudCorrect) {
            case .keepLocal:
                nKeep += 1
                rows.append(sftRow(instr: instr, response: keepResponse(resp)))
            case .escalate:
                nEsc += 1
                let reason = (o["reason"] as? String) ?? "low confidence; defer to cloud"
                rows.append(sftRow(instr: instr, response: deferResponse(reason: reason)))
            case .drop:
                nDrop += 1
            }
        }
        try? rows.joined(separator: "\n").appending("\n").write(toFile: outPath, atomically: true, encoding: .utf8)
        print("build-escalate-data: \(nKeep) keep-local + \(nEsc) escalate (\(nDrop) dropped) → \(outPath)")
    }

    static func keepResponse(_ r: String) -> String {
        jsonObject(["defer_to_cloud": false, "response": r])
    }
    static func deferResponse(reason: String) -> String {
        jsonObject(["defer_to_cloud": true, "reason": reason])
    }
    static func jsonObject(_ o: [String: Any]) -> String {
        (try? String(data: JSONSerialization.data(withJSONObject: o), encoding: .utf8)) ?? "{}"
    }
    static func sftRow(instr: String, response: String) -> String {
        jsonObject(["instruction": instr, "response": response])
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm build-escalate-data <in.jsonl> --out <sft.jsonl>

        Label rollouts for defer-to-cloud SFT (B5). Input rows:
          {instruction|prompt, response, local_correct: Bool, cloud_correct?: Bool, reason?}
        Output: chatml SFT JSONL teaching the {"defer_to_cloud": bool, ...} signal.
        Train it with `posttrainllm sft` (the GPU step). Score with `posttrainllm eval-escalate`.
        """)
        exit(code)
    }
}
