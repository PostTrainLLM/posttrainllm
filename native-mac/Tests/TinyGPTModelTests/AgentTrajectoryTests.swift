import XCTest
@testable import TinyGPTModel

/// B22 — AgentTrajectory roundtrip + recorder tests. Asserts byte-equal
/// preservation of `input_ids` / `output_ids` across save → reload, since
/// the whole point of the format is that downstream SFT/DPO consumers can
/// trust those arrays without retokenization.
final class AgentTrajectoryTests: XCTestCase {

    func testRoundtripPreservesTokenIds() throws {
        let traj = AgentTrajectory(
            id: "11111111-2222-3333-4444-555555555555",
            checkpointPath: "/models/specialist.tinygpt",
            modelFingerprint: "abc123",
            task: "bfcl-mt-easy",
            steps: [
                AgentTrajectoryStep(
                    role: "user",
                    content: "What's the weather in Paris?",
                    inputIds: [1, 2, 3, 4, 5]),
                AgentTrajectoryStep(
                    role: "assistant",
                    content: "{\"tool\":\"weather\",\"arguments\":{\"city\":\"Paris\"}}",
                    outputIds: [9, 8, 7, 6, 5, 4, 3, 2, 1],
                    toolCall: ToolCallPayload(
                        name: "weather",
                        argumentsJson: "{\"city\":\"Paris\"}")),
                AgentTrajectoryStep(
                    role: "tool",
                    content: "Sunny, 22°C",
                    toolResult: ToolResultPayload(
                        name: "weather",
                        stdout: "Sunny, 22°C",
                        stderr: "",
                        exitCode: 0,
                        durationSec: 0.42)),
                AgentTrajectoryStep(
                    role: "assistant",
                    content: "{\"answer\":\"22°C and sunny.\"}",
                    outputIds: [10, 11, 12, 13, 14, 15],
                    reward: 1.0),
            ],
            summary: ["task": "bfcl-mt-easy", "final_reward": "1.0"])

        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("trajtest-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: tmp) }

        let written = try traj.write(to: tmp)
        XCTAssertTrue(written.lastPathComponent.hasSuffix(".atraj"))

        let loaded = try AgentTrajectory.load(from: written)
        XCTAssertEqual(loaded, traj)

        // Specific byte-equal asserts on the token-ID arrays — the
        // invariant this format exists to preserve.
        XCTAssertEqual(loaded.steps[0].inputIds, [1, 2, 3, 4, 5])
        XCTAssertEqual(loaded.steps[1].outputIds, [9, 8, 7, 6, 5, 4, 3, 2, 1])
        XCTAssertEqual(loaded.steps[3].outputIds, [10, 11, 12, 13, 14, 15])
        XCTAssertEqual(loaded.steps[1].toolCall?.name, "weather")
        XCTAssertEqual(loaded.steps[2].toolResult?.exitCode, 0)
    }

    func testRecorderAppendsAndFlushes() throws {
        let recorder = AgentTrajectoryRecorder(
            checkpointPath: "/models/test.tinygpt",
            task: "unit-test")
        recorder.appendUser(text: "ping",
                            inputIds: [101, 102])
        recorder.appendAssistant(
            text: "{\"tool\":\"echo\",\"arguments\":{\"msg\":\"ping\"}}",
            outputIds: [201, 202, 203],
            toolCall: ToolCallPayload(name: "echo",
                                       argumentsJson: "{\"msg\":\"ping\"}"))
        recorder.appendTool(result: ToolResultPayload(
            name: "echo", stdout: "ping", stderr: "",
            exitCode: 0, durationSec: 0.01))
        recorder.appendAssistant(
            text: "{\"answer\":\"pong\"}",
            outputIds: [301, 302])
        recorder.annotateLastReward(0.5)
        recorder.setSummary(["test": "ok"])

        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("rectest-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: tmp) }
        let url = try recorder.finish(to: tmp)
        let loaded = try AgentTrajectory.load(from: url)

        XCTAssertEqual(loaded.checkpointPath, "/models/test.tinygpt")
        XCTAssertEqual(loaded.task, "unit-test")
        XCTAssertEqual(loaded.steps.count, 4)
        XCTAssertEqual(loaded.steps[0].inputIds, [101, 102])
        XCTAssertEqual(loaded.steps[1].outputIds, [201, 202, 203])
        XCTAssertEqual(loaded.steps[1].toolCall?.argumentsJson,
                       "{\"msg\":\"ping\"}")
        XCTAssertEqual(loaded.steps[2].toolResult?.stdout, "ping")
        XCTAssertEqual(loaded.steps[3].outputIds, [301, 302])
        XCTAssertEqual(loaded.steps[3].reward, 0.5)
        XCTAssertEqual(loaded.summary["test"], "ok")
    }

    func testEmptyTrajectoryRoundtripsAndDirIsAutoCreated() throws {
        let traj = AgentTrajectory(task: "smoke")
        let tmp = FileManager.default.temporaryDirectory
            .appendingPathComponent("emptytest-\(UUID().uuidString)")
            .appendingPathComponent("nested") // ensure nested dir auto-creates
        defer { try? FileManager.default.removeItem(at: tmp.deletingLastPathComponent()) }
        let url = try traj.write(to: tmp)
        let loaded = try AgentTrajectory.load(from: url)
        XCTAssertEqual(loaded.task, "smoke")
        XCTAssertTrue(loaded.steps.isEmpty)
    }
}
