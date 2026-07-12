import Foundation
import SwiftUI
import AppKit

/// Shared runner that shells out to the `posttrainllm` CLI and streams its
/// stdout/stderr into a log. Factors out the locate + Process + Pipe pattern
/// that was duplicated across controllers, so new command surfaces (DPO,
/// distill, factory-run, eval-sql) reuse one implementation.
@MainActor
final class CLICommandRunner: ObservableObject {
    @Published var log: String = ""
    @Published var isRunning: Bool = false
    @Published var exitCode: Int32? = nil
    @Published var lastError: String? = nil

    private var process: Process?

    /// Run `posttrainllm <args…>`. `args` must NOT include the executable path.
    func run(_ args: [String]) {
        guard !isRunning else { return }
        guard let cli = Self.locateCLI() else {
            let msg = "posttrainllm CLI not found. Build it first:\n    cd native-mac && swift build --product posttrainllm\n"
            lastError = "CLI not found"
            log = "✗ " + msg
            return
        }
        log = "$ posttrainllm \(args.joined(separator: " "))\n\n"
        exitCode = nil
        lastError = nil
        isRunning = true

        let p = Process()
        p.executableURL = cli
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let chunk = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in self?.log += chunk }
        }
        p.terminationHandler = { [weak self] proc in
            let status = proc.terminationStatus
            Task { @MainActor in
                pipe.fileHandleForReading.readabilityHandler = nil
                self?.exitCode = status
                self?.isRunning = false
                self?.process = nil
                self?.log += "\n— exit \(status) —\n"
            }
        }
        do {
            try p.run()
            process = p
        } catch {
            isRunning = false
            lastError = "launch failed: \(error)"
            log += "✗ launch failed: \(error)\n"
        }
    }

    func cancel() { process?.terminate() }

    /// Locate the built CLI. Checks bundle-relative build dirs (walking up),
    /// the current working directory, and `/usr/local/bin`. Accepts release OR
    /// debug builds — SQL eval requires the debug build's multi-LoRA path.
    static func locateCLI() -> URL? {
        let fm = FileManager.default
        let rels = [
            "arm64-apple-macosx/release/posttrainllm",
            "arm64-apple-macosx/debug/posttrainllm",
            "release/posttrainllm",
            "debug/posttrainllm",
        ]
        var roots: [URL] = []
        if let exec = Bundle.main.executableURL {
            var dir = exec.deletingLastPathComponent()
            for _ in 0..<8 { roots.append(dir); dir = dir.deletingLastPathComponent() }
        }
        roots.append(URL(fileURLWithPath: fm.currentDirectoryPath))
        for root in roots {
            for sub in [".build", "native-mac/.build"] {
                for rel in rels {
                    let c = root.appendingPathComponent(sub).appendingPathComponent(rel)
                    if fm.isExecutableFile(atPath: c.path) { return c }
                }
            }
        }
        let usr = URL(fileURLWithPath: "/usr/local/bin/posttrainllm")
        return fm.isExecutableFile(atPath: usr.path) ? usr : nil
    }
}

/// Compact labeled text field used by the CLI command forms.
struct CLIField: View {
    let label: String
    let placeholder: String
    @Binding var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.faint)
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(Theme.fg)
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .background(Theme.panel)
                .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.line))
        }
    }
}

/// Labeled path field with a Browse… button (open or save panel).
struct CLIPathField: View {
    let label: String
    let placeholder: String
    @Binding var path: String
    var chooseDirectories: Bool = false
    var save: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(Theme.faint)
            HStack(spacing: 6) {
                TextField(placeholder, text: $path)
                    .textFieldStyle(.plain)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.fg)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 6)
                    .background(Theme.panel)
                    .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.line))
                Button("Browse…") { browse() }
                    .font(.system(size: 10, design: .monospaced))
                    .buttonStyle(.plain)
                    .foregroundStyle(Theme.accent)
            }
        }
    }

    private func browse() {
        if save {
            let panel = NSSavePanel()
            panel.canCreateDirectories = true
            if panel.runModal() == .OK, let url = panel.url { path = url.path }
        } else {
            let panel = NSOpenPanel()
            panel.canChooseFiles = !chooseDirectories
            panel.canChooseDirectories = chooseDirectories
            panel.allowsMultipleSelection = false
            if panel.runModal() == .OK, let url = panel.url { path = url.path }
        }
    }
}

/// Filled action button used to launch a CLI command.
struct CLIRunButtonStyle: ButtonStyle {
    var color: Color = Theme.accent
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .semibold, design: .monospaced))
            .foregroundStyle(Theme.base)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(color.opacity(configuration.isPressed ? 0.75 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 5))
    }
}

/// Scrolling monospaced output panel shared by the CLI command forms.
struct CLILogView: View {
    let log: String
    var body: some View {
        ScrollView {
            Text(log.isEmpty ? "output appears here" : log)
                .font(.system(size: 10.5, design: .monospaced))
                .foregroundStyle(log.isEmpty ? Theme.faint : Theme.muted)
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding(12)
        }
        .background(Theme.base)
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line))
    }
}
