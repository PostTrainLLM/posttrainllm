import Foundation
import XCTest
@testable import TinyGPTModel

/// Issue #159 — agentic trajectory export. Proves the actions that
/// produced an answer survive export: one row per assistant turn, full
/// conditioning context preserved, tool results reconstructed to the
/// JSON the model actually saw, and supervision lands on exactly the
/// intended spans.
final class TrajectoryExportTests: XCTestCase {

    // MARK: - fixture

    /// system → user → assistant(tool call) → tool → assistant(answer)
    private func toolUseTrajectory() -> AgentTrajectory {
        AgentTrajectory(
            id: "traj-1", task: "fixture",
            steps: [
                AgentTrajectoryStep(role: "system", content: "You have tools."),
                AgentTrajectoryStep(role: "user", content: "Read count.txt."),
                AgentTrajectoryStep(
                    role: "assistant",
                    content: #"{"tool":"read_file","arguments":{"path":"count.txt"}}"#,
                    outputIds: [41, 42, 43],
                    toolCall: ToolCallPayload(
                        name: "read_file",
                        argumentsJson: #"{"path":"count.txt"}"#)),
                AgentTrajectoryStep(
                    role: "tool", content: "17",
                    toolResult: ToolResultPayload(
                        name: "read_file", stdout: "17", stderr: "",
                        exitCode: 0)),
                AgentTrajectoryStep(
                    role: "assistant", content: #"{"answer":"The number is 17."}"#,
                    outputIds: [50, 51]),
            ])
    }

    // MARK: - AgentTrajectoryExport.rows

    func testOneRowPerAssistantTurn() {
        let rows = AgentTrajectoryExport.rows(for: toolUseTrajectory())
        XCTAssertEqual(rows.count, 2)
        for row in rows {
            XCTAssertEqual(row.messages.last?.role, "assistant")
            XCTAssertTrue(row.messages.last?.supervise ?? false)
            XCTAssertFalse(row.messages.dropLast().contains { $0.supervise },
                           "context messages must never be supervised")
        }
    }

    func testToolCallTurnIsSupervisedTarget() {
        let rows = AgentTrajectoryExport.rows(for: toolUseTrajectory())
        // Row 1 supervises the tool CALL itself — the action, not the answer.
        XCTAssertEqual(rows[0].messages.map(\.role),
                       ["system", "user", "assistant"])
        let target = rows[0].messages[2]
        XCTAssertTrue(target.content.contains(#""tool":"read_file""#))
        XCTAssertEqual(target.toolCall?.name, "read_file")
        XCTAssertEqual(target.outputIds, [41, 42, 43])
    }

    func testAnswerRowCarriesFullContext() {
        let rows = AgentTrajectoryExport.rows(for: toolUseTrajectory())
        // Row 2's context contains the tool call AND the tool result.
        XCTAssertEqual(rows[1].messages.map(\.role),
                       ["system", "user", "assistant", "tool", "assistant"])
        XCTAssertFalse(rows[1].messages[2].supervise)
        XCTAssertFalse(rows[1].messages[3].supervise)
        XCTAssertTrue(rows[1].messages[4].content.contains("17"))
    }

    func testToolResultReconstructedAsModelSawIt() {
        let rows = AgentTrajectoryExport.rows(for: toolUseTrajectory())
        let tool = rows[1].messages[3]
        // Not bare stdout ("17") — the structured JSON the agent loop fed.
        XCTAssertTrue(tool.content.contains(#""tool":"read_file""#))
        XCTAssertTrue(tool.content.contains(#""stdout":"17""#))
        XCTAssertTrue(tool.content.contains(#""exit_code":0"#))
        XCTAssertEqual(tool.toolResult?.name, "read_file")
    }

    func testToolContentFallbackWithoutPayload() {
        let traj = AgentTrajectory(steps: [
            AgentTrajectoryStep(role: "user", content: "hi"),
            AgentTrajectoryStep(role: "assistant", content: #"{"tool":"x"}"#),
            AgentTrajectoryStep(role: "tool", content: "raw stdout only"),
            AgentTrajectoryStep(role: "assistant", content: "done"),
        ])
        let rows = AgentTrajectoryExport.rows(for: traj)
        XCTAssertEqual(rows[1].messages[2].content, "raw stdout only")
    }

    func testContextKeyDistinguishesSamePromptDifferentPrefix() {
        // Two rows ending in assistant turns reachable from the same user
        // prompt share that prompt but NOT their conditioning context.
        let rows = AgentTrajectoryExport.rows(for: toolUseTrajectory())
        XCTAssertNotEqual(rows[0].contextKey, rows[1].contextKey)
        XCTAssertNotEqual(rows[0].rowKey, rows[1].rowKey)
    }

    func testEmptyAssistantTurnSkippedButKeptAsContext() {
        let traj = AgentTrajectory(steps: [
            AgentTrajectoryStep(role: "user", content: "hi"),
            AgentTrajectoryStep(role: "assistant", content: "   "),
            AgentTrajectoryStep(role: "user", content: "again?"),
            AgentTrajectoryStep(role: "assistant", content: "real answer"),
        ])
        let rows = AgentTrajectoryExport.rows(for: traj)
        XCTAssertEqual(rows.count, 1)
        XCTAssertEqual(rows[0].messages.map(\.role),
                       ["user", "assistant", "user", "assistant"])
    }

    func testNoAssistantStepsYieldsNoRows() {
        let traj = AgentTrajectory(steps: [
            AgentTrajectoryStep(role: "system", content: "s"),
            AgentTrajectoryStep(role: "user", content: "u"),
        ])
        XCTAssertTrue(AgentTrajectoryExport.rows(for: traj).isEmpty)
    }

    // MARK: - renderChatBlocks

    func testRenderMatchesAgentLoopBlockShapes() {
        let blocks = SFTBuilder.renderChatBlocks([
            SFTMessage(role: "system", content: "SYS", supervise: false),
            SFTMessage(role: "user", content: "U", supervise: false),
            SFTMessage(role: "assistant", content: "CALL", supervise: false),
            SFTMessage(role: "tool", content: "RES", supervise: false),
            SFTMessage(role: "assistant", content: "ANS", supervise: true),
        ])
        let texts = blocks.map(\.text)
        XCTAssertEqual(texts, [
            "<|im_start|>system\nSYS<|im_end|>\n",
            "<|im_start|>user\nU<|im_end|>\n<|im_start|>assistant\n",
            "CALL<|im_end|>",
            "<|im_start|>tool\nRES<|im_end|>\n<|im_start|>assistant\n",
            "ANS<|im_end|>",
        ])
        XCTAssertEqual(blocks.map(\.supervise),
                       [false, false, false, false, true])
    }

    func testRenderAddsAssistantPrefaceWhenContextLacksIt() {
        // A row starting with assistant (or after system) still gets the
        // <im_start>assistant marker — as context, never supervised.
        let blocks = SFTBuilder.renderChatBlocks([
            SFTMessage(role: "assistant", content: "A", supervise: true),
        ])
        XCTAssertEqual(blocks.map(\.text),
                       ["<|im_start|>assistant\n", "A<|im_end|>"])
        XCTAssertEqual(blocks.map(\.supervise), [false, true])
    }

    // MARK: - buildChatExample (injected encoder)

    /// Character-level stub encoder — deterministic, tokenizer-free.
    private func stubEncode(_ s: String) -> [Int32] {
        Array(s.utf8).map { Int32($0) }
    }

    func testMaskCoversExactlyTheSupervisedSpan() throws {
        let ex = try SFTBuilder.buildChatExample(
            messages: [
                SFTMessage(role: "user", content: "U", supervise: false),
                SFTMessage(role: "assistant", content: "ANS", supervise: true),
            ],
            maxSeqLen: 1024, encode: stubEncode)
        // context = user block incl. assistant preface; target = "ANS<|im_end|>"
        let ctxText = "<|im_start|>user\nU<|im_end|>\n<|im_start|>assistant\n"
        let tgtText = "ANS<|im_end|>"
        XCTAssertEqual(ex.tokens, stubEncode(ctxText) + stubEncode(tgtText))
        let ctxLen = stubEncode(ctxText).count
        XCTAssertEqual(Array(ex.responseMask.prefix(ctxLen)),
                       [Bool](repeating: false, count: ctxLen))
        XCTAssertEqual(Array(ex.responseMask.suffix(stubEncode(tgtText).count)),
                       [Bool](repeating: true, count: stubEncode(tgtText).count))
    }

    func testUnsupervisedAssistantTurnIsPureContext() throws {
        let ex = try SFTBuilder.buildChatExample(
            messages: [
                SFTMessage(role: "user", content: "U", supervise: false),
                SFTMessage(role: "assistant", content: "CALL", supervise: false),
                SFTMessage(role: "tool", content: "RES", supervise: false),
                SFTMessage(role: "assistant", content: "ANS", supervise: true),
            ],
            maxSeqLen: 1024, encode: stubEncode)
        let supervised = zip(ex.tokens, ex.responseMask)
            .filter { $0.1 }.map { $0.0 }
        XCTAssertEqual(supervised, stubEncode("ANS<|im_end|>"))
    }

    func testTruncationCapsAtMaxSeqLen() throws {
        let ex = try SFTBuilder.buildChatExample(
            messages: [
                SFTMessage(role: "user", content: "U", supervise: false),
                SFTMessage(role: "assistant", content: "LONG-ANSWER", supervise: true),
            ],
            maxSeqLen: 40, encode: stubEncode)
        XCTAssertEqual(ex.tokens.count, 40)
        XCTAssertEqual(ex.responseMask.count, 40)
    }

    // MARK: - SFTReader chat rows

    func testReaderParsesSuperviseFlags() throws {
        let url = try writeTemp(jsonl: """
            {"messages":[{"role":"user","content":"q","supervise":false},{"role":"assistant","content":"a","supervise":true}],"export":"trajectory"}
            """)
        let records = try SFTReader.readJSONL(url)
        XCTAssertEqual(records.count, 1)
        XCTAssertEqual(records[0].messages?.map(\.supervise), [false, true])
    }

    func testReaderDefaultsToLastAssistantWhenUnflagged() throws {
        let url = try writeTemp(jsonl: """
            {"messages":[{"role":"user","content":"q"},{"role":"assistant","content":"a"}]}
            """)
        let records = try SFTReader.readJSONL(url)
        XCTAssertEqual(records[0].messages?.map(\.supervise), [false, true])
    }

    func testReaderKeepsFlatRowsUnchanged() throws {
        let url = try writeTemp(jsonl: """
            {"instruction":"i","response":"r"}
            {"messages":[{"role":"user","content":"q"},{"role":"assistant","content":"a"}]}
            """)
        let records = try SFTReader.readJSONL(url)
        XCTAssertEqual(records.count, 2)
        XCTAssertNil(records[0].messages)
        XCTAssertEqual(records[0].instruction, "i")
        XCTAssertNotNil(records[1].messages)
    }

    private func writeTemp(jsonl: String) throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("traj-test-\(UUID().uuidString).jsonl")
        try jsonl.write(to: url, atomically: true, encoding: .utf8)
        addTeardownBlock { try? FileManager.default.removeItem(at: url) }
        return url
    }
}
