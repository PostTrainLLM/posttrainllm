import Foundation
import Darwin

/// Local Mac environment snapshot for model-check. Pure Foundation +
/// sysctl — deliberately no Metal/MLX so the check library stays
/// linkable anywhere (and unit-testable without a GPU).
///
/// Two ways to produce one:
///   - `detect()`   — probe this Mac (chip, RAM, disk, macOS, runtimes)
///   - `manual(...)`— caller-supplied specs, for checking compatibility
///     against a *different* machine than the one running the tool.
///     `source` records which path produced the values, and the report
///     shows it — the web/server's specs must never masquerade as the
///     user's machine.
public struct MacEnvironment: Equatable, Sendable {
    public var chip: String
    public var arch: String
    public var ramBytes: Int64
    public var freeDiskBytes: Int64
    public var macOSVersion: String
    public var source: String                     // "detected" | "manual"
    public var runtimes: [ModelCheckReport.RuntimeProbe]

    public init(chip: String, arch: String, ramBytes: Int64, freeDiskBytes: Int64,
                macOSVersion: String, source: String,
                runtimes: [ModelCheckReport.RuntimeProbe]) {
        self.chip = chip
        self.arch = arch
        self.ramBytes = ramBytes
        self.freeDiskBytes = freeDiskBytes
        self.macOSVersion = macOSVersion
        self.source = source
        self.runtimes = runtimes
    }

    /// Probe the host Mac. Runtime probing shells out to `--version`-style
    /// commands with a short timeout; every probe is best-effort and a
    /// failure records `found: false`, never an error.
    public static func detect() -> MacEnvironment {
        let chip = sysctlString("machdep.cpu.brand_string") ?? "Apple Silicon"
        let arch = sysctlString("hw.machine") ?? "arm64"
        let ram = Int64(ProcessInfo.processInfo.physicalMemory)
        let osVersion = ProcessInfo.processInfo.operatingSystemVersion
        let macOS = "macOS \(osVersion.majorVersion).\(osVersion.minorVersion).\(osVersion.patchVersion)"

        var disk: Int64 = 0
        if let vals = try? URL(fileURLWithPath: NSHomeDirectory())
            .resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]),
           let free = vals.volumeAvailableCapacityForImportantUsage {
            disk = Int64(free)
        }

        return MacEnvironment(
            chip: chip, arch: arch, ramBytes: ram, freeDiskBytes: disk,
            macOSVersion: macOS, source: "detected", runtimes: probeRuntimes())
    }

    /// Caller-supplied specs (UI "check a different Mac" flow, or CLI
    /// flags). Runtime list is empty — we did not probe that machine —
    /// and `source` is "manual" so the report states it.
    public static func manual(chip: String?, ramGB: Int?, diskGB: Int?, macOS: String?) -> MacEnvironment {
        MacEnvironment(
            chip: chip ?? "Apple Silicon (unspecified)",
            arch: "arm64",
            ramBytes: Int64(ramGB ?? 0) * 1_073_741_824,
            freeDiskBytes: Int64(diskGB ?? 0) * 1_073_741_824,
            macOSVersion: macOS ?? "unspecified",
            source: "manual",
            runtimes: [])
    }

    // MARK: - Runtime probes

    /// The bounded set of Mac runtimes that matter for "can this model
    /// execute here": posttrainllm itself, the GGUF runners, the Python
    /// MLX/transformers stack, and LM Studio. Probing is a single
    /// `--version`-style invocation each with a 6s cap — never a model
    /// load, never an install.
    static func probeRuntimes() -> [ModelCheckReport.RuntimeProbe] {
        var out: [ModelCheckReport.RuntimeProbe] = []

        func cli(_ name: String, _ args: [String], _ detail: String) {
            if let r = runProbe(args) {
                // Tools are sloppy about where the version lands —
                // `ollama --version` emits "Warning: could not connect…"
                // ahead of (or around) the version on stdout+stderr.
                // Extract the first version-looking token from anywhere
                // in the output; fall back to the first non-empty line.
                let text = r.out
                let version: String?
                if let m = text.range(of: #"\d+\.\d+[\.\d]*"#, options: .regularExpression) {
                    version = String(text[m])
                } else {
                    version = text.components(separatedBy: "\n")
                        .map { $0.trimmingCharacters(in: .whitespaces) }
                        .first { !$0.isEmpty }
                }
                out.append(.init(name: name, found: true,
                                 version: version,
                                 detail: detail))
            } else {
                out.append(.init(name: name, found: false, version: nil, detail: detail))
            }
        }

        cli("posttrainllm", ["posttrainllm", "--version"], "`posttrainllm --version`")
        cli("ollama", ["ollama", "--version"], "`ollama --version`")
        // llama-cli has no reliable --version (newer builds hang on it);
        // --help exits 0 immediately and still proves the binary works.
        cli("llama.cpp", ["llama-cli", "--help"], "`llama-cli --help`")
        cli("lms (LM Studio)", ["lms", "--version"], "`lms --version`")

        // One python probe reports the whole ML stack via
        // importlib.metadata — versions without importing heavy modules.
        if let r = runProbe(["python3", "-c", """
            import importlib.metadata as m
            pkgs = ["mlx", "mlx-lm", "transformers", "diffusers", "torch", "llama-cpp-python"]
            found = []
            for p in pkgs:
                try: found.append(f"{p}=={m.version(p)}")
                except Exception: pass
            print(";".join(found))
            """]), r.status == 0 {
            let entries = r.out.trimmingCharacters(in: .whitespacesAndNewlines)
                .split(separator: ";").map(String.init).filter { !$0.isEmpty }
            if entries.isEmpty {
                out.append(.init(name: "python3 ML stack", found: false, version: nil,
                                 detail: "python3 present; no mlx/transformers/diffusers distributions"))
            } else {
                out.append(.init(name: "python3 ML stack", found: true,
                                 version: entries.joined(separator: ", "),
                                 detail: "importlib.metadata on python3"))
            }
        } else {
            out.append(.init(name: "python3 ML stack", found: false, version: nil,
                             detail: "no python3 on PATH"))
        }
        return out
    }

    /// Run `<tool> <args>` via /usr/bin/env with a timeout. Returns nil on
    /// launch failure, non-zero exit, or timeout — all "not found".
    static func runProbe(_ args: [String], timeout: TimeInterval = 6) -> (status: Int32, out: String)? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        do { try p.run() } catch { return nil }
        let deadline = Date().addingTimeInterval(timeout)
        while p.isRunning && Date() < deadline { usleep(20_000) }
        if p.isRunning { p.terminate(); return nil }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard p.terminationStatus == 0 else { return nil }
        return (p.terminationStatus, String(decoding: data, as: UTF8.self))
    }

    static func sysctlString(_ name: String) -> String? {
        var size = 0
        guard sysctlbyname(name, nil, &size, nil, 0) == 0, size > 0 else { return nil }
        var buf = [CChar](repeating: 0, count: size)
        guard sysctlbyname(name, &buf, &size, nil, 0) == 0 else { return nil }
        return String(cString: buf)
    }
}
