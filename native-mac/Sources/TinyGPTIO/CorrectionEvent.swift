import Foundation

// On-device continual-learning — Phase 1: correction capture.
//
// A `CorrectionEvent` records that a user fixed a model's output: the
// original output, their corrected version, and enough context to later
// turn it into a training pair. The corrected TEXT is the signal (not a
// binary reward) — the Trajectory insight. Phase 1 only CAPTURES; curation
// (-> SFT/DPO pairs) and the gated overnight refresh are later phases.
// See docs/prds/continual-learning-loop.md.
//
// Everything here is pure Foundation (no MLX) so the capture path and its
// tests run without loading a model or the Metal runtime.

public struct CorrectionEvent: Codable, Equatable {
    /// Schema version; bump on an incompatible change so `loadAll` can skip
    /// or migrate old lines.
    public var version: Int
    /// Stable id for this event (UUID string).
    public var id: String
    /// Unix seconds when the correction was recorded.
    public var timestamp: Double
    /// Free-form intent label: "dictation" | "tool_call" | "action" | …
    /// Kept a string (not an enum) so new skills can capture without a
    /// schema change.
    public var intentKind: String
    /// The context/prompt that produced `original` (optional — some
    /// surfaces only have the before/after pair).
    public var input: String?
    /// The model output the user corrected.
    public var original: String
    /// The user's corrected version — the training target.
    public var corrected: String
    /// Which model produced `original` (fingerprint or path), if known.
    public var modelFingerprint: String?
    /// Provenance: "serve" | "agent" | "cli" | client name. Free-form.
    public var source: String?

    public static let currentVersion = 1

    public init(version: Int = CorrectionEvent.currentVersion,
                id: String = UUID().uuidString,
                timestamp: Double = Date().timeIntervalSince1970,
                intentKind: String,
                input: String? = nil,
                original: String,
                corrected: String,
                modelFingerprint: String? = nil,
                source: String? = nil) {
        self.version = version
        self.id = id
        self.timestamp = timestamp
        self.intentKind = intentKind
        self.input = input
        self.original = original
        self.corrected = corrected
        self.modelFingerprint = modelFingerprint
        self.source = source
    }
}

/// Append-only JSONL store of correction events. One JSON object per line so
/// captures are cheap (seek-to-end append, no rewrite) and a partial write
/// only ever loses the last line. Local-first by default — the data never
/// has to leave the device.
public struct CorrectionStore {
    public let url: URL

    /// Point at an explicit JSONL file.
    public init(fileURL: URL) {
        self.url = fileURL
    }

    /// Point at `directory/name` (default `corrections.jsonl`).
    public init(directory: URL, name: String = "corrections.jsonl") {
        self.url = directory.appendingPathComponent(name)
    }

    /// `~/.tinygpt/corrections` — the default local capture location.
    public static func defaultDirectory() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".tinygpt")
            .appendingPathComponent("corrections")
    }

    /// Append one event as a single JSON line, creating the file (and parent
    /// directory) on first write. Encoding uses sorted keys + no pretty-print
    /// so each event is exactly one line.
    ///
    /// Concurrency: opens with `O_APPEND | O_CREAT` and writes the whole line
    /// in one `write(2)`. On a local filesystem an append-mode write of a
    /// line-sized payload is atomic — the kernel seeks-to-end and writes as a
    /// unit — so concurrent writers (the CLI and the planned serve endpoint)
    /// can't interleave or clobber each other. (No separate exists-check, so
    /// no create-race either.) Files are created `0600` / dirs `0700` since
    /// corrections are potentially-sensitive user text that stays on-device.
    public func append(_ event: CorrectionEvent) throws {
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys]
        var line = try enc.encode(event)
        line.append(0x0A)  // newline terminator

        let fm = FileManager.default
        let dir = url.deletingLastPathComponent()
        if !fm.fileExists(atPath: dir.path) {
            try fm.createDirectory(at: dir, withIntermediateDirectories: true,
                                   attributes: [.posixPermissions: 0o700])
        }

        let fd = open(url.path, O_WRONLY | O_APPEND | O_CREAT, 0o600)
        guard fd >= 0 else {
            throw NSError(domain: "tinygpt.correction-store", code: Int(errno),
                          userInfo: [NSLocalizedDescriptionKey:
                            "open(\(url.path)) failed: \(String(cString: strerror(errno)))"])
        }
        defer { close(fd) }
        try line.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            guard let base = raw.baseAddress else { return }
            var written = 0
            while written < line.count {
                let n = write(fd, base.advanced(by: written), line.count - written)
                if n < 0 {
                    throw NSError(domain: "tinygpt.correction-store", code: Int(errno),
                                  userInfo: [NSLocalizedDescriptionKey:
                                    "write failed: \(String(cString: strerror(errno)))"])
                }
                written += n
            }
        }
    }

    /// Load every parseable event. Unparseable lines (partial final write,
    /// schema drift) are skipped rather than failing the whole read, so the
    /// store stays usable as it evolves.
    public func loadAll() throws -> [CorrectionEvent] {
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.path) else { return [] }
        let data = try Data(contentsOf: url)
        guard let text = String(data: data, encoding: .utf8) else { return [] }
        let dec = JSONDecoder()
        var out: [CorrectionEvent] = []
        for raw in text.split(separator: "\n", omittingEmptySubsequences: true) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { continue }
            if let event = try? dec.decode(CorrectionEvent.self, from: Data(line.utf8)) {
                out.append(event)
            }
        }
        return out
    }

    /// Number of stored events (parseable lines).
    public func count() throws -> Int {
        try loadAll().count
    }
}
