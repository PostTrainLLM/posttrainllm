import Foundation

/// Pure gate logic for `posttrainllm eval-gate` (B32). Compares a candidate
/// eval run against a stored baseline and decides PASS/FAIL per suite.
///
/// This namespace is intentionally model-free and side-effect-free so the
/// threshold/direction/verdict logic is unit-testable without a GPU or a
/// running server. The CLI wrapper (`Sources/TinyGPT/EvalGate.swift`)
/// handles arg parsing, spec resolution, suite-running, and the exit code;
/// it delegates the actual judgement to `EvalGate.evaluate`.
///
/// V1 scope: gates accuracy-like metrics in [0,1] (BFCL pass rate, τ-bench
/// pass@1, unhappy-path averages). Thresholds are expressed in percentage
/// points. Lower-is-better raw metrics (latency_ms, rss_mb) carry a
/// direction but pp deltas assume a 0..1 score — gating raw-unit metrics is
/// a documented follow-up (see docs/prds/B32-eval-ci-gate.md §"Scope — out").
public enum EvalGate {

    /// Default regression tolerance (percentage points) when a suite
    /// declares none.
    public static let defaultThreshold: Double = 2.0

    public enum Direction: String, Codable, Sendable {
        case higherIsBetter
        case lowerIsBetter
    }

    /// Metric-name heuristic for score direction. Most eval metrics are
    /// higher-is-better; perplexity/loss/latency/memory are lower-is-better.
    public static func direction(for metric: String) -> Direction {
        let m = metric.lowercased()
        let lowerIsBetter = ["ppl", "perplexity", "loss", "nll",
                             "latency_ms", "latency", "wall_seconds",
                             "rss_mb", "rss", "ttft_ms", "ttft",
                             "error_rate", "error", "wer"]
        for needle in lowerIsBetter where m.contains(needle) {
            return .lowerIsBetter
        }
        return .higherIsBetter
    }

    /// Minimal projection of `EvalCompare.Row` (defined in the posttrainllm
    /// executable module). Decodes the same snake_case JSONL; extra keys are
    /// ignored. Kept here so the gate logic lives in a test-target-backed
    /// library rather than the un-testable executable target.
    public struct Row: Codable, Sendable, Hashable {
        public let task: String
        public let subtask: String?
        public let metric: String
        public let score: Double
        public let n_examples: Int
        public let baseline: Bool

        public init(task: String, subtask: String? = nil, metric: String,
                    score: Double, n_examples: Int = 0, baseline: Bool = false) {
            self.task = task
            self.subtask = subtask
            self.metric = metric
            self.score = score
            self.n_examples = n_examples
            self.baseline = baseline
        }

        enum CodingKeys: String, CodingKey {
            case task, subtask, metric, score, n_examples, baseline
        }

        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            task = try c.decode(String.self, forKey: .task)
            subtask = try c.decodeIfPresent(String.self, forKey: .subtask)
            metric = try c.decode(String.self, forKey: .metric)
            score = try c.decode(Double.self, forKey: .score)
            n_examples = try c.decodeIfPresent(Int.self, forKey: .n_examples) ?? 0
            baseline = try c.decodeIfPresent(Bool.self, forKey: .baseline) ?? false
        }

        /// Stable identity for baseline↔candidate matching.
        public var key: String { "\(task)::\(subtask ?? "")::\(metric)" }
    }

    /// One suite the gate runs/compares. `task` is the `EvalCompare.Row`
    /// task to match against (defaults to `name`). `command` is the argv the
    /// CLI runs to produce candidate rows (CLI-only; ignored by `evaluate`).
    public struct SuiteSpec: Codable, Sendable {
        public let name: String
        public let task: String?
        /// Per-suite regression tolerance in percentage points; overrides
        /// the spec default. JSON key: `threshold`.
        public let threshold: Double?
        public let command: [String]?

        public init(name: String, task: String? = nil,
                    threshold: Double? = nil, command: [String]? = nil) {
            self.name = name
            self.task = task
            self.threshold = threshold
            self.command = command
        }

        public var resolvedTask: String { task ?? name }
    }

    /// The gate spec. Lives either in `posttrainllm.project.json` under an
    /// optional `eval` block, or in a standalone `eval-gate.json`.
    public struct Spec: Codable, Sendable {
        public let baseline: String
        /// Default regression tolerance in percentage points. JSON key:
        /// `default_threshold` (snake_case in the project file).
        public let defaultThreshold: Double?
        public let suites: [SuiteSpec]

        public init(baseline: String, defaultThreshold: Double? = nil,
                    suites: [SuiteSpec]) {
            self.baseline = baseline
            self.defaultThreshold = defaultThreshold
            self.suites = suites
        }

        public var resolvedDefaultThreshold: Double {
            defaultThreshold ?? EvalGate.defaultThreshold
        }

        public static let jsonDecoder: JSONDecoder = {
            let d = JSONDecoder()
            d.keyDecodingStrategy = .convertFromSnakeCase
            return d
        }()
    }

    public enum Verdict: String, Codable, Sendable {
        case pass
        case fail
        case missing  // no matching baseline row — informational, not a fail
    }

    public struct SuiteResult: Codable, Sendable {
        public let name: String
        public let task: String
        public let subtask: String?
        public let metric: String
        public let direction: Direction
        public let baselineScore: Double?
        public let candidateScore: Double?
        /// Present when the candidate score is a K-pass mean. Carries the
        /// underlying trial scores so a gate result is auditable, not just a
        /// collapsed number.
        public let candidateStats: PassStats?
        /// Direction-adjusted delta in percentage points. Positive = better.
        public let deltaPP: Double?
        public let thresholdPP: Double
        public let verdict: Verdict
    }

    public struct PassStats: Codable, Sendable, Hashable {
        public let n: Int
        public let trialScores: [Double]
        public let mean: Double
        public let stdev: Double
        public let stderr: Double
        public let ci95Low: Double
        public let ci95High: Double

        public init(scores: [Double]) {
            let clean = scores.filter { $0.isFinite }
            self.n = clean.count
            self.trialScores = clean
            if clean.isEmpty {
                self.mean = 0
                self.stdev = 0
                self.stderr = 0
                self.ci95Low = 0
                self.ci95High = 0
                return
            }
            let mean = clean.reduce(0, +) / Double(clean.count)
            let variance: Double
            if clean.count > 1 {
                variance = clean.reduce(0) { $0 + pow($1 - mean, 2) } / Double(clean.count - 1)
            } else {
                variance = 0
            }
            let stdev = sqrt(variance)
            let stderr = stdev / sqrt(Double(clean.count))
            let ci = 1.96 * stderr
            self.mean = mean
            self.stdev = stdev
            self.stderr = stderr
            self.ci95Low = mean - ci
            self.ci95High = mean + ci
        }
    }

    public struct AgentEvalBudget: Codable, Sendable, Hashable {
        public let maxSteps: Int?
        public let sandboxCpus: Double?
        public let sandboxRamMb: Int?
        public let temperature: Double?
        public let topP: Double?
        public let samplingSeed: Int?
        public let infraPatches: [String]

        public init(maxSteps: Int? = nil,
                    sandboxCpus: Double? = nil,
                    sandboxRamMb: Int? = nil,
                    temperature: Double? = nil,
                    topP: Double? = nil,
                    samplingSeed: Int? = nil,
                    infraPatches: [String] = []) {
            self.maxSteps = maxSteps
            self.sandboxCpus = sandboxCpus
            self.sandboxRamMb = sandboxRamMb
            self.temperature = temperature
            self.topP = topP
            self.samplingSeed = samplingSeed
            self.infraPatches = infraPatches
        }

        enum CodingKeys: String, CodingKey {
            case maxSteps = "max_steps"
            case sandboxCpus = "sandbox_cpus"
            case sandboxRamMb = "sandbox_ram_mb"
            case temperature
            case topP = "top_p"
            case samplingSeed = "sampling_seed"
            case infraPatches = "infra_patches"
        }
    }

    public struct AgentEvalProtocol: Codable, Sendable, Hashable {
        public let passes: Int
        public let budget: AgentEvalBudget?

        public init(passes: Int = 1, budget: AgentEvalBudget? = nil) {
            self.passes = max(1, passes)
            self.budget = budget
        }
    }

    public struct Report: Codable, Sendable {
        public let suites: [SuiteResult]
        public let passed: Bool
        public let failedCount: Int
        public let missingCount: Int
        public let evalProtocol: AgentEvalProtocol?

        enum CodingKeys: String, CodingKey {
            case suites, passed, failedCount, missingCount
            case evalProtocol = "protocol"
        }

        public init(suites: [SuiteResult], evalProtocol: AgentEvalProtocol? = nil) {
            self.suites = suites
            self.failedCount = suites.filter { $0.verdict == .fail }.count
            self.missingCount = suites.filter { $0.verdict == .missing }.count
            self.passed = failedCount == 0
            self.evalProtocol = evalProtocol
        }
    }

    /// Compare candidate rows against baseline rows.
    ///
    /// - For each suite in `spec.suites`, every candidate row whose `task`
    ///   matches the suite is judged against the same-key baseline row.
    /// - If `spec.suites` is empty, every candidate row is gated under the
    ///   default threshold (whole-run gate).
    /// - A regression worse than the (direction-adjusted) suite threshold is
    ///   a `.fail`. A missing baseline row is `.missing` (does not fail the
    ///   gate — you can't regress against a number you never had).
    public static func evaluate(baseline: [Row], candidate: [Row], spec: Spec) -> Report {
        evaluate(baseline: baseline, candidate: candidate, candidateStats: [:], spec: spec)
    }

    public static func evaluate(baseline: [Row],
                                candidate: [Row],
                                candidateStats: [String: PassStats],
                                spec: Spec,
                                evalProtocol: AgentEvalProtocol? = nil) -> Report {
        let baseByKey = Dictionary(baseline.map { ($0.key, $0) },
                                   uniquingKeysWith: { _, b in b })

        // task → threshold; tasks not named in the spec fall back to default.
        var thresholdByTask: [String: Double] = [:]
        var gatedTasks = Set<String>()
        for s in spec.suites {
            thresholdByTask[s.resolvedTask] = s.threshold ?? spec.resolvedDefaultThreshold
            gatedTasks.insert(s.resolvedTask)
        }
        let nameByTask = Dictionary(spec.suites.map { ($0.resolvedTask, $0.name) },
                                    uniquingKeysWith: { a, _ in a })

        let gateAll = spec.suites.isEmpty
        var results: [SuiteResult] = []
        for cand in candidate.sorted(by: { $0.key < $1.key }) {
            guard gateAll || gatedTasks.contains(cand.task) else { continue }
            let threshold = thresholdByTask[cand.task] ?? spec.resolvedDefaultThreshold
            let dir = direction(for: cand.metric)
            let base = baseByKey[cand.key]
            let verdict: Verdict
            var deltaPP: Double? = nil
            if let base {
                let raw = cand.score - base.score
                let adjusted = dir == .higherIsBetter ? raw : -raw
                let pp = adjusted * 100.0
                deltaPP = pp
                verdict = pp < -threshold ? .fail : .pass
            } else {
                verdict = .missing
            }
            results.append(SuiteResult(
                name: nameByTask[cand.task] ?? cand.task,
                task: cand.task,
                subtask: cand.subtask,
                metric: cand.metric,
                direction: dir,
                baselineScore: base?.score,
                candidateScore: cand.score,
                candidateStats: candidateStats[cand.key],
                deltaPP: deltaPP,
                thresholdPP: threshold,
                verdict: verdict))
        }
        return Report(suites: results, evalProtocol: evalProtocol)
    }

    /// Collapse rows sharing a key into one row whose score is the mean.
    /// The `--passes K` path runs each suite K times and gates on the
    /// average rather than the last run, so single-run noise can't flip the
    /// verdict. Input order of first-seen keys is preserved.
    public static func averagedByKey(_ rows: [Row]) -> [Row] {
        summarizedByKey(rows).rows
    }

    /// Collapse repeated rows into mean rows and return per-key uncertainty
    /// stats for keys with multiple trials. Used by `eval-gate --passes K`.
    public static func summarizedByKey(_ rows: [Row]) -> (rows: [Row], stats: [String: PassStats]) {
        var order: [String] = []
        var groups: [String: [Row]] = [:]
        for r in rows {
            if groups[r.key] == nil { order.append(r.key) }
            groups[r.key, default: []].append(r)
        }
        var stats: [String: PassStats] = [:]
        let averaged = order.map { key in
            let g = groups[key]!
            let passStats = PassStats(scores: g.map(\.score))
            if g.count > 1 { stats[key] = passStats }
            let first = g[0]
            return Row(task: first.task, subtask: first.subtask, metric: first.metric,
                       score: passStats.mean, n_examples: first.n_examples, baseline: first.baseline)
        }
        return (averaged, stats)
    }

    // MARK: - JSONL IO

    /// Decode an `EvalCompare.Row` JSONL file into gate rows. Lines that
    /// don't parse are skipped (matches `EvalCompare.run` leniency).
    public static func loadRows(fromJSONLAt path: String) throws -> [Row] {
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        guard let text = String(data: data, encoding: .utf8) else { return [] }
        let dec = JSONDecoder()
        var rows: [Row] = []
        for line in text.split(separator: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.isEmpty, let lineData = trimmed.data(using: .utf8) else { continue }
            if let row = try? dec.decode(Row.self, from: lineData) { rows.append(row) }
        }
        return rows
    }
}
