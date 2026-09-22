import Foundation

/// Issue #159 — agentic trajectory export for `traces-to-data --export trajectory`.
///
/// The answer-only exporter flattens a rollout to (user → final answer)
/// pairs: tool calls and the observations that grounded the answer are
/// dropped. This path instead emits **one row per assistant turn**, each
/// carrying the full context prefix the model actually saw — system,
/// user, earlier assistant turns (as context), and tool results.
///
/// Discipline borrowed from Halo's rollout handling: every eligible
/// assistant turn becomes a supervised target under its real conditioning
/// context; user/tool/system steps stay context, never targets. Ambiguous
/// steps (unknown roles, empty assistant content) are preserved as
/// context rather than guessed at.
///
/// Tool-result fidelity note: the recorder stores `result.stdout` as the
/// tool step's `content`, but the model was fed the structured JSON
/// `{"tool","stdout","stderr","exit_code"}` (AgentLoop.encodeToolResult).
/// When the structured `tool_result` payload exists we reconstruct that
/// JSON so training context matches what was fed at inference time.
public enum AgentTrajectoryExport {

    /// One message inside an exported row. `supervise` marks the single
    /// assistant turn this row trains on; everything else is context.
    /// `tool_call` / `tool_result` / `output_ids` are carried through
    /// verbatim for future consumers (token-level RLVR wants the sampled
    /// IDs — they are tokenizer-coupled, so SFT re-encodes text instead).
    public struct Message: Equatable, Sendable {
        public let role: String
        public let content: String
        public let supervise: Bool
        public let toolCall: ToolCallPayload?
        public let toolResult: ToolResultPayload?
        public let outputIds: [Int]?

        public init(role: String, content: String, supervise: Bool,
                    toolCall: ToolCallPayload? = nil,
                    toolResult: ToolResultPayload? = nil,
                    outputIds: [Int]? = nil) {
            self.role = role
            self.content = content
            self.supervise = supervise
            self.toolCall = toolCall
            self.toolResult = toolResult
            self.outputIds = outputIds
        }
    }

    /// One emitted training row: the message list (last entry is the
    /// supervised target) plus the keys dedup operates on.
    /// `contextKey` is the full conditioning context — two rows sharing a
    /// user prompt but differing earlier in the trajectory are NOT dupes.
    public struct Row: Sendable {
        public let messages: [Message]
        public let contextKey: String
        public let rowKey: String
    }

    /// Emit one row per eligible assistant turn. Returns an empty array
    /// for trajectories with no usable assistant content.
    public static func rows(for traj: AgentTrajectory) -> [Row] {
        var context: [Message] = []
        var rows: [Row] = []
        for step in traj.steps {
            switch step.role {
            case "assistant":
                let content = step.content
                let eligible = !content
                    .trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    || !(step.outputIds ?? []).isEmpty
                let target = Message(
                    role: "assistant", content: content, supervise: true,
                    toolCall: step.toolCall, outputIds: step.outputIds)
                if eligible {
                    rows.append(Row(
                        messages: context + [target],
                        contextKey: serialize(context),
                        rowKey: serialize(context + [target])))
                }
                // The turn joins the context for later rows — unsupervised.
                context.append(Message(
                    role: "assistant", content: content, supervise: false,
                    toolCall: step.toolCall, outputIds: step.outputIds))
            case "tool":
                context.append(Message(
                    role: "tool",
                    content: toolResultText(step),
                    supervise: false,
                    toolResult: step.toolResult))
            default:
                // system / user / anything else: context, verbatim.
                context.append(Message(role: step.role,
                                       content: step.content,
                                       supervise: false))
            }
        }
        return rows
    }

    /// Rebuild the JSON the agent loop actually fed the model for a tool
    /// step — `{"tool","stdout","stderr","exit_code"}` — falling back to
    /// the recorded `content` (bare stdout) when no payload was stored.
    public static func toolResultText(_ step: AgentTrajectoryStep) -> String {
        guard let r = step.toolResult else { return step.content }
        let obj: [String: Any] = [
            "tool": r.name,
            "stdout": r.stdout,
            "stderr": r.stderr,
            "exit_code": r.exitCode,
        ]
        if let data = try? JSONSerialization.data(
            withJSONObject: obj, options: [.sortedKeys]),
           let s = String(data: data, encoding: .utf8) { return s }
        return step.content
    }

    /// Stable serialization of a message list for dedup keys — role,
    /// content, and supervise flag only; ids and payloads don't affect
    /// what the model learns from.
    private static func serialize(_ msgs: [Message]) -> String {
        msgs.map { "\($0.role)\u{1F}\($0.supervise)\u{1F}\($0.content)" }
            .joined(separator: "\u{1E}")
    }
}
