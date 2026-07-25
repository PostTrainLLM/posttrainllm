import SwiftUI
import TinyGPTIO

/// "Runs" workspace — the factory orchestration surfaces that were CLI-only:
/// validate/publish-check a run folder, SQL execution eval, and batch generate.
/// Mirrors TrainHubView's segmented-mode layout.
struct RunsHubView: View {
    enum Mode: String, CaseIterable, Identifiable {
        case factoryRun  = "Factory run"
        case evalGate    = "Eval gate"
        case evalCompare = "Eval compare"
        case sqlEval     = "SQL eval"
        case generate    = "Generate"
        var id: String { rawValue }

        var subtitle: String {
            switch self {
            case .factoryRun:  return "Validate or publish-check a runs/<id> folder against the schema + evidence gates."
            case .evalGate:    return "Score a candidate against a frozen spec + baseline; exits non-zero on regression."
            case .evalCompare: return "Group/sort eval result JSONLs by model, step, or task."
            case .sqlEval:     return "Execution accuracy of predicted SQL against local SQLite DBs."
            case .generate:    return "Batch-generate completions for a prompt set, composing adapters."
            }
        }
    }

    @State private var mode: Mode = .factoryRun

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 8) {
                Picker("", selection: $mode) {
                    ForEach(Mode.allCases) { m in Text(m.rawValue).tag(m) }
                }
                .pickerStyle(.segmented)
                .frame(maxWidth: 620)
                Text(mode.subtitle)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 14)
            .background(Theme.panel.opacity(0.5))
            .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .bottom)

            Group {
                switch mode {
                case .factoryRun:  FactoryRunView()
                case .evalGate:    EvalGateView()
                case .evalCompare: EvalCompareView()
                case .sqlEval:     SQLEvalView()
                case .generate:    GenerateView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(Theme.base)
    }
}

/// `posttrainllm factory-run validate|publish-check runs/<id>`.
struct FactoryRunView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var runDir = ""
    @State private var runRoot = "runs"
    @State private var action = "validate"
    @State private var reportOnly = true
    @State private var discovered: [FactoryRunLifecycle.RunRecord] = []
    @State private var discoveryError = ""

    private let actions = ["validate", "publish-check"]

    private var args: [String] {
        var a = ["factory-run", action]
        if action == "publish-check" && reportOnly { a.append("--allow-report-only") }
        a.append(runDir)
        return a
    }
    private var canRun: Bool { !runDir.isEmpty && !runner.isRunning }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(title: "Factory run — validate / publish-check",
                          subtitle: "Point at a runs/<id> folder. validate = typed schema; publish-check = full evidence gates (report-only allows unshipped candidates).")
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .bottom, spacing: 8) {
                    CLIPathField(label: "Run root", placeholder: "runs", path: $runRoot,
                                 chooseDirectories: true)
                    Button("Refresh") { refreshDiscovery() }
                        .buttonStyle(.bordered)
                }
                if !discoveryError.isEmpty {
                    Text(discoveryError)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.red)
                }
                if !discovered.isEmpty {
                    ScrollView(.horizontal) {
                        HStack(spacing: 8) {
                            ForEach(discovered) { record in
                                Button {
                                    runDir = URL(fileURLWithPath: runRoot)
                                        .appendingPathComponent(record.relativeRunPath).path
                                } label: {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(record.status.runId)
                                        Text("\(record.status.phase.rawValue) · r\(record.status.revision)"
                                             + (record.isStale ? " · stale" : ""))
                                            .foregroundStyle(record.isStale ? .orange : Theme.muted)
                                    }
                                    .font(.system(size: 10, design: .monospaced))
                                }
                                .buttonStyle(.bordered)
                            }
                        }
                    }
                }
            }
            CLIPathField(label: "Run folder (runs/<id>)", placeholder: "path to run directory", path: $runDir, chooseDirectories: true)
            HStack(alignment: .bottom, spacing: 14) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("action").font(.system(size: 10, design: .monospaced)).foregroundStyle(Theme.faint)
                    Picker("", selection: $action) {
                        ForEach(actions, id: \.self) { Text($0).tag($0) }
                    }.labelsHidden().frame(width: 180)
                }
                if action == "publish-check" {
                    Toggle("--allow-report-only", isOn: $reportOnly)
                        .toggleStyle(.checkbox)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Theme.muted)
                }
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 200)
        }
        .padding(20)
        .background(Theme.base)
    }

    private func refreshDiscovery() {
        do {
            discovered = try FactoryRunLifecycle.list(
                root: URL(fileURLWithPath: runRoot)
            )
            discoveryError = ""
        } catch {
            discovered = []
            discoveryError = "Run discovery failed: \(error)"
        }
    }
}

/// `posttrainllm eval-gate --spec <spec> --candidate <model> [--baseline …]`.
struct EvalGateView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var spec = ""
    @State private var candidate = ""
    @State private var baseline = ""
    @State private var out = ""
    @State private var threshold = ""
    @State private var passes = "1"
    @State private var updateBaseline = false

    private var args: [String] {
        var a = ["eval-gate", "--spec", spec, "--candidate", candidate]
        if !baseline.isEmpty { a += ["--baseline", baseline] }
        if !out.isEmpty { a += ["--out", out] }
        if !threshold.isEmpty { a += ["--threshold", threshold] }
        if !passes.isEmpty && passes != "1" { a += ["--passes", passes] }
        if updateBaseline { a.append("--update-baseline") }
        return a
    }
    private var canRun: Bool { !spec.isEmpty && !candidate.isEmpty && !runner.isRunning }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(title: "Eval gate — frozen spec vs candidate",
                          subtitle: "Runs the gate spec against the candidate and compares to a frozen baseline. Non-zero exit = regression.")
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    CLIPathField(label: "Gate spec (.json)", placeholder: "eval-gate spec", path: $spec)
                    CLIPathField(label: "Candidate (model / adapter)", placeholder: "candidate to gate", path: $candidate, chooseDirectories: true)
                    CLIPathField(label: "Baseline (optional override)", placeholder: "frozen baseline", path: $baseline, chooseDirectories: true)
                    CLIPathField(label: "Out (optional)", placeholder: "results json", path: $out, save: true)
                    HStack(spacing: 10) {
                        CLIField(label: "threshold", placeholder: "e.g. 0.9", text: $threshold).frame(width: 110)
                        CLIField(label: "passes", placeholder: "1", text: $passes).frame(width: 80)
                        Toggle("--update-baseline", isOn: $updateBaseline)
                            .toggleStyle(.checkbox)
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(Theme.muted)
                    }
                }
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 150)
        }
        .padding(20)
        .background(Theme.base)
    }
}

/// `posttrainllm eval-compare <results.jsonl>+ [--by model|step|task]`.
struct EvalCompareView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var resultsA = ""
    @State private var resultsB = ""
    @State private var by = "model"

    private let bys = ["model", "step", "task"]

    private var args: [String] {
        var a = ["eval-compare", resultsA]
        if !resultsB.isEmpty { a.append(resultsB) }
        a += ["--by", by]
        return a
    }
    private var canRun: Bool { !resultsA.isEmpty && !runner.isRunning }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(title: "Eval compare — group result JSONLs",
                          subtitle: "Compare one or more eval result files, grouped by model, step, or task.")
            CLIPathField(label: "Results 1 (.jsonl)", placeholder: "eval results", path: $resultsA)
            CLIPathField(label: "Results 2 (.jsonl, optional)", placeholder: "second file", path: $resultsB)
            VStack(alignment: .leading, spacing: 3) {
                Text("group by").font(.system(size: 10, design: .monospaced)).foregroundStyle(Theme.faint)
                Picker("", selection: $by) {
                    ForEach(bys, id: \.self) { Text($0).tag($0) }
                }.labelsHidden().frame(width: 200)
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 200)
        }
        .padding(20)
        .background(Theme.base)
    }
}

/// `posttrainllm eval-sql <preds.jsonl> --db-dir <dbs>`.
struct SQLEvalView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var preds = ""
    @State private var dbDir = ""

    private var args: [String] { ["eval-sql", preds, "--db-dir", dbDir] }
    private var canRun: Bool { !preds.isEmpty && !dbDir.isEmpty && !runner.isRunning }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(title: "SQL eval — execution accuracy",
                          subtitle: "Scores predicted_sql vs gold by executing both against the DBs (exact-match reported too).")
            CLIPathField(label: "Predictions (.jsonl)", placeholder: "rows with predicted_sql / gold_sql / db", path: $preds)
            CLIPathField(label: "DB dir", placeholder: "folder of SQLite DBs", path: $dbDir, chooseDirectories: true)
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 220)
        }
        .padding(20)
        .background(Theme.base)
    }
}

/// `posttrainllm generate <model> [--lora …] --data <jsonl> --out <jsonl> …`.
struct GenerateView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var model = ""
    @State private var loraA = ""
    @State private var loraB = ""
    @State private var data = ""
    @State private var out = ""
    @State private var promptField = "prompt"
    @State private var outField = "predicted_sql"
    @State private var maxTokens = "72"

    private var args: [String] {
        var a = ["generate", model]
        if !loraA.isEmpty { a += ["--lora", loraA] }
        if !loraB.isEmpty { a += ["--lora", loraB] }
        a += ["--data", data, "--prompt-field", promptField, "--out-field", outField,
              "--max-tokens", maxTokens, "--out", out]
        return a
    }
    private var canRun: Bool { !model.isEmpty && !data.isEmpty && !out.isEmpty && !runner.isRunning }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(title: "Generate — batch completions",
                          subtitle: "Compose up to two adapters (e.g. --lora sft --lora dpo). Writes one row per prompt to the output JSONL.")
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    CLIPathField(label: "Base model (HF dir / .tinygpt)", placeholder: "path to base", path: $model, chooseDirectories: true)
                    CLIPathField(label: "Adapter 1 (.lora, optional)", placeholder: "e.g. SFT adapter", path: $loraA)
                    CLIPathField(label: "Adapter 2 (.lora, optional)", placeholder: "e.g. DPO adapter", path: $loraB)
                    CLIPathField(label: "Prompts (.jsonl)", placeholder: "input rows", path: $data)
                    CLIPathField(label: "Output (.jsonl)", placeholder: "where to write completions", path: $out, save: true)
                    HStack(spacing: 10) {
                        CLIField(label: "prompt-field", placeholder: "prompt", text: $promptField).frame(width: 130)
                        CLIField(label: "out-field", placeholder: "predicted_sql", text: $outField).frame(width: 150)
                        CLIField(label: "max-tokens", placeholder: "72", text: $maxTokens).frame(width: 100)
                    }
                }
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 150)
        }
        .padding(20)
        .background(Theme.base)
    }
}
