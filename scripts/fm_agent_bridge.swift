// fm_agent_bridge — expose Apple's on-device FoundationModels model behind the OpenAI
// chat-completions + tools API, so our existing BFCL MULTI-TURN harness can score it on
// the SAME agentic gate as DeepSeek / Gemma / our distilled 4B, with zero harness changes
// (point bfcl_multiturn_deepseek.py's DS_URL at this server).
//
// Distinct from scripts/fm_bridge.swift, which is a stdin/stdout line bridge for the Pace
// single-turn PLANNER gate. This one is an HTTP server for the multi-turn AGENTIC gate
// (tool-calling over BFCL backends: VehicleControlAPI / TradingBot / TravelAPI / file-ops),
// where the tool catalog is dynamic per task so a static @Generable type won't do.
//
// The "conform to a common API" pattern: Apple ships ClaudeForFoundationModels to put Claude
// behind the on-device LanguageModelSession API; here we go the other way and put the
// on-device model behind the OpenAI API the rest of our stack already speaks.
//
// Tool-calling uses guided generation: each request builds a DynamicGenerationSchema
//   { tool_calls: [{ name: <enum of THIS task's tool names>, arguments_json: String }], message: String? }
// and we read GeneratedContent.jsonString back out. The tool *catalog* (descriptions + param
// schemas) is injected into the prompt text since only the names are enum-constrained.
//
// Build: xcrun swiftc -O -target arm64-apple-macosx26.0 scripts/fm_agent_bridge.swift -o /tmp/fm_agent_bridge
// Run:   FM_PORT=8765 /tmp/fm_agent_bridge
import Foundation
import FoundationModels
import Darwin

let PORT = UInt16(ProcessInfo.processInfo.environment["FM_PORT"] ?? "8765") ?? 8765
let MAXTOK = Int(ProcessInfo.processInfo.environment["FM_MAXTOK"] ?? "512") ?? 512
// FM_COMPACT=1 renders the tool catalog as names + one-line descriptions only (no param
// schemas). Apple's on-device model has a ~4096-token context — a single BFCL backend's full
// catalog (19-23 tools, ~3-4.4k tokens) overflows it before the conversation even starts. The
// compact catalog is the deferred-tools idea: give the model the menu, not every schema.
let COMPACT = (ProcessInfo.processInfo.environment["FM_COMPACT"] ?? "0") == "1"
func log(_ s: String) { FileHandle.standardError.write((s + "\n").data(using: .utf8)!) }

// ---- async→sync bridge so the blocking accept loop can call `await respond` ----
func runBlocking<T>(_ op: @escaping () async -> T) -> T {
    let sem = DispatchSemaphore(value: 0)
    let box = UnsafeMutablePointer<T?>.allocate(capacity: 1)
    box.initialize(to: nil)
    Task.detached { box.pointee = await op(); sem.signal() }
    sem.wait()
    let v = box.pointee!
    box.deinitialize(count: 1); box.deallocate()
    return v
}

// ---- prompt assembly from an OpenAI message list ----
func anyJSON(_ v: Any) -> String {
    if let d = try? JSONSerialization.data(withJSONObject: v, options: [.withoutEscapingSlashes]),
       let s = String(data: d, encoding: .utf8) { return s }
    return "\(v)"
}

func renderToolCatalog(_ tools: [[String: Any]]) -> ([String], String) {
    var names: [String] = []
    var lines: [String] = []
    for t in tools {
        guard let fn = t["function"] as? [String: Any], let name = fn["name"] as? String else { continue }
        names.append(name)
        let desc = (fn["description"] as? String) ?? ""
        if COMPACT {
            let props = (fn["parameters"] as? [String: Any])?["properties"] as? [String: Any]
            let argNames = props.map { Array($0.keys).sorted().joined(separator: ", ") } ?? ""
            lines.append("- \(name)(\(argNames)): \(desc)")
        } else {
            let params = fn["parameters"] as? [String: Any] ?? [:]
            lines.append("- \(name): \(desc)\n  params: \(anyJSON(params))")
        }
    }
    return (names, lines.joined(separator: "\n"))
}

func renderConversation(_ messages: [[String: Any]]) -> (system: String, body: String) {
    var system = ""
    var body: [String] = []
    for m in messages {
        let role = (m["role"] as? String) ?? "user"
        let content = (m["content"] as? String) ?? ""
        switch role {
        case "system": system += content
        case "user": body.append("User: \(content)")
        case "assistant":
            if let tcs = m["tool_calls"] as? [[String: Any]], !tcs.isEmpty {
                let calls = tcs.compactMap { tc -> String? in
                    guard let fn = tc["function"] as? [String: Any], let n = fn["name"] as? String else { return nil }
                    let args = (fn["arguments"] as? String) ?? "{}"
                    return "\(n)(\(args))"
                }.joined(separator: ", ")
                body.append("Assistant called: \(calls)")
            } else if !content.isEmpty {
                body.append("Assistant: \(content)")
            }
        case "tool":
            body.append("Tool result: \(content)")
        default: break
        }
    }
    return (system, body.joined(separator: "\n"))
}

// ---- build the forced output schema for THIS turn ----
@available(macOS 26.0, *)
func buildSchema(toolNames: [String]) throws -> GenerationSchema {
    let names = toolNames.isEmpty ? ["noop"] : toolNames
    let nameEnum = DynamicGenerationSchema(name: "ToolName", anyOf: names)
    let argStr = DynamicGenerationSchema(type: String.self)
    let call = DynamicGenerationSchema(name: "Call", properties: [
        .init(name: "name", schema: nameEnum),
        .init(name: "arguments_json",
              description: "A JSON object of the arguments for this call, encoded as a string.",
              schema: argStr),
    ])
    let callsArray = DynamicGenerationSchema(arrayOf: call)
    let msgStr = DynamicGenerationSchema(type: String.self)
    let root = DynamicGenerationSchema(name: "Reply", properties: [
        .init(name: "tool_calls",
              description: "Function calls to make this step. Empty when the turn's request is fully handled.",
              schema: callsArray, isOptional: true),
        .init(name: "message",
              description: "Assistant reply text when no tool call is needed.",
              schema: msgStr, isOptional: true),
    ])
    return try GenerationSchema(root: root, dependencies: [])
}

// ---- one chat-completion: messages+tools -> OpenAI-shaped {content, tool_calls} ----
@available(macOS 26.0, *)
func complete(messages: [[String: Any]], tools: [[String: Any]]) async -> [String: Any] {
    let (names, catalog) = renderToolCatalog(tools)
    let (system, convo) = renderConversation(messages)
    let instructions = system.isEmpty ? "You are an autonomous tool-using agent." : system
    let prompt = """
    TOOLS (call by name; put the call's arguments as a JSON object string in arguments_json):
    \(catalog)

    CONVERSATION SO FAR:
    \(convo)

    Produce the next assistant step. If function calls are needed to satisfy the user's current \
    request, fill tool_calls (do not repeat a call that already succeeded above). When the current \
    request is fully handled, leave tool_calls empty and put any reply in message.
    """
    do {
        let schema = try buildSchema(toolNames: names)
        let session = LanguageModelSession(instructions: instructions)
        let opts = GenerationOptions(samplingMode: .greedy, temperature: nil, maximumResponseTokens: MAXTOK)
        let resp = try await session.respond(to: prompt, schema: schema, includeSchemaInPrompt: true, options: opts)
        return parseReply(resp.content.jsonString)
    } catch {
        log("[complete err] \(error)")
        return ["content": "", "tool_calls": []]
    }
}

// ---- map the model's guided JSON into the OpenAI message shape the harness expects ----
func parseReply(_ raw: String) -> [String: Any] {
    guard let data = raw.data(using: .utf8),
          let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        return ["content": raw, "tool_calls": []]
    }
    var toolCalls: [[String: Any]] = []
    if let calls = obj["tool_calls"] as? [[String: Any]] {
        for (i, c) in calls.enumerated() {
            guard let name = c["name"] as? String, !name.isEmpty, name != "noop" else { continue }
            var args = (c["arguments_json"] as? String) ?? "{}"
            if args.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { args = "{}" }
            toolCalls.append([
                "id": "call_\(i)",
                "type": "function",
                "function": ["name": name, "arguments": args],
            ])
        }
    }
    let message = (obj["message"] as? String) ?? ""
    return ["content": message, "tool_calls": toolCalls]
}

// ---- minimal HTTP/1.1 server (blocking, one connection at a time; the harness is sequential) ----
func readRequestBody(_ fd: Int32) -> Data? {
    var buf = Data()
    var tmp = [UInt8](repeating: 0, count: 65536)
    var headerEnd: Range<Data.Index>? = nil
    while headerEnd == nil {
        let n = recv(fd, &tmp, tmp.count, 0)
        if n <= 0 { return nil }
        buf.append(contentsOf: tmp[0..<n])
        headerEnd = buf.range(of: Data("\r\n\r\n".utf8))
    }
    let header = String(data: buf[..<headerEnd!.lowerBound], encoding: .utf8) ?? ""
    var contentLength = 0
    for line in header.split(separator: "\r\n") {
        let p = line.split(separator: ":", maxSplits: 1)
        if p.count == 2, p[0].lowercased().trimmingCharacters(in: .whitespaces) == "content-length" {
            contentLength = Int(p[1].trimmingCharacters(in: .whitespaces)) ?? 0
        }
    }
    var body = buf[headerEnd!.upperBound...]
    while body.count < contentLength {
        let n = recv(fd, &tmp, tmp.count, 0)
        if n <= 0 { break }
        body.append(contentsOf: tmp[0..<n])
    }
    return Data(body.prefix(contentLength))
}

func writeResponse(_ fd: Int32, _ jsonObj: [String: Any]) {
    let payload = (try? JSONSerialization.data(withJSONObject: jsonObj)) ?? Data("{}".utf8)
    var head = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: \(payload.count)\r\nConnection: close\r\n\r\n".data(using: .utf8)!
    head.append(payload)
    head.withUnsafeBytes { ptr in
        var off = 0
        let base = ptr.baseAddress!
        while off < head.count {
            let n = send(fd, base + off, head.count - off, 0)
            if n <= 0 { break }
            off += n
        }
    }
}

guard #available(macOS 26.0, *) else { log("needs macOS 26+"); exit(1) }

let avail = SystemLanguageModel.default.availability
if case .unavailable(let reason) = avail { log("[boot] on-device model UNAVAILABLE: \(reason)"); exit(1) }
log("[boot] on-device model available")

let listenFD = socket(AF_INET, SOCK_STREAM, 0)
var yes: Int32 = 1
setsockopt(listenFD, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
var addr = sockaddr_in()
addr.sin_family = sa_family_t(AF_INET)
addr.sin_port = PORT.bigEndian
addr.sin_addr.s_addr = inet_addr("127.0.0.1")
let bindRC = withUnsafePointer(to: &addr) { p in
    p.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(listenFD, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) }
}
if bindRC != 0 { log("[boot] bind failed on :\(PORT)"); exit(1) }
listen(listenFD, 16)
log("[boot] fm_agent_bridge listening on http://127.0.0.1:\(PORT)/v1/chat/completions")

var served = 0
while true {
    let clientFD = accept(listenFD, nil, nil)
    if clientFD < 0 { continue }
    defer { close(clientFD) }
    guard let body = readRequestBody(clientFD),
          let req = try? JSONSerialization.jsonObject(with: body) as? [String: Any] else {
        writeResponse(clientFD, ["choices": [["message": ["role": "assistant", "content": "", "tool_calls": []]]]])
        continue
    }
    let messages = (req["messages"] as? [[String: Any]]) ?? []
    let tools = (req["tools"] as? [[String: Any]]) ?? []
    let msg = runBlocking { await complete(messages: messages, tools: tools) }
    served += 1
    let tcs = (msg["tool_calls"] as? [[String: Any]]) ?? []
    if served % 20 == 0 { log("[served \(served)] last step: \(tcs.count) tool_call(s)") }
    writeResponse(clientFD, ["choices": [["message": [
        "role": "assistant",
        "content": msg["content"] ?? "",
        "tool_calls": tcs,
    ]]]])
}
