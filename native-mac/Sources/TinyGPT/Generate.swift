import Foundation
import TinyGPTModel

/// `posttrainllm generate <model> --data rows.jsonl --out preds.jsonl` — run a model
/// (optionally base+adapter) over a dataset via a managed serve, writing each
/// row back with the model's output. This is the missing "generate predictions"
/// step the specialist recipes feed into the eval-* gates (eval-sql, eval-router,
/// eval-milu, eval-review, eval-escalate, eval-bfcl).
///
/// UNTESTED in CI — needs a real model + GPU to run a serve. Mirrors the
/// JudgeShim serve+completion pattern (compiles; behavior unverified here).
enum Generate {
    static func run(args: [String]) {
        var model: String?, dataPath: String?, outPath: String?
        var loraPaths: [String] = []
        var loraWeights: [Float] = []
        var promptField = "prompt", outField = "output"
        var maxTokens = 256, servePort = 8097
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--data":         dataPath = args[i+1]; i += 2
            case "--out":          outPath = args[i+1]; i += 2
            case "--lora":         loraPaths.append(args[i+1]); i += 2
            case "--lora-weight":  loraWeights.append(Float(args[i+1]) ?? 1.0); i += 2
            case "--prompt-field": promptField = args[i+1]; i += 2
            case "--out-field":    outField = args[i+1]; i += 2
            case "--max-tokens":   maxTokens = Int(args[i+1]) ?? maxTokens; i += 2
            case "--serve-port":   servePort = Int(args[i+1]) ?? servePort; i += 2
            case "-h", "--help":   exitUsage(0)
            default:
                if args[i].hasPrefix("-") { fputs("unknown flag: \(args[i])\n", stderr); exitUsage() }
                model = args[i]; i += 1
            }
        }
        guard let model = model else { fputs("missing <model>\n", stderr); exitUsage() }
        guard let dataPath = dataPath else { fputs("--data required\n", stderr); exitUsage() }
        guard let outPath = outPath else { fputs("--out required\n", stderr); exitUsage() }
        guard let raw = try? String(contentsOfFile: dataPath, encoding: .utf8) else {
            fputs("could not read \(dataPath)\n", stderr); exit(1)
        }

        while loraWeights.count < loraPaths.count { loraWeights.append(1.0) }
        var serveArgs: [String] = []
        for (idx, path) in loraPaths.enumerated() {
            serveArgs += ["--lora", path, "--lora-weight", "\(loraWeights[idx])"]
        }
        let serve = EvalHarnessSupport.startServe(modelPath: model, port: servePort,
                                                  extraArgs: serveArgs)
        defer { if serve.isRunning { serve.terminate() } }
        let base = "http://127.0.0.1:\(servePort)/v1"

        let outURL = URL(fileURLWithPath: outPath)
        try? FileManager.default.removeItem(at: outURL)
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        guard let fh = try? FileHandle(forWritingTo: outURL) else {
            fputs("could not open \(outPath)\n", stderr); exit(1)
        }
        defer { try? fh.close() }

        var n = 0
        for line in raw.split(separator: "\n") {
            guard let d = line.data(using: .utf8),
                  var o = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { continue }
            let prompt = (o[promptField] as? String) ?? ""
            let text = EvalHarnessSupport.completion(baseURL: base, prompt: prompt, maxTokens: maxTokens) ?? ""
            o[outField] = text
            if let od = try? JSONSerialization.data(withJSONObject: o),
               let outLine = String(data: od, encoding: .utf8) {
                fh.write(Data((outLine + "\n").utf8)); n += 1
            }
        }
        print("generate: wrote \(n) rows to \(outPath) (field '\(outField)')")
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: posttrainllm generate <model> --data rows.jsonl --out preds.jsonl [options]

        Run a model over a dataset via a managed serve; each output row is the
        input row plus the model's text under --out-field. Feeds the eval-* gates.

        --data <jsonl>        input rows (required)
        --out <jsonl>         output rows (required)
        --lora <path>         apply a trained adapter on the base; repeat to compose
        --lora-weight F       per-adapter mix weight when composing (default 1.0)
        --prompt-field NAME   field to send as the prompt (default: prompt)
        --out-field NAME      field to write the output under (default: output)
        --max-tokens N        (default 256)   --serve-port N (default 8097)

        UNTESTED in CI — needs a real model + GPU.
        """)
        exit(code)
    }
}
