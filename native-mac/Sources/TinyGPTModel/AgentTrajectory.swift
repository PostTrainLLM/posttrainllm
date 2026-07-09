import Foundation

/// B22 — Token-preserving agent trajectory record.
///
/// Every agent rollout (the CLI `posttrainllm agent`, the serve-side multi-turn
/// loop, BFCL / τ-bench harness runs) can write one `.atraj` file
/// describing the full conversation: per-step role, decoded content,
/// **raw token IDs** sampled or fed, structured tool calls, tool results,
/// and rewards. The token-IDs invariant is the point — downstream SFT,
/// DPO, and (later) RLVR consume `output_ids` directly instead of
/// retokenizing the decoded text, which silently corrupts gradients on
/// tool-call args containing `\n` or non-ASCII bytes.
///
/// File layout (`<id>.atraj`): one JSON object encoded by `JSONEncoder`
/// with snake_case keys. Optional gzip is intentionally **out of V1
/// scope** — `.atraj.gz` is reserved for a later compression pass.
///
/// Discipline lifted from Poolside's Laguna deep dive
/// (https://poolside.ai/blog/laguna-a-deeper-dive). Their finding:
/// keeping token IDs end-to-end avoids the BPE re-encoding mismatches
/// that silently bias off-policy gradients.
public struct AgentTrajectoryStep: Codable, Equatable {
    public var role: String                      // "system" | "user" | "assistant" | "tool"
    public var content: String                   // decoded text — for human inspection
    public var inputIds: [Int]?                  // token IDs fed to the model on this step
    public var outputIds: [Int]?                 // sampled IDs (assistant only)
    public var toolCall: ToolCallPayload?        // structured tool args (assistant initiating)
    public var toolResult: ToolResultPayload?    // structured tool output (tool role)
    public var reward: Double?                   // task-defined; nil if not scored
    public var timestamp: Double?                // Unix seconds; optional — runtime stamps it

    public init(role: String,
                content: String,
                inputIds: [Int]? = nil,
                outputIds: [Int]? = nil,
                toolCall: ToolCallPayload? = nil,
                toolResult: ToolResultPayload? = nil,
                reward: Double? = nil,
                timestamp: Double? = nil)
    {
        self.role = role
        self.content = content
        self.inputIds = inputIds
        self.outputIds = outputIds
        self.toolCall = toolCall
        self.toolResult = toolResult
        self.reward = reward
        self.timestamp = timestamp
    }

    private enum CodingKeys: String, CodingKey {
        case role, content
        case inputIds = "input_ids"
        case outputIds = "output_ids"
        case toolCall = "tool_call"
        case toolResult = "tool_result"
        case reward
        case timestamp
    }
}

/// Structured tool invocation. We keep `arguments` as a JSON string so
/// the codable surface stays Sendable and dictionary-heterogeneity isn't
/// a problem — the consumer parses on demand.
public struct ToolCallPayload: Codable, Equatable {
    public var name: String
    public var argumentsJson: String

    public init(name: String, argumentsJson: String) {
        self.name = name
        self.argumentsJson = argumentsJson
    }

    private enum CodingKeys: String, CodingKey {
        case name
        case argumentsJson = "arguments_json"
    }
}

public struct ToolResultPayload: Codable, Equatable {
    public var name: String
    public var stdout: String
    public var stderr: String
    public var exitCode: Int
    public var durationSec: Double?

    public init(name: String, stdout: String, stderr: String,
                exitCode: Int, durationSec: Double? = nil)
    {
        self.name = name
        self.stdout = stdout
        self.stderr = stderr
        self.exitCode = exitCode
        self.durationSec = durationSec
    }

    private enum CodingKeys: String, CodingKey {
        case name, stdout, stderr
        case exitCode = "exit_code"
        case durationSec = "duration_sec"
    }
}

/// The top-level trajectory record. One file per rollout.
public struct AgentTrajectory: Codable, Equatable {
    public var version: Int                       // bump on incompatible schema change
    public var id: String                         // UUID for the rollout
    public var checkpointPath: String?            // origin model path (free-form)
    public var modelFingerprint: String?          // SHA-256(weights), if computed
    public var task: String?                      // optional task label (BFCL category, etc.)
    public var steps: [AgentTrajectoryStep]
    public var summary: [String: String]          // task-defined; small string-string bag

    public init(id: String = UUID().uuidString,
                version: Int = 1,
                checkpointPath: String? = nil,
                modelFingerprint: String? = nil,
                task: String? = nil,
                steps: [AgentTrajectoryStep] = [],
                summary: [String: String] = [:])
    {
        self.version = version
        self.id = id
        self.checkpointPath = checkpointPath
        self.modelFingerprint = modelFingerprint
        self.task = task
        self.steps = steps
        self.summary = summary
    }

    private enum CodingKeys: String, CodingKey {
        case version, id
        case checkpointPath = "checkpoint_path"
        case modelFingerprint = "model_fingerprint"
        case task, steps, summary
    }

    // MARK: - I/O

    /// Serialize as pretty-printed JSON for readability (the files are
    /// usually < 1 MB; pretty-printing helps debugging far more than the
    /// few % size saved).
    public func encode() throws -> Data {
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try enc.encode(self)
    }

    /// Atomically write to `<dir>/<id>.atraj`. Creates the directory if
    /// it doesn't exist. Returns the written URL.
    @discardableResult
    public func write(to directory: URL) throws -> URL {
        try FileManager.default.createDirectory(at: directory,
                                                 withIntermediateDirectories: true)
        let url = directory.appendingPathComponent("\(id).atraj")
        let data = try encode()
        try data.write(to: url, options: .atomic)
        return url
    }

    public static func load(from url: URL) throws -> AgentTrajectory {
        let data = try Data(contentsOf: url)
        return try JSONDecoder().decode(AgentTrajectory.self, from: data)
    }
}

/// Mutable recorder used by AgentLoop. Each call appends one step; the
/// final `finish(to:)` flushes to disk. The recorder is intentionally
/// **not** thread-safe — agent rollouts are single-threaded; a future
/// concurrent loop should own a recorder per task.
public final class AgentTrajectoryRecorder {
    public private(set) var trajectory: AgentTrajectory

    public init(checkpointPath: String? = nil,
                modelFingerprint: String? = nil,
                task: String? = nil)
    {
        self.trajectory = AgentTrajectory(
            checkpointPath: checkpointPath,
            modelFingerprint: modelFingerprint,
            task: task)
    }

    public func appendUser(text: String, inputIds: [Int]? = nil) {
        trajectory.steps.append(AgentTrajectoryStep(
            role: "user", content: text, inputIds: inputIds,
            timestamp: Date().timeIntervalSince1970))
    }

    public func appendSystem(text: String, inputIds: [Int]? = nil) {
        trajectory.steps.append(AgentTrajectoryStep(
            role: "system", content: text, inputIds: inputIds,
            timestamp: Date().timeIntervalSince1970))
    }

    public func appendAssistant(text: String, outputIds: [Int]? = nil,
                                 toolCall: ToolCallPayload? = nil)
    {
        trajectory.steps.append(AgentTrajectoryStep(
            role: "assistant", content: text,
            outputIds: outputIds, toolCall: toolCall,
            timestamp: Date().timeIntervalSince1970))
    }

    public func appendTool(result: ToolResultPayload, inputIds: [Int]? = nil) {
        trajectory.steps.append(AgentTrajectoryStep(
            role: "tool", content: result.stdout,
            inputIds: inputIds, toolResult: result,
            timestamp: Date().timeIntervalSince1970))
    }

    public func annotateLastReward(_ reward: Double) {
        guard !trajectory.steps.isEmpty else { return }
        trajectory.steps[trajectory.steps.count - 1].reward = reward
    }

    public func setSummary(_ kv: [String: String]) {
        for (k, v) in kv { trajectory.summary[k] = v }
    }

    @discardableResult
    public func finish(to directory: URL) throws -> URL {
        return try trajectory.write(to: directory)
    }
}
