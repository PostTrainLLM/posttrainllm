import Foundation
import TinyGPTModel

/// Shared schema for every `tinygpt eval-*` subcommand + a comparison
/// CLI that ingests multiple eval JSONLs and renders a pivot table.
///
/// Design decision (E0, see docs/PLAN.md Tier E): every harness wrapper
/// emits rows that conform to this exact shape. Two queries become
/// trivial:
///   - **Cross-model**: TinyGPT-huge-base-v1 vs SmolLM2-135M on MMLU
///   - **Cross-checkpoint**: huge-base-v1 step-1000 vs step-10000 vs
///     step-50000 on GSM8K (training dynamics)
///
/// Both fall out for free given a single column-stable JSONL contract.
public enum EvalCompare {

    /// One result row. Emitted by E1/E2/E3/.../E7 wrappers; consumed by
    /// `eval-compare`. JSON keys are snake_case so Python harnesses can
    /// write the same shape without translation.
    public struct Row: Codable, Hashable {
        public let run_id: String          // UUID per eval invocation
        public let model_path: String      // absolute path on disk
        public let model_name: String      // "tinygpt-huge-base-v1", "SmolLM2-135M", ...
        public let model_step: Int?        // training step (nil for foreign models)
        public let baseline: Bool          // true = reference model
        public let task: String            // "mmlu", "gsm8k", "bfcl", "humaneval", ...
        public let subtask: String?        // "mmlu/physics", "bfcl/parallel", ...
        public let metric: String          // "accuracy", "exact_match", "f1", "pass@1"
        public let score: Double           // 0..1 typically
        public let n_examples: Int
        public let wall_seconds: Double
        public let timestamp: String       // ISO8601
        public let harness_version: String?
        public let evalProtocol: EvalGate.AgentEvalProtocol?
        /// Optional K-pass uncertainty for this row. Older rows omit it;
        /// `eval-compare` also derives the same shape when repeated rows
        /// with the same task/model/metric are present in the input JSONL.
        public let passStats: EvalGate.PassStats?

        enum CodingKeys: String, CodingKey {
            case run_id, model_path, model_name, model_step, baseline
            case task, subtask, metric, score, n_examples, wall_seconds
            case timestamp, harness_version
            case evalProtocol = "protocol"
            case passStats = "pass_stats"
        }

        public init(run_id: String, model_path: String, model_name: String,
                    model_step: Int? = nil, baseline: Bool = false,
                    task: String, subtask: String? = nil,
                    metric: String, score: Double, n_examples: Int,
                    wall_seconds: Double, timestamp: String? = nil,
                    harness_version: String? = nil,
                    evalProtocol: EvalGate.AgentEvalProtocol? = nil,
                    passStats: EvalGate.PassStats? = nil) {
            self.run_id = run_id
            self.model_path = model_path
            self.model_name = model_name
            self.model_step = model_step
            self.baseline = baseline
            self.task = task
            self.subtask = subtask
            self.metric = metric
            self.score = score
            self.n_examples = n_examples
            self.wall_seconds = wall_seconds
            self.timestamp = timestamp ?? ISO8601DateFormatter().string(from: Date())
            self.harness_version = harness_version
            self.evalProtocol = evalProtocol
            self.passStats = passStats
        }

        /// Helper for harness wrappers — encode + append one row.
        public static func append(_ row: Row, to url: URL) throws {
            let enc = JSONEncoder()
            enc.outputFormatting = [.sortedKeys]
            var data = try enc.encode(row)
            data.append(0x0A)  // newline
            if FileManager.default.fileExists(atPath: url.path) {
                let h = try FileHandle(forWritingTo: url)
                try h.seekToEnd()
                try h.write(contentsOf: data)
                try h.close()
            } else {
                try data.write(to: url, options: .atomic)
            }
        }
    }

    // MARK: - eval-compare CLI

    static func run(args: [String]) {
        var paths: [String] = []
        var groupBy: String = "model"   // model | step | task
        var sortBy: String = "score"
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--by":       groupBy = args[i+1]; i += 2
            case "--sort":     sortBy = args[i+1]; i += 2
            case "-h", "--help": exitUsage(0)
            default:
                if args[i].hasPrefix("-") {
                    fputs("unknown flag: \(args[i])\n", stderr); exitUsage()
                }
                paths.append(args[i]); i += 1
            }
        }
        guard !paths.isEmpty else { fputs("missing eval jsonl path(s)\n", stderr); exitUsage() }

        var rows: [Row] = []
        for p in paths {
            guard let data = try? Data(contentsOf: URL(fileURLWithPath: p)) else {
                fputs("could not read \(p)\n", stderr); continue
            }
            guard let text = String(data: data, encoding: .utf8) else { continue }
            let dec = JSONDecoder()
            for line in text.split(separator: "\n") {
                let trimmed = line.trimmingCharacters(in: .whitespaces)
                guard !trimmed.isEmpty else { continue }
                guard let lineData = trimmed.data(using: .utf8),
                      let row = try? dec.decode(Row.self, from: lineData)
                else { continue }
                rows.append(row)
            }
        }
        guard !rows.isEmpty else {
            fputs("no valid eval rows found across \(paths.count) file(s)\n", stderr); exit(1)
        }

        switch groupBy {
        case "model":  printByModel(rows)
        case "step":   printByStep(rows)
        case "task":   printByTask(rows)
        default:       fputs("unknown --by '\(groupBy)' (expected: model|step|task)\n", stderr); exitUsage()
        }
        _ = sortBy  // reserved for future "--sort name" / "--sort score" options
    }

    // MARK: - render

    /// Group by task × model; one row per task with one column per model.
    /// The canonical "did we beat the baseline" view.
    private static func printByModel(_ rows: [Row]) {
        let tasks = Array(Set(rows.map { $0.task })).sorted()
        // Sort models: baselines first (so "did we beat them" reads naturally
        // left-to-right), then ours alphabetically.
        // Same model_name appears across rows (different steps, different
        // tasks). `Dictionary(uniqueKeysWithValues:)` traps on duplicates;
        // last-write-wins via the merging initializer matches "if ANY row
        // for this name says baseline, it's a baseline".
        let nameToBaseline: [String: Bool] = Dictionary(
            rows.map { ($0.model_name, $0.baseline) },
            uniquingKeysWith: { a, b in a || b })
        let models = Array(Set(rows.map { $0.model_name })).sorted { a, b in
            let aB = nameToBaseline[a] ?? false
            let bB = nameToBaseline[b] ?? false
            if aB != bB { return aB && !bB }
            return a < b
        }

        var grouped: [String: [String: [Row]]] = [:]   // task → model → rows
        for r in rows {
            grouped[r.task, default: [:]][r.model_name, default: []].append(r)
        }

        // Column width has to fit BOTH the header (model name) and the
        // wide-format cells ("0.350±0.020  (n=12345,k=3)"). Otherwise the trailing
        // ")" gets truncated by `.padding(toLength:)`.
        var renderedCells: [String: [String: String]] = [:]
        for task in tasks {
            for model in models {
                if let summary = summarize(grouped[task]?[model] ?? []) {
                    renderedCells[task, default: [:]][model] = render(summary)
                }
            }
        }
        let maxCellW = renderedCells.values.flatMap { $0.values.map(\.count) }.max() ?? 0
        let modelW = max((models.map { $0.count }.max() ?? 8), maxCellW)
        let taskW = max(8, (tasks.map { $0.count }.max() ?? 8))

        print("")
        print("Eval comparison — by model × task")
        print(String(repeating: "─", count: taskW + (modelW + 4) * models.count + 4))
        var header = "task".padding(toLength: taskW, withPad: " ", startingAt: 0)
        for m in models {
            header += "  " + m.padding(toLength: modelW, withPad: " ", startingAt: 0)
        }
        print(header)
        print(String(repeating: "─", count: taskW + (modelW + 4) * models.count + 4))
        for task in tasks {
            var row = task.padding(toLength: taskW, withPad: " ", startingAt: 0)
            for m in models {
                if let cell = renderedCells[task]?[m] {
                    row += "  " + cell.padding(toLength: modelW, withPad: " ", startingAt: 0)
                } else {
                    row += "  " + "—".padding(toLength: modelW, withPad: " ", startingAt: 0)
                }
            }
            print(row)
        }
        print("")
    }

    /// Group by step — useful for training-dynamics views from a single
    /// training run (rows with the same model_name + multiple model_step).
    private static func printByStep(_ rows: [Row]) {
        // Pin to a single model_name — pick the one with the most rows.
        let modelCounts = Dictionary(grouping: rows, by: { $0.model_name })
            .mapValues { $0.count }
        guard let model = modelCounts.max(by: { $0.value < $1.value })?.key else { return }
        let mine = rows.filter { $0.model_name == model && $0.model_step != nil }
        guard !mine.isEmpty else {
            print("no rows with model_step (need a save-history training run)"); return
        }
        let tasks = Array(Set(mine.map { $0.task })).sorted()
        let steps = Array(Set(mine.compactMap { $0.model_step })).sorted()

        print("")
        print("Eval emergence — \(model) over \(steps.count) checkpoints")
        var header = "step    "
        for t in tasks {
            header += "  " + t.padding(toLength: 10, withPad: " ", startingAt: 0)
        }
        print(header)
        print(String(repeating: "─", count: header.count))

        var by: [Int: [String: [Row]]] = [:]
        for r in mine {
            by[r.model_step!, default: [:]][r.task, default: []].append(r)
        }
        for s in steps {
            var line = String(format: "%-8d", s)
            for t in tasks {
                let cell = summarize(by[s]?[t] ?? []).map { renderScoreOnly($0) } ?? "—"
                line += "  " + cell.padding(toLength: 10, withPad: " ", startingAt: 0)
            }
            print(line)
        }
        print("")
    }

    /// Group by task — for each task, all models ranked best-to-worst.
    /// Easier to read when you have many models and many tasks; complements
    /// the cross-table view.
    private static func printByTask(_ rows: [Row]) {
        let tasks = Array(Set(rows.map { $0.task })).sorted()
        for t in tasks {
            print("\n\(t)")
            print(String(repeating: "─", count: t.count + 4))
            let grouped = Dictionary(grouping: rows.filter { $0.task == t }) {
                "\($0.model_name)::\($0.model_step.map(String.init) ?? "")"
            }
            let ranked = grouped.values.compactMap { group -> (Row, RenderSummary)? in
                guard let first = group.first, let summary = summarize(group) else { return nil }
                return (first, summary)
            }.sorted { $0.1.score > $1.1.score }
            for (r, summary) in ranked {
                let star = r.baseline ? "  (baseline)" : ""
                let step = r.model_step.map { " step=\($0)" } ?? ""
                print("  \(render(summary))  \(r.model_name)\(step)\(star)")
            }
        }
        print("")
    }

    private struct RenderSummary {
        let score: Double
        let nExamples: Int
        let stats: EvalGate.PassStats?
    }

    private static func summarize(_ rows: [Row]) -> RenderSummary? {
        guard let first = rows.first else { return nil }
        if rows.count == 1 {
            return RenderSummary(score: first.score, nExamples: first.n_examples,
                                 stats: first.passStats)
        }
        let stats = EvalGate.PassStats(scores: rows.map(\.score))
        return RenderSummary(score: stats.mean, nExamples: first.n_examples,
                             stats: stats)
    }

    private static func ci95HalfWidth(_ stats: EvalGate.PassStats, score: Double) -> Double? {
        guard stats.n > 1 else { return nil }
        return max(abs(stats.ci95High - score), abs(score - stats.ci95Low))
    }

    private static func renderScoreOnly(_ summary: RenderSummary) -> String {
        if let stats = summary.stats, let ci = ci95HalfWidth(stats, score: summary.score) {
            return String(format: "%.3f±%.3f", summary.score, ci)
        }
        return String(format: "%.3f", summary.score)
    }

    private static func render(_ summary: RenderSummary) -> String {
        let score = renderScoreOnly(summary)
        if let k = summary.stats?.n, k > 1 {
            return "\(score)  (n=\(summary.nExamples),k=\(k))"
        }
        return "\(score)  (n=\(summary.nExamples))"
    }

    private static func exitUsage(_ code: Int32 = 2) -> Never {
        print("""
        usage: tinygpt eval-compare <results.jsonl>+ [--by model|step|task]

        Render comparison tables across one or more eval JSONL files. Every
        `tinygpt eval-*` subcommand emits rows in the shared schema (see
        EvalCompare.Row in this file) so cross-model and cross-checkpoint
        comparisons are one command.

        --by model   (default) task × model pivot. "Did we beat baseline X?"
        --by step    pin to one model, show task × training step.
                     "When did this capability emerge?"
        --by task    for each task, all models ranked best-to-worst.

        Example:
          tinygpt eval-compare ~/eval/run-*.jsonl --by model
          tinygpt eval-compare ~/eval/huge-base-v1-timeline.jsonl --by step
        """)
        exit(code)
    }
}
