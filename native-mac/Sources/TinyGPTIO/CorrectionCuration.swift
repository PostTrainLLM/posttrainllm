import Foundation

// Continual-learning Phase 2 (curation): turn captured corrections into
// training pairs. Pure value logic (no I/O) so it's unit-testable without a
// model or the Metal runtime; the `corrections-to-data` CLI does the file I/O.
// See docs/prds/continual-learning-loop.md.
//
// A correction grounds a training pair only when it carries the `input` that
// produced the output — that's the prompt the model conditions on. Without it
// there's no well-formed (prompt → target) pair, so those events are skipped
// (and reported) rather than guessed at.

public extension CorrectionEvent {
    /// SFT pair: (user prompt, assistant target) = (input, corrected).
    /// nil when `input` is missing/empty (can't ground a pair).
    func sftPair() -> (user: String, assistant: String)? {
        guard let input, !input.isEmpty else { return nil }
        return (input, corrected)
    }

    /// DPO/preference triple: prompt=input, chosen=corrected, rejected=original.
    /// nil when `input` is missing/empty. Also nil if corrected == original
    /// (no preference signal).
    func dpoTriple() -> (prompt: String, chosen: String, rejected: String)? {
        guard let input, !input.isEmpty, corrected != original else { return nil }
        return (input, corrected, original)
    }
}

public enum CorrectionCorpusFormat: String {
    case sft
    case dpo
}

/// Convert a batch of correction events into JSONL rows for `tinygpt sft`/`dpo`.
/// Returns the encoded lines (one JSON object each, no trailing newline) plus a
/// skipped count for events that couldn't ground a pair. Row shapes match the
/// existing `traces-to-data` SFT JSONL (ChatML `messages`) and the DPO loader.
public enum CorrectionCurator {

    public struct Result {
        public let lines: [String]
        public let emitted: Int
        public let skipped: Int
    }

    public static func curate(_ events: [CorrectionEvent],
                              format: CorrectionCorpusFormat) -> Result {
        var lines: [String] = []
        var skipped = 0
        for e in events {
            let row: [String: Any]?
            switch format {
            case .sft:
                if let pair = e.sftPair() {
                    row = [
                        "messages": [
                            ["role": "user", "content": pair.user],
                            ["role": "assistant", "content": pair.assistant],
                        ],
                        "task": e.intentKind,
                        "source": "correction:\(e.id)",
                    ]
                } else { row = nil }
            case .dpo:
                if let t = e.dpoTriple() {
                    row = [
                        "prompt": t.prompt,
                        "chosen": t.chosen,
                        "rejected": t.rejected,
                        "task": e.intentKind,
                        "source": "correction:\(e.id)",
                    ]
                } else { row = nil }
            }
            guard let row,
                  let data = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]),
                  let line = String(data: data, encoding: .utf8)
            else { skipped += 1; continue }
            lines.append(line)
        }
        return Result(lines: lines, emitted: lines.count, skipped: skipped)
    }
}
