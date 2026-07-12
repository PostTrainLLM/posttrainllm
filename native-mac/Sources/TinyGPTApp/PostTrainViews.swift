import SwiftUI

/// Preference-tuning (DPO / SimPO / ORPO / KTO) as a real GUI flow over the CLI.
/// Replaces the old DPOStubView — builds the `posttrainllm dpo` invocation from
/// the form and streams training output.
struct DPOView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var base = ""
    @State private var data = ""
    @State private var out = ""
    @State private var lossType = "dpo"
    @State private var rank = "4"
    @State private var alpha = "8"
    @State private var beta = "0.1"
    @State private var steps = "50"
    @State private var lr = "5e-6"
    @State private var template = "chatml"

    private let lossTypes = ["dpo", "simpo", "orpo", "kto"]

    private var args: [String] {
        ["dpo", base,
         "--data", data, "--out", out,
         "--loss-type", lossType, "--template", template,
         "--rank", rank, "--alpha", alpha, "--beta", beta,
         "--steps", steps, "--lr", lr]
    }
    private var canRun: Bool {
        !base.isEmpty && !data.isEmpty && !out.isEmpty && !runner.isRunning
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(
                title: "DPO — preference tuning",
                subtitle: "Chosen-vs-rejected pairs after SFT. `dpo`/`kto` load a frozen reference; `simpo`/`orpo` are reference-free. Reference anchoring is the cure for policy collapse."
            )
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    CLIPathField(label: "Base model (HF dir / .tinygpt)", placeholder: "path to base", path: $base, chooseDirectories: true)
                    CLIPathField(label: "Preference data (.jsonl)", placeholder: "prompt / chosen / rejected", path: $data)
                    CLIPathField(label: "Output adapter (.lora)", placeholder: "where to write", path: $out, save: true)
                    HStack(alignment: .bottom, spacing: 10) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("loss-type").font(.system(size: 10, design: .monospaced)).foregroundStyle(Theme.faint)
                            Picker("", selection: $lossType) {
                                ForEach(lossTypes, id: \.self) { Text($0).tag($0) }
                            }
                            .labelsHidden().frame(width: 130)
                        }
                        CLIField(label: "template", placeholder: "chatml", text: $template).frame(width: 130)
                    }
                    HStack(spacing: 10) {
                        CLIField(label: "rank", placeholder: "4", text: $rank).frame(width: 74)
                        CLIField(label: "alpha", placeholder: "8", text: $alpha).frame(width: 74)
                        CLIField(label: "beta", placeholder: "0.1", text: $beta).frame(width: 84)
                        CLIField(label: "steps", placeholder: "50", text: $steps).frame(width: 84)
                        CLIField(label: "lr", placeholder: "5e-6", text: $lr).frame(width: 100)
                    }
                }
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 170)
        }
        .padding(20)
        .background(Theme.base)
    }
}

/// Knowledge distillation (teacher → student) as a real GUI flow over the CLI.
/// Replaces the old DistillStubView.
struct DistillView: View {
    @StateObject private var runner = CLICommandRunner()
    @State private var student = ""
    @State private var teacher = ""
    @State private var data = ""
    @State private var out = ""
    @State private var mode = "soft"
    @State private var temperature = "4.0"
    @State private var alpha = "0.7"
    @State private var steps = "1000"
    @State private var lr = "1e-4"

    private let modes = ["soft", "hard"]

    private var args: [String] {
        ["distill", student,
         "--teacher", teacher, "--data", data, "--out", out,
         "--mode", mode, "--temperature", temperature, "--alpha", alpha,
         "--steps", steps, "--lr", lr]
    }
    private var canRun: Bool {
        !student.isEmpty && !teacher.isEmpty && !data.isEmpty && !out.isEmpty && !runner.isRunning
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            CommandHeader(
                title: "Distill — teacher → student",
                subtitle: "soft = KL(teacher logits) + NLL; hard = NLL on teacher-generated text. Compress a stronger teacher into a measured specialist."
            )
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    CLIPathField(label: "Student (base to train)", placeholder: ".tinygpt / HF dir", path: $student, chooseDirectories: true)
                    CLIPathField(label: "Teacher (frozen)", placeholder: ".tinygpt / HF dir", path: $teacher, chooseDirectories: true)
                    CLIPathField(label: "Corpus / data", placeholder: "UTF-8 text or .jsonl", path: $data)
                    CLIPathField(label: "Output (.tinygpt)", placeholder: "distilled student", path: $out, save: true)
                    HStack(alignment: .bottom, spacing: 10) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("mode").font(.system(size: 10, design: .monospaced)).foregroundStyle(Theme.faint)
                            Picker("", selection: $mode) {
                                ForEach(modes, id: \.self) { Text($0).tag($0) }
                            }
                            .labelsHidden().frame(width: 110)
                        }
                        CLIField(label: "temperature", placeholder: "4.0", text: $temperature).frame(width: 100)
                        CLIField(label: "alpha (KL wt)", placeholder: "0.7", text: $alpha).frame(width: 100)
                        CLIField(label: "steps", placeholder: "1000", text: $steps).frame(width: 90)
                        CLIField(label: "lr", placeholder: "1e-4", text: $lr).frame(width: 100)
                    }
                }
            }
            CommandControls(runner: runner, canRun: canRun, run: { runner.run(args) })
            CLILogView(log: runner.log).frame(minHeight: 170)
        }
        .padding(20)
        .background(Theme.base)
    }
}

/// Shared header for CLI command forms.
struct CommandHeader: View {
    let title: String
    let subtitle: String
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.fg)
            Text(subtitle)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Shared Run/Stop controls + exit-status chip for CLI command forms.
struct CommandControls: View {
    @ObservedObject var runner: CLICommandRunner
    let canRun: Bool
    let run: () -> Void
    var body: some View {
        HStack(spacing: 12) {
            if runner.isRunning {
                Button("Stop") { runner.cancel() }
                    .buttonStyle(CLIRunButtonStyle(color: Theme.danger))
            } else {
                Button("Run") { run() }
                    .buttonStyle(CLIRunButtonStyle())
                    .disabled(!canRun)
                    .opacity(canRun ? 1 : 0.45)
            }
            if let code = runner.exitCode {
                Text(code == 0 ? "✓ exit 0" : "✗ exit \(code)")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(code == 0 ? Theme.accent : Theme.danger)
            }
            if let err = runner.lastError {
                Text(err).font(.system(size: 11, design: .monospaced)).foregroundStyle(Theme.danger)
            }
            Spacer()
        }
    }
}
