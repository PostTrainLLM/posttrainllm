// B13 — iterate a training-run checkpoint history for interp-replay. Pure
// filename → step parsing + ordering (testable); the actual model loading +
// probe execution live in the CLI (and reuse the shipped probe code).
import Foundation

public enum CheckpointBatchLoader {

    /// Parse the training step from a history filename like
    /// "run.step-1500.tinygpt" → 1500. nil when there's no `step-N` marker.
    public static func parseStep(_ filename: String) -> Int? {
        guard let r = filename.range(of: "step-") else { return nil }
        let digits = filename[r.upperBound...].prefix { $0.isNumber }
        return digits.isEmpty ? nil : Int(digits)
    }

    /// Map filenames to `(step, file)` ordered by step; entries without a
    /// `step-N` marker are dropped (the final/no-step checkpoint isn't a
    /// timeline point).
    public static func ordered(_ filenames: [String]) -> [(step: Int, file: String)] {
        filenames.compactMap { f in parseStep(f).map { (step: $0, file: f) } }
            .sorted { $0.step < $1.step }
    }
}
