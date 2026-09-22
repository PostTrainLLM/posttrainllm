import Foundation
import Darwin

/// Bounded subprocess plumbing for model-run. Two shapes only:
///   - `capture`  — run with pipes, hard-timeout kill, output returned.
///                  Used for every verification step so a hung download
///                  or load dies here instead of pinning the terminal.
///   - `attached` — run wired to the real stdin/stdout so an interactive
///                  session (`--chat`) owns the terminal. Returns the
///                  exit status so the caller can clean up daemons it
///                  spawned; model-run never exits leaving its own
///                  processes behind.
public enum Subprocess {

    public struct Result: Sendable {
        public let status: Int32
        public let stdout: String
        public let stderr: String
        public let timedOut: Bool
        public let durationMS: Int
    }

    /// Run `argv` (via /usr/bin/env, so PATH resolution matches the
    /// shell), capturing stdout/stderr with a watchdog. On timeout the
    /// child is SIGKILLed. Pipes are drained on background threads — a
    /// child that fills the 64 KB pipe buffer (ollama's pull progress
    /// exceeds it easily) would otherwise deadlock against
    /// waitUntilExit.
    public static func capture(_ argv: [String],
                               timeout: TimeInterval) -> Result {
        let startedAt = Date()
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = argv
        let out = Pipe(), err = Pipe()
        p.standardOutput = out
        p.standardError = err
        do { try p.run() } catch {
            return Result(status: -1, stdout: "",
                          stderr: "spawn failed: \(error)", timedOut: false,
                          durationMS: Int(Date().timeIntervalSince(startedAt) * 1_000))
        }
        final class Box: @unchecked Sendable { var d = Data() }
        let ob = Box(), eb = Box()
        let g = DispatchGroup()
        g.enter(); DispatchQueue.global().async {
            ob.d = out.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        g.enter(); DispatchQueue.global().async {
            eb.d = err.fileHandleForReading.readDataToEndOfFile(); g.leave() }
        var timedOut = false
        let deadline = Date().addingTimeInterval(timeout)
        while p.isRunning {
            if Date() > deadline {
                timedOut = true
                kill(p.processIdentifier, SIGKILL)
                break
            }
            Thread.sleep(forTimeInterval: 0.2)
        }
        p.waitUntilExit()
        g.wait()
        return Result(status: p.terminationStatus,
                      stdout: String(decoding: ob.d, as: UTF8.self),
                      stderr: String(decoding: eb.d, as: UTF8.self),
                      timedOut: timedOut,
                      durationMS: Int(Date().timeIntervalSince(startedAt) * 1_000))
    }

    /// Run `argv` attached to the real terminal (interactive sessions).
    /// Returns the exit status — callers that spawned a supporting
    /// daemon terminate it after this returns.
    @discardableResult
    public static func attached(_ argv: [String]) -> Int32 {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = argv
        guard (try? p.run()) != nil else { return -1 }
        p.waitUntilExit()
        return p.terminationStatus
    }

    /// Spawn a detached background process (used for `ollama serve`).
    /// Output goes to /dev/null; the returned Process is the caller's
    /// to terminate.
    public static func daemon(_ argv: [String]) -> Process? {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        p.arguments = argv
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        guard (try? p.run()) != nil else { return nil }
        return p
    }
}
