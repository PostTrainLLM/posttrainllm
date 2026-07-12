import SwiftUI

/// "Runs" workspace — the factory orchestration surfaces that were CLI-only:
/// validate/publish-check a run folder, SQL execution eval, and batch generate.
/// Mirrors TrainHubView's segmented-mode layout.
struct RunsHubView: View {
    enum Mode: String, CaseIterable, Identifiable {
        case factoryRun = "Factory run"
        case sqlEval    = "SQL eval"
        case generate   = "Generate"
        var id: String { rawValue }

        var subtitle: String {
            switch self {
            case .factoryRun: return "Validate or publish-check a runs/<id> folder against the schema + evidence gates."
            case .sqlEval:    return "Execution accuracy of predicted SQL against local SQLite DBs."
            case .generate:   return "Batch-generate completions for a prompt set, composing adapters."
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
                .frame(maxWidth: 460)
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
                case .factoryRun: FactoryRunView()
                case .sqlEval:    SQLEvalView()
                case .generate:   GenerateView()
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
    @State private var action = "validate"
    @State private var reportOnly = true

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
