// B5 — cloud-escalation training signal: label rollouts for "should I defer
// to cloud?" and score a defer classifier. Pure logic (no MLX, no network) so
// the labeling rule and the eval metrics are unit-testable; the SFT run and the
// cloud teacher that produces the outcomes live outside.
import Foundation

public enum EscalationLabel: String, Sendable {
    case escalate    // local was wrong, cloud fixed it → teach defer
    case keepLocal   // local was right → teach don't-defer
    case drop        // ambiguous (local wrong, cloud no better) → exclude
}

public enum EscalationLabeling {

    /// Label one turn given outcomes. `cloudCorrect == nil` means cloud wasn't
    /// consulted (treat as can't-confirm → drop when local was wrong).
    public static func label(localCorrect: Bool, cloudCorrect: Bool?) -> EscalationLabel {
        if localCorrect { return .keepLocal }
        if cloudCorrect == true { return .escalate }
        return .drop
    }

    public struct Metrics: Equatable, Sendable {
        public let precision: Double   // of deferred, fraction where local was actually wrong
        public let recall: Double      // of local-wrong cases, fraction the model deferred
        public let overEscalation: Double  // of local-right cases, fraction wrongly deferred
        public let n: Int
    }

    /// `predictions[i]` = the model emitted defer_to_cloud; `localWrong[i]` =
    /// local answer was actually wrong (the ground truth).
    public static func metrics(predictions: [Bool], localWrong: [Bool]) -> Metrics {
        precondition(predictions.count == localWrong.count, "length mismatch")
        var tp = 0, fp = 0, fn = 0, localRight = 0, deferWhenRight = 0
        for (deferred, wrong) in zip(predictions, localWrong) {
            if deferred && wrong { tp += 1 }
            if deferred && !wrong { fp += 1; deferWhenRight += 1 }
            if !deferred && wrong { fn += 1 }
            if !wrong { localRight += 1 }
        }
        let precision = (tp + fp) > 0 ? Double(tp) / Double(tp + fp) : 0
        let recall = (tp + fn) > 0 ? Double(tp) / Double(tp + fn) : 0
        let over = localRight > 0 ? Double(deferWhenRight) / Double(localRight) : 0
        return Metrics(precision: precision, recall: recall, overEscalation: over, n: predictions.count)
    }
}
