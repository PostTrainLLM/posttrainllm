import SwiftUI
import AppKit
import TinyGPTCheck

/// "Check model compatibility" workspace (issue #156). Paste a Hugging
/// Face URL → Analyze → read the report → copy next steps or the agent
/// prompt. Renders the same `ModelCheckReport` the `model-check` CLI
/// emits; the check is read-only (metadata only — no downloads, no
/// installs, no execution).
struct ModelCheckView: View {
    @StateObject private var controller = ModelCheckController()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                header
                inputSection
                envOverrideSection
                if controller.isChecking { progressSection }
                if let err = controller.lastError { errorSection(err) }
                if let report = controller.report { reportSections(report) }
            }
            .padding(.horizontal, 32)
            .padding(.vertical, 28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.base)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Check model compatibility")
                .font(.tgDisplay)
                .foregroundStyle(Theme.fg)
            Text("paste a Hugging Face model URL — reports what runs here, what needs changes, and what an agent should investigate · read-only, nothing is installed or run")
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(Theme.muted)
        }
    }

    private var inputSection: some View {
        HStack(spacing: 10) {
            TextField("https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507", text: $controller.input)
                .textFieldStyle(.plain)
                .font(.system(size: 12, design: .monospaced))
                .foregroundStyle(Theme.fg)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(Theme.panel)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line))
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .onSubmit { controller.check() }
            Button("Analyze") { controller.check() }
                .buttonStyle(CLIRunButtonStyle())
                .disabled(controller.isChecking || controller.input.trimmingCharacters(in: .whitespaces).isEmpty)
        }
    }

    private var envOverrideSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle(isOn: $controller.useManualEnv) {
                Text("check a different Mac's specs")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.muted)
            }
            .toggleStyle(.checkbox)
            if controller.useManualEnv {
                HStack(spacing: 10) {
                    CLIField(label: "CHIP", placeholder: "Apple M4 Pro", text: $controller.manualChip)
                    CLIField(label: "RAM GB", placeholder: "48", text: $controller.manualRAMGB)
                    CLIField(label: "FREE DISK GB", placeholder: "200", text: $controller.manualDiskGB)
                    CLIField(label: "MACOS", placeholder: "26.0", text: $controller.manualMacOS)
                }
                Text("environment is marked \"manual\" in the report — the machine running this app is never used as the target")
                    .font(.system(size: 10))
                    .foregroundStyle(Theme.faint)
            }
        }
    }

    private var progressSection: some View {
        HStack(spacing: 10) {
            ProgressView().controlSize(.small)
            Text(controller.stage?.rawValue ?? "Working")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Theme.accent)
            Text("→ \(nextStageHint)")
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.faint)
        }
        .padding(12)
        .background(Theme.panel)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var nextStageHint: String {
        switch controller.stage {
        case .inspectingRepository: return "Checking environment → Preparing report"
        case .checkingEnvironment: return "Preparing report"
        default: return ""
        }
    }

    private func errorSection(_ err: String) -> some View {
        WarningBanner(message: err)
    }

    // MARK: - report

    private func verdictColor(_ v: ModelCheckReport.Verdict) -> Color {
        switch v {
        case .expectedToWork: return Theme.accent
        case .changesRequired: return Theme.warn
        case .unsupportedOnCheckedPath: return Theme.brand
        case .unknown: return Theme.muted
        }
    }

    @ViewBuilder
    private func reportSections(_ r: ModelCheckReport) -> some View {
        verdictBanner(r)
        modelEnvironmentSections(r)
        pathsAndChangesSections(r)
        toolsSection(r)
        evidenceSection(r)
        nextActionSection(r)
    }

    private func verdictBanner(_ r: ModelCheckReport) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                Text(r.verdict.displayName.uppercased())
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundStyle(Theme.base)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(verdictColor(r.verdict))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                Text("\(r.model.id) @ \(r.model.revision)")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(Theme.fg)
            }
            Text(r.verdictSummary)
                .font(.system(size: 12))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.panel)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(verdictColor(r.verdict).opacity(0.4)))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    @ViewBuilder
    private func modelEnvironmentSections(_ r: ModelCheckReport) -> some View {
        section("MODEL") {
            kvRow("task", r.model.task ?? "unknown")
            kvRow("library", r.model.library ?? "unknown")
            kvRow("architectures", r.model.architectures.isEmpty ? "unknown" : r.model.architectures.joined(separator: ", "))
            kvRow("formats", r.model.formats.isEmpty ? "unknown" : r.model.formats.joined(separator: ", "))
            if let v = r.model.selectedVariant { kvRow("variant", v) }
            if r.model.gated { kvRow("gated", "yes — HF_TOKEN required") }
            if let m = r.model.lastModified { kvRow("last modified", m) }
        }

        section("CURRENT SETUP — \(r.environment.source.uppercased())") {
            kvRow("chip", "\(r.environment.chip) (\(r.environment.arch))")
            kvRow("RAM", ModelCheckReport.fmtBytes(r.environment.ramBytes))
            kvRow("disk free", ModelCheckReport.fmtBytes(r.environment.freeDiskBytes))
            kvRow("macOS", r.environment.macOSVersion)
            let found = r.environment.runtimes.filter(\.found)
            if !found.isEmpty {
                kvRow("runtimes", found.map { "\($0.name) \($0.version ?? "")".trimmingCharacters(in: .whitespaces) }.joined(separator: " · "))
            }
            Divider().background(Theme.line)
            kvRow("checked path", r.checkedPath.name)
            labeledText(r.checkedPath.detail)
        }
    }

    @ViewBuilder
    private func pathsAndChangesSections(_ r: ModelCheckReport) -> some View {
        if !r.otherPaths.isEmpty {
            section("OTHER MAC EXECUTION PATHS") {
                ForEach(Array(r.otherPaths.enumerated()), id: \.offset) { _, p in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 8) {
                            Text(p.name)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(Theme.fg)
                            Text(p.status.displayName)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(verdictColor(p.status))
                            Text(p.evidenceKind)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(Theme.faint)
                        }
                        Text(p.detail)
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                        if let s = p.source {
                            Text(s)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(Theme.faint)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }

        if !r.requiredChanges.isEmpty {
            section("REQUIRED CHANGES") {
                ForEach(Array(r.requiredChanges.enumerated()), id: \.offset) { _, c in
                    HStack(alignment: .top, spacing: 8) {
                        Text(c.kind)
                            .font(.system(size: 9, weight: .semibold, design: .monospaced))
                            .foregroundStyle(Theme.warn)
                            .frame(width: 110, alignment: .leading)
                        Text(c.detail + (c.sizeBytes.map { " (\(ModelCheckReport.fmtBytes($0))\(c.estimate ? ", estimate" : ""))" } ?? ""))
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.fg)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func toolsSection(_ r: ModelCheckReport) -> some View {
        if !r.tools.isEmpty {
            section("TOOLS THAT CAN RUN THIS MODEL") {
                ForEach(Array(r.tools.enumerated()), id: \.offset) { _, tool in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 8) {
                            Text(tool.name)
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(tool.applies ? Theme.fg : Theme.faint)
                            Text(tool.applies ? tool.availability.replacingOccurrences(of: "_", with: " ") : "not applicable")
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(toolAvailabilityColor(tool))
                        }
                        Text(tool.detail)
                            .font(.system(size: 11))
                            .foregroundStyle(tool.applies ? Theme.muted : Theme.faint)
                            .fixedSize(horizontal: false, vertical: true)
                        if tool.applies, let command = tool.run {
                            Text(command)
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(Theme.accent)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    private func toolAvailabilityColor(_ tool: ModelCheckReport.ToolOption) -> Color {
        guard tool.applies else { return Theme.faint }
        switch tool.availability {
        case "bundled", "installed": return Theme.accent
        case "not_installed": return Theme.warn
        default: return Theme.muted
        }
    }

    @ViewBuilder
    private func evidenceSection(_ r: ModelCheckReport) -> some View {
        if !r.limitations.isEmpty {
            section("LIMITATIONS") {
                ForEach(r.limitations, id: \.self) { l in
                    Text("• \(l)")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }

        section("EVIDENCE") {
            ForEach(Array(r.evidence.enumerated()), id: \.offset) { _, e in
                VStack(alignment: .leading, spacing: 2) {
                    Text("[\(e.kind)] \(e.detail)")
                        .font(.system(size: 11))
                        .foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(e.source)
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(Theme.faint)
                        .textSelection(.enabled)
                }
                .padding(.vertical, 2)
            }
            kvRow("checked at", r.checkedAt)
        }
    }

    private func nextActionSection(_ r: ModelCheckReport) -> some View {
        section("NEXT ACTION") {
            ForEach(r.nextActions, id: \.self) { a in
                Text("• \(a)")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.fg)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 10) {
                Button("Copy next steps") {
                    copyToPasteboard(r.nextActions.map { "• \($0)" }.joined(separator: "\n"))
                }
                .font(.system(size: 11, design: .monospaced))
                .buttonStyle(.bordered)
                Button("Copy agent prompt") {
                    copyToPasteboard(r.agentPrompt)
                }
                .font(.system(size: 11, design: .monospaced))
                .buttonStyle(.borderedProminent)
                .tint(Theme.accent)
                Button("Copy JSON report") {
                    copyToPasteboard((try? r.encoded()) ?? "")
                }
                .font(.system(size: 11, design: .monospaced))
                .buttonStyle(.bordered)
            }
            .padding(.top, 6)
            Text("the agent prompt carries model, revision, environment, findings, and open questions — paste it into an agent to investigate further")
                .font(.system(size: 10))
                .foregroundStyle(Theme.faint)
        }
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.faint)
                .tracking(1)
            VStack(alignment: .leading, spacing: 6) { content() }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.panel)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private func kvRow(_ key: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(key)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.faint)
                .frame(width: 110, alignment: .leading)
            Text(value)
                .font(.system(size: 11))
                .foregroundStyle(Theme.fg)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func labeledText(_ s: String) -> some View {
        Text(s)
            .font(.system(size: 11))
            .foregroundStyle(Theme.muted)
            .fixedSize(horizontal: false, vertical: true)
    }

    private func copyToPasteboard(_ s: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(s, forType: .string)
    }
}
