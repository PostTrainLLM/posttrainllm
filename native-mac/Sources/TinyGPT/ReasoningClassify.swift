import Foundation

/// 4-class prompt reasoning-depth classifier — bag-of-trigrams + softmax-4.
///
/// Castform's reasoning-classification step (docs/learn/castform-rl-finetune.md §3).
/// Tags every prompt with depth: `single-hop` / `multi-hop` / `comparison` / `other`.
/// Output feeds B29's trace-to-training-data pipeline (balanced training mix)
/// and the B27 leaderboard (per-depth breakdown).
///
/// On-disk format (`.tgfr`):
///   magic "TGFR" (4B) | version u32 | vocabSize u32 | ngramOrder u32 | numClasses u32
///   | for c in 0..<numClasses: bias[c] f32, weights[c] f32 × vocabSize
///
/// Subcommand: `tinygpt reasoning-classify --mode {train|score|filter} ...`
enum ReasoningClassify {

    static let magic: [UInt8] = Array("TGFR".utf8)
    static let version: UInt32 = 1
    static let defaultVocab: Int = 65_536
    static let defaultNgram: Int = 3
    static let labels: [String] = ["single-hop", "multi-hop", "comparison", "other"]
    static var numClasses: Int { labels.count }

    // MARK: - Tokenize + hash + ngrams (same shape as QualityClassifier)

    private static func tokenize(_ text: String) -> [String] {
        var out: [String] = []
        var current = [Character]()
        out.reserveCapacity(text.count / 5)
        for ch in text.lowercased() {
            if ch.isLetter || ch.isNumber {
                current.append(ch)
            } else if !current.isEmpty {
                out.append(String(current)); current.removeAll(keepingCapacity: true)
            }
        }
        if !current.isEmpty { out.append(String(current)) }
        return out
    }

    private static func hash(_ s: String, vocabSize: Int) -> Int {
        var h: UInt32 = 2_166_136_261
        for b in s.utf8 {
            h ^= UInt32(b)
            h = h &* 16_777_619
        }
        return Int(h) % vocabSize
    }

    private static func ngrams(words: [String], n: Int, vocabSize: Int) -> [Int] {
        guard !words.isEmpty else { return [] }
        var buckets: [Int] = []
        buckets.reserveCapacity(words.count * 3)
        for w in words { buckets.append(hash(w, vocabSize: vocabSize)) }
        if n >= 2, words.count >= 2 {
            for i in 0..<(words.count - 1) {
                buckets.append(hash("\(words[i])_\(words[i + 1])", vocabSize: vocabSize))
            }
        }
        if n >= 3, words.count >= 3 {
            for i in 0..<(words.count - 2) {
                buckets.append(hash("\(words[i])_\(words[i + 1])_\(words[i + 2])", vocabSize: vocabSize))
            }
        }
        return buckets
    }

    // MARK: - Softmax-K scoring

    /// Returns `logits[c] = bias[c] + Σ weights[c][bucket]` for each class.
    private static func logits(buckets: [Int],
                                weights: [[Float]], bias: [Float]) -> [Float] {
        let k = bias.count
        var out = bias
        for c in 0..<k {
            for b in buckets { out[c] += weights[c][b] }
        }
        return out
    }

    /// Numerically-stable softmax: subtract max before exp.
    private static func softmax(_ logits: [Float]) -> [Float] {
        let m = logits.max() ?? 0
        var exps = [Float](repeating: 0, count: logits.count)
        var s: Float = 0
        for i in 0..<logits.count { exps[i] = expf(logits[i] - m); s += exps[i] }
        if s == 0 { return [Float](repeating: 1.0 / Float(logits.count), count: logits.count) }
        for i in 0..<exps.count { exps[i] /= s }
        return exps
    }

    private static func argmax(_ v: [Float]) -> Int {
        var bi = 0
        for i in 1..<v.count where v[i] > v[bi] { bi = i }
        return bi
    }

    // MARK: - Model I/O

    private static func saveModel(weights: [[Float]], bias: [Float],
                                   vocabSize: Int, ngramOrder: Int,
                                   to url: URL) throws {
        precondition(weights.count == bias.count)
        var out = Data()
        out.append(contentsOf: magic)
        var v = version.littleEndian
        withUnsafeBytes(of: &v) { out.append(contentsOf: $0) }
        var vs = UInt32(vocabSize).littleEndian
        withUnsafeBytes(of: &vs) { out.append(contentsOf: $0) }
        var ng = UInt32(ngramOrder).littleEndian
        withUnsafeBytes(of: &ng) { out.append(contentsOf: $0) }
        var nc = UInt32(weights.count).littleEndian
        withUnsafeBytes(of: &nc) { out.append(contentsOf: $0) }
        for c in 0..<weights.count {
            var bC = bias[c]
            withUnsafeBytes(of: &bC) { out.append(contentsOf: $0) }
            weights[c].withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
        }
        try out.write(to: url, options: .atomic)
    }

    fileprivate struct LoadedModel {
        let weights: [[Float]]
        let bias: [Float]
        let vocabSize: Int
        let ngramOrder: Int
        var numClasses: Int { bias.count }
    }

    fileprivate static func loadModel(from url: URL) throws -> LoadedModel {
        let data = try Data(contentsOf: url)
        guard data.count >= 24 else {
            throw NSError(domain: "tgfr", code: 1, userInfo: [NSLocalizedDescriptionKey: "file too small"])
        }
        guard Array(data.prefix(4)) == magic else {
            throw NSError(domain: "tgfr", code: 2, userInfo: [NSLocalizedDescriptionKey: "magic mismatch (expected TGFR)"])
        }
        let ver = data[4..<8].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self).littleEndian }
        guard ver == version else {
            throw NSError(domain: "tgfr", code: 3, userInfo: [NSLocalizedDescriptionKey: "unsupported version \(ver)"])
        }
        let vs = Int(data[8..<12].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self).littleEndian })
        let ng = Int(data[12..<16].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self).littleEndian })
        let nc = Int(data[16..<20].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self).littleEndian })
        var bias = [Float](); bias.reserveCapacity(nc)
        var weights = [[Float]](); weights.reserveCapacity(nc)
        var off = 20
        for _ in 0..<nc {
            let b = data[off..<(off + 4)].withUnsafeBytes { $0.loadUnaligned(as: Float.self) }
            bias.append(b); off += 4
            let wBytes = data[off..<(off + vs * 4)]
            let w = wBytes.withUnsafeBytes { raw -> [Float] in
                let buf = UnsafeBufferPointer(
                    start: raw.baseAddress?.assumingMemoryBound(to: Float.self),
                    count: vs)
                return Array(buf)
            }
            weights.append(w); off += vs * 4
        }
        return LoadedModel(weights: weights, bias: bias, vocabSize: vs, ngramOrder: ng)
    }

    // MARK: - Labeled-input reader

    /// Read `(text, label_idx)` rows from a JSONL with `prompt` + `reasoning_depth`.
    /// Unknown label strings → "other" (idx 3).
    private static func readLabeled(_ path: String) -> [(String, Int)] {
        guard let raw = try? String(contentsOfFile: path, encoding: .utf8) else {
            fputs("could not read \(path)\n", stderr); exit(1)
        }
        var out: [(String, Int)] = []
        let labelIdx = Dictionary(uniqueKeysWithValues: labels.enumerated().map { ($1, $0) })
        for line in raw.split(separator: "\n") {
            guard let data = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }
            let text = (obj["prompt"] as? String) ?? (obj["text"] as? String) ?? ""
            let lbl = (obj["reasoning_depth"] as? String) ?? (obj["label"] as? String) ?? "other"
            guard !text.isEmpty else { continue }
            out.append((text, labelIdx[lbl] ?? (labels.count - 1)))
        }
        return out
    }

    // MARK: - Train mode

    private static func runTrain(_ args: [String]) {
        var trainPath: String? = nil
        var outPath: String? = nil
        var vocabSize: Int = defaultVocab
        var ngramOrder: Int = defaultNgram
        var epochs: Int = 8
        var lr: Float = 0.1
        var l2: Float = 1e-5
        var seed: UInt64 = 42
        var heldoutPath: String? = nil

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--train":     trainPath = args[i+1]; i += 2
            case "--out":       outPath = args[i+1]; i += 2
            case "--heldout":   heldoutPath = args[i+1]; i += 2
            case "--vocab":     vocabSize = max(1024, Int(args[i+1]) ?? vocabSize); i += 2
            case "--ngram":     ngramOrder = max(1, min(3, Int(args[i+1]) ?? ngramOrder)); i += 2
            case "--epochs":    epochs = max(1, Int(args[i+1]) ?? epochs); i += 2
            case "--lr":        lr = Float(args[i+1]) ?? lr; i += 2
            case "--l2":        l2 = Float(args[i+1]) ?? l2; i += 2
            case "--seed":      seed = UInt64(args[i+1]) ?? seed; i += 2
            default:            fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }
        guard let trainPath = trainPath, let outPath = outPath else {
            fputs("--train and --out required\n", stderr); exitUsage()
        }
        let rows = readLabeled(trainPath)
        guard !rows.isEmpty else { fputs("no rows in \(trainPath)\n", stderr); exit(1) }
        print("""

        TinyGPT — reasoning-depth classifier (train)
        --------------------------------------------
        train:       \(trainPath) (\(rows.count) rows)
        heldout:     \(heldoutPath ?? "none")
        labels:      \(labels.joined(separator: ", "))
        vocab:       \(vocabSize)
        ngram:       \(ngramOrder)
        epochs:      \(epochs)
        lr:          \(lr)
        l2:          \(l2)
        seed:        \(seed)
        """)

        // Pre-bucketize.
        struct Example { let buckets: [Int]; let label: Int }
        var examples: [Example] = []
        examples.reserveCapacity(rows.count)
        for (text, lbl) in rows {
            let toks = tokenize(text)
            let bk = ngrams(words: toks, n: ngramOrder, vocabSize: vocabSize)
            examples.append(Example(buckets: bk, label: lbl))
        }

        var weights = [[Float]](repeating: [Float](repeating: 0, count: vocabSize), count: numClasses)
        var bias = [Float](repeating: 0, count: numClasses)
        var rng = Mulberry32R(seed: UInt32(truncatingIfNeeded: seed))

        for epoch in 0..<epochs {
            // Shuffle.
            for i in stride(from: examples.count - 1, through: 1, by: -1) {
                let j = Int(rng.next() % UInt32(i + 1))
                if i != j { examples.swapAt(i, j) }
            }
            var lossSum: Double = 0
            var correct = 0
            for ex in examples {
                var lg = bias
                for c in 0..<numClasses {
                    for b in ex.buckets { lg[c] += weights[c][b] }
                }
                let probs = softmax(lg)
                let pTrue = max(probs[ex.label], Float(1e-10))
                lossSum += -Double(logf(pTrue))
                // SGD: ∂L/∂logit[c] = probs[c] - 1{c==label}
                for c in 0..<numClasses {
                    let grad: Float = probs[c] - (c == ex.label ? 1 : 0)
                    bias[c] -= lr * grad
                    let stepBuckets = ex.buckets
                    for b in stepBuckets {
                        weights[c][b] -= lr * (grad + l2 * weights[c][b])
                    }
                }
                if argmax(probs) == ex.label { correct += 1 }
            }
            let avgLoss = lossSum / Double(examples.count)
            let acc = Float(correct) / Float(examples.count)
            print(String(format: "  epoch %d/%d  loss %.4f  train-acc %.3f", epoch + 1, epochs, avgLoss, acc))
        }

        // Held-out eval (if provided).
        if let heldoutPath = heldoutPath {
            let heldRows = readLabeled(heldoutPath)
            let metrics = evaluate(rows: heldRows, weights: weights, bias: bias,
                                    vocabSize: vocabSize, n: ngramOrder)
            print("""

            held-out eval (\(heldRows.count) rows)
              accuracy:   \(String(format: "%.3f", metrics.accuracy))
              macro-F1:   \(String(format: "%.3f", metrics.macroF1))
            """)
            for (i, lbl) in labels.enumerated() {
                let padded = lbl.padding(toLength: 12, withPad: " ", startingAt: 0)
                print(String(format: "    \(padded)  precision %.3f  recall %.3f  f1 %.3f  (n=%d)",
                              metrics.precision[i], metrics.recall[i], metrics.f1[i], metrics.support[i]))
            }
        }

        do {
            try saveModel(weights: weights, bias: bias,
                           vocabSize: vocabSize, ngramOrder: ngramOrder,
                           to: URL(fileURLWithPath: outPath))
            let sz = 20 + numClasses * (4 + vocabSize * 4)
            print("\nwrote classifier → \(outPath) (\(sz) bytes)")
        } catch {
            fputs("save failed: \(error)\n", stderr); exit(1)
        }
    }

    fileprivate struct Metrics {
        let accuracy: Float
        let macroF1: Float
        let precision: [Float]
        let recall: [Float]
        let f1: [Float]
        let support: [Int]
    }

    fileprivate static func evaluate(rows: [(String, Int)],
                                      weights: [[Float]], bias: [Float],
                                      vocabSize: Int, n: Int) -> Metrics {
        let k = bias.count
        var tp = [Int](repeating: 0, count: k)
        var fp = [Int](repeating: 0, count: k)
        var fn = [Int](repeating: 0, count: k)
        var support = [Int](repeating: 0, count: k)
        var correct = 0
        for (text, lbl) in rows {
            let toks = tokenize(text)
            let bk = ngrams(words: toks, n: n, vocabSize: vocabSize)
            let lg = logits(buckets: bk, weights: weights, bias: bias)
            let pred = argmax(lg)
            support[lbl] += 1
            if pred == lbl { tp[lbl] += 1; correct += 1 }
            else { fp[pred] += 1; fn[lbl] += 1 }
        }
        var precision = [Float](repeating: 0, count: k)
        var recall = [Float](repeating: 0, count: k)
        var f1 = [Float](repeating: 0, count: k)
        for c in 0..<k {
            let pDen = tp[c] + fp[c]
            let rDen = tp[c] + fn[c]
            precision[c] = pDen == 0 ? 0 : Float(tp[c]) / Float(pDen)
            recall[c] = rDen == 0 ? 0 : Float(tp[c]) / Float(rDen)
            let f1Den = precision[c] + recall[c]
            f1[c] = f1Den == 0 ? 0 : 2 * precision[c] * recall[c] / f1Den
        }
        let acc = rows.isEmpty ? 0 : Float(correct) / Float(rows.count)
        let macroF1 = k == 0 ? 0 : f1.reduce(0, +) / Float(k)
        return Metrics(accuracy: acc, macroF1: macroF1,
                        precision: precision, recall: recall, f1: f1, support: support)
    }

    // MARK: - Score mode

    private static func runScore(_ args: [String]) {
        var inputPath: String? = nil
        var modelPath: String? = nil
        var outPath: String? = nil
        var promptField: String = "prompt"

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--score":   inputPath = args[i+1]; i += 2
            case "--model":   modelPath = args[i+1]; i += 2
            case "--out":     outPath = args[i+1]; i += 2
            case "--field":   promptField = args[i+1]; i += 2
            default:          fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }
        guard let inputPath = inputPath, let modelPath = modelPath, let outPath = outPath else {
            fputs("--score, --model, --out required\n", stderr); exitUsage()
        }
        let model: LoadedModel
        do { model = try loadModel(from: URL(fileURLWithPath: modelPath)) }
        catch { fputs("load failed: \(error)\n", stderr); exit(1) }
        print("loaded reasoning-classify model: vocab=\(model.vocabSize), ngram=\(model.ngramOrder), classes=\(model.numClasses)")

        guard let raw = try? String(contentsOfFile: inputPath, encoding: .utf8) else {
            fputs("could not read \(inputPath)\n", stderr); exit(1)
        }
        let outURL = URL(fileURLWithPath: outPath)
        try? FileManager.default.removeItem(at: outURL)
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        guard let outFH = try? FileHandle(forWritingTo: outURL) else {
            fputs("could not open \(outPath) for write\n", stderr); exit(1)
        }
        defer { try? outFH.close() }

        var counts = [Int](repeating: 0, count: model.numClasses)
        var total = 0
        let startedAt = Date()
        var bytesRead = 0
        for line in raw.split(separator: "\n", omittingEmptySubsequences: true) {
            guard let data = line.data(using: .utf8),
                  var obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }
            let text = (obj[promptField] as? String) ?? (obj["text"] as? String) ?? ""
            guard !text.isEmpty else { continue }
            bytesRead += text.utf8.count
            let toks = tokenize(text)
            let bk = ngrams(words: toks, n: model.ngramOrder, vocabSize: model.vocabSize)
            let lg = logits(buckets: bk, weights: model.weights, bias: model.bias)
            let pred = argmax(lg)
            obj["reasoning_depth"] = labels[pred]
            counts[pred] += 1; total += 1
            if let encoded = try? JSONSerialization.data(withJSONObject: obj) {
                try? outFH.write(contentsOf: encoded)
                try? outFH.write(contentsOf: Data([0x0A]))
            }
        }
        let elapsed = Date().timeIntervalSince(startedAt)
        let mbps = elapsed > 0 ? (Double(bytesRead) / 1_048_576.0) / elapsed : 0
        print("""

        scored:    \(total) rows
        throughput: \(String(format: "%.2f", mbps)) MB/s (text bytes)
        per-class:
        """)
        for c in 0..<model.numClasses {
            let pct = total == 0 ? 0 : Float(counts[c]) / Float(total) * 100
            let padded = labels[c].padding(toLength: 12, withPad: " ", startingAt: 0)
            print(String(format: "  \(padded) %d (%.1f%%)", counts[c], pct))
        }
    }

    // MARK: - Filter mode

    /// Downsample a `--score`d JSONL to match a target reasoning-depth mix.
    /// `--target-mix "single=0.3,multi=0.5,comparison=0.2,other=0.0"`.
    /// Missing keys default to 0 (drop class entirely).
    private static func runFilter(_ args: [String]) {
        var inputPath: String? = nil
        var outPath: String? = nil
        var targetSpec: String = ""
        var seed: UInt64 = 42

        var i = 0
        while i < args.count {
            switch args[i] {
            case "--filter":      inputPath = args[i+1]; i += 2
            case "--out":         outPath = args[i+1]; i += 2
            case "--target-mix":  targetSpec = args[i+1]; i += 2
            case "--seed":        seed = UInt64(args[i+1]) ?? seed; i += 2
            default:              fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
            }
        }
        guard let inputPath = inputPath, let outPath = outPath else {
            fputs("--filter and --out required\n", stderr); exitUsage()
        }

        // Parse target mix. Accept short keys ("single", "multi", "comparison",
        // "other") or full label names.
        let aliases: [String: String] = [
            "single": "single-hop", "single-hop": "single-hop",
            "multi": "multi-hop", "multi-hop": "multi-hop",
            "comparison": "comparison", "compare": "comparison",
            "other": "other"
        ]
        var target = [Float](repeating: 0, count: numClasses)
        for kv in targetSpec.split(separator: ",") {
            let parts = kv.split(separator: "=", maxSplits: 1).map { String($0).trimmingCharacters(in: .whitespaces) }
            guard parts.count == 2, let v = Float(parts[1]) else { continue }
            guard let canon = aliases[parts[0].lowercased()],
                  let idx = labels.firstIndex(of: canon) else { continue }
            target[idx] = v
        }
        let sum = target.reduce(0, +)
        guard sum > 0 else { fputs("--target-mix is empty or unparseable\n", stderr); exit(1) }
        for i in 0..<target.count { target[i] /= sum }

        guard let raw = try? String(contentsOfFile: inputPath, encoding: .utf8) else {
            fputs("could not read \(inputPath)\n", stderr); exit(1)
        }
        // Bucket per class, preserving raw line text.
        var bucket = [[String]](repeating: [], count: numClasses)
        let labelIdx = Dictionary(uniqueKeysWithValues: labels.enumerated().map { ($1, $0) })
        for line in raw.split(separator: "\n", omittingEmptySubsequences: true) {
            guard let data = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }
            let lbl = (obj["reasoning_depth"] as? String) ?? "other"
            let ci = labelIdx[lbl] ?? (numClasses - 1)
            bucket[ci].append(String(line))
        }

        // Largest feasible total N such that target[c] * N ≤ bucket[c].count
        // for all c with target[c] > 0. Pick N = floor(min(bucket[c].count / target[c])).
        var maxN = Int.max
        for c in 0..<numClasses where target[c] > 0 {
            let cap = Int(Float(bucket[c].count) / target[c])
            if cap < maxN { maxN = cap }
        }
        if maxN == Int.max { maxN = 0 }

        var rng = Mulberry32R(seed: UInt32(truncatingIfNeeded: seed))
        let outURL = URL(fileURLWithPath: outPath)
        try? FileManager.default.removeItem(at: outURL)
        FileManager.default.createFile(atPath: outURL.path, contents: nil)
        guard let outFH = try? FileHandle(forWritingTo: outURL) else {
            fputs("could not open \(outPath) for write\n", stderr); exit(1)
        }
        defer { try? outFH.close() }

        var emitted = [Int](repeating: 0, count: numClasses)
        for c in 0..<numClasses {
            let want = Int((Float(maxN) * target[c]).rounded())
            // Shuffle bucket[c], take first `want`.
            var arr = bucket[c]
            for i in stride(from: arr.count - 1, through: 1, by: -1) {
                let j = Int(rng.next() % UInt32(i + 1))
                if i != j { arr.swapAt(i, j) }
            }
            let take = min(want, arr.count)
            for k in 0..<take {
                try? outFH.write(contentsOf: Data((arr[k] + "\n").utf8))
            }
            emitted[c] = take
        }

        let totalOut = emitted.reduce(0, +)
        print("""

        TinyGPT — reasoning-classify --filter
        input:       \(inputPath)  (per-class: \(bucket.map { $0.count }))
        target mix:  \(target.map { String(format: "%.2f", $0) })
        emitted:     \(totalOut) rows
        per-class:
        """)
        for c in 0..<numClasses {
            let frac = totalOut == 0 ? 0 : Float(emitted[c]) / Float(totalOut)
            let padded = labels[c].padding(toLength: 12, withPad: " ", startingAt: 0)
            print(String(format: "  \(padded) %d (%.1f%%)", emitted[c], frac * 100))
        }
        print("out:         \(outPath)")
    }

    // MARK: - Entry

    static func run(args: [String]) {
        // Modes are gated by which "primary" flag is present so a single
        // subcommand dispatches cleanly.
        if args.contains("-h") || args.contains("--help") || args.isEmpty { exitUsage(0) }
        if args.contains("--train") { runTrain(args); return }
        if args.contains("--score") { runScore(args); return }
        if args.contains("--filter") { runFilter(args); return }
        fputs("reasoning-classify: must pass one of --train / --score / --filter\n", stderr)
        exitUsage()
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt reasoning-classify --train <labeled.jsonl> --out <reason.tgfr> \\
                                          [--heldout <held.jsonl>] [options]
               tinygpt reasoning-classify --score <corpus.jsonl> --model <reason.tgfr> \\
                                          --out <scored.jsonl> [--field <prompt-field>]
               tinygpt reasoning-classify --filter <scored.jsonl> --out <balanced.jsonl> \\
                                          --target-mix "single=0.3,multi=0.5,comparison=0.2,other=0.0" \\
                                          [--seed <n>]

        Tag prompts by reasoning depth: single-hop, multi-hop, comparison, other.
        Bag-of-trigram + softmax-4 (the FineWeb-Edu shape, extended to multiclass).

        --train mode flags:
          --vocab N    hashed-feature vocab size  (default \(defaultVocab))
          --ngram N    1 / 2 / 3                  (default \(defaultNgram))
          --epochs N   SGD passes                 (default 8)
          --lr F       learning rate              (default 0.1)
          --l2 F       L2 regulariser             (default 1e-5)
          --seed N     deterministic shuffle      (default 42)
          --heldout    JSONL for held-out metrics

        --score mode reads JSONL (`--field` selects the prompt field, default "prompt")
                     and writes the same rows with `reasoning_depth` added.

        --filter mode reads --score's output, downsamples to match --target-mix.
                     Aliases: single | multi | comparison | other.
        """)
        exit(code)
    }
}

/// Mulberry32 — tiny seedable PRNG. Duplicate of the one in QualityClassifier;
/// shared utility lives behind the deferred BagOfNgramClassifier refactor.
private struct Mulberry32R {
    private var state: UInt32
    init(seed: UInt32) { self.state = seed == 0 ? 0xDEADBEEF : seed }
    mutating func next() -> UInt32 {
        state = state &+ 0x6D2B79F5
        var z: UInt32 = state
        z = (z ^ (z >> 15)) &* (z | 1)
        z = z ^ (z &+ ((z ^ (z >> 7)) &* (z | 61)))
        return z ^ (z >> 14)
    }
}
