import Foundation
#if canImport(CoreML)
import CoreML
#endif

// Shared CLI helpers, consolidated from per-command copies.
//
// Only genuinely identical helpers live here. Intentionally divergent
// formatters (e.g. the abbreviated `formatLargeInt` in HFInspect/HFLoad and
// the many `formatBytes` variants with different units/precision) are left in
// place because they produce different output on purpose.

/// Run an async throwing operation to completion from a synchronous context.
///
/// Bridges async APIs (tokenizer/model loaders) into the synchronous CLI via a
/// `DispatchSemaphore` + detached task. Consolidated from per-command copies of
/// the same semaphore/box/signal boilerplate.
func runBlocking<T>(_ work: @escaping () async throws -> T) throws -> T {
    let sem = DispatchSemaphore(value: 0)
    nonisolated(unsafe) var boxed: T? = nil
    nonisolated(unsafe) var error: Error? = nil
    Task.detached {
        do { boxed = try await work() }
        catch let e { error = e }
        sem.signal()
    }
    sem.wait()
    if let e = error { throw e }
    guard let v = boxed else {
        throw NSError(domain: "posttrainllm.runBlocking", code: 99,
                      userInfo: [NSLocalizedDescriptionKey: "async operation returned nil"])
    }
    return v
}

/// Group-separated integer, e.g. `1234567` → `"1,234,567"`.
func formatLargeInt(_ n: Int) -> String {
    let f = NumberFormatter()
    f.numberStyle = .decimal
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}

/// Index of the first maximum element. Assumes a non-empty input.
func argmax(_ logits: [Float]) -> Int {
    var best = 0
    var bestV = -Float.greatestFiniteMagnitude
    for i in 0..<logits.count where logits[i] > bestV {
        bestV = logits[i]
        best = i
    }
    return best
}

#if canImport(CoreML)
/// Parse a `--compute-units` string into an `MLComputeUnits` value.
func mlComputeUnits(from s: String) -> MLComputeUnits {
    switch s.lowercased() {
    case "ane":  return .cpuAndNeuralEngine
    case "gpu":  return .cpuAndGPU
    case "all":  return .all
    case "cpu":  return .cpuOnly
    default:
        fputs("unknown --compute-units \(s); using ane\n", stderr)
        return .cpuAndNeuralEngine
    }
}
#endif
