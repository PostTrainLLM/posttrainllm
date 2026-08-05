// Classify JSONL Pace intent rows with Apple's on-device FoundationModels model.
// Input:  {"id":"...","text":"..."}
// Output: {"id":"...","label":"...","latency_ms":123.4,"error":null}
//
// Build:
//   xcrun swiftc -O -target arm64-apple-macosx26.0 scripts/fm_intent_bridge.swift -o /tmp/fm_intent_bridge

import Foundation
import FoundationModels

let labels = [
    "chitchat", "pureKnowledge", "screenDescription", "screenAction",
    "research", "phoneLargeModel", "unknown",
]

let instructions = """
Classify one user voice turn for Pace, a macOS voice companion, into exactly one label.
chitchat: greetings, thanks, goodbyes, apologies, or social filler.
pureKnowledge: a single spoken-answer question needing no current screen; questions about Pace itself; past-tense research mentions are not new research requests.
screenDescription: inspect, read, summarize, or describe visible screen content without changing it.
screenAction: perform a supported Mac action such as click, type, open an app, navigate, or control volume.
research: a requested multi-step investigation, comparison, source search, or synthesis.
phoneLargeModel: explicitly or idiomatically escalate to a bigger, cloud, frontier, or smarter model.
unknown: unsupported physical, home-device, or commerce actions; gibberish; or genuinely uncategorizable input.
Pace boundaries: volume control is screenAction; home lights and appliances are unknown; questions about Pace are pureKnowledge.
"""

func runBlocking<T>(_ operation: @escaping () async -> T) -> T {
    let semaphore = DispatchSemaphore(value: 0)
    let box = UnsafeMutablePointer<T?>.allocate(capacity: 1)
    box.initialize(to: nil)
    Task.detached {
        box.pointee = await operation()
        semaphore.signal()
    }
    semaphore.wait()
    let value = box.pointee!
    box.deinitialize(count: 1)
    box.deallocate()
    return value
}

@available(macOS 26.0, *)
func schema() throws -> GenerationSchema {
    let label = DynamicGenerationSchema(name: "PaceIntent", anyOf: labels)
    let root = DynamicGenerationSchema(
        name: "Classification",
        properties: [.init(name: "label", schema: label)]
    )
    return try GenerationSchema(root: root, dependencies: [])
}

@available(macOS 26.0, *)
func classify(_ text: String) async -> (String?, String?) {
    do {
        let session = LanguageModelSession(instructions: instructions)
        let options = GenerationOptions(samplingMode: .greedy, temperature: nil, maximumResponseTokens: 24)
        let response = try await session.respond(
            to: "User turn: \(text)",
            schema: try schema(),
            includeSchemaInPrompt: true,
            options: options
        )
        guard let data = response.content.jsonString.data(using: .utf8),
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let label = object["label"] as? String,
              labels.contains(label) else {
            return (nil, "model returned no valid label")
        }
        return (label, nil)
    } catch {
        return (nil, String(describing: error))
    }
}

func emit(id: String, label: String?, latency: Double, error: String?) {
    let object: [String: Any] = [
        "id": id,
        "label": label ?? NSNull(),
        "latency_ms": latency,
        "error": error ?? NSNull(),
    ]
    guard let data = try? JSONSerialization.data(withJSONObject: object),
          let line = String(data: data, encoding: .utf8) else { return }
    print(line)
    fflush(stdout)
}

guard #available(macOS 26.0, *) else {
    fputs("FoundationModels requires macOS 26 or newer\n", stderr)
    exit(1)
}
if case .unavailable(let reason) = SystemLanguageModel.default.availability {
    fputs("FoundationModels unavailable: \(reason)\n", stderr)
    exit(1)
}

while let line = readLine() {
    guard let data = line.data(using: .utf8),
          let row = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let id = row["id"] as? String,
          let text = row["text"] as? String else {
        emit(id: "invalid", label: nil, latency: 0, error: "invalid input row")
        continue
    }
    let started = ContinuousClock.now
    let result = runBlocking { await classify(text) }
    let duration = ContinuousClock.now - started
    let milliseconds = Double(duration.components.seconds) * 1000
        + Double(duration.components.attoseconds) / 1_000_000_000_000_000
    emit(id: id, label: result.0, latency: milliseconds, error: result.1)
}
