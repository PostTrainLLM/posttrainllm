import Foundation
import XCTest
@testable import TinyGPTIO

final class CorrectionStoreTests: XCTestCase {

    private func tempDir() -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("posttrainllm-correction-tests")
            .appendingPathComponent(UUID().uuidString)
        return dir
    }

    func test_append_then_loadAll_roundTrips() throws {
        let store = CorrectionStore(directory: tempDir())
        let a = CorrectionEvent(intentKind: "dictation",
                                input: "transcribe this",
                                original: "their going home",
                                corrected: "they're going home",
                                source: "cli")
        let b = CorrectionEvent(intentKind: "tool_call",
                                original: "{\"name\":\"opn\"}",
                                corrected: "{\"name\":\"open\"}")
        try store.append(a)
        try store.append(b)

        let loaded = try store.loadAll()
        XCTAssertEqual(loaded.count, 2)
        XCTAssertEqual(loaded[0], a)
        XCTAssertEqual(loaded[1], b)
        XCTAssertEqual(try store.count(), 2)

        try? FileManager.default.removeItem(at: store.url.deletingLastPathComponent())
    }

    func test_loadAll_skipsCorruptLines() throws {
        let dir = tempDir()
        let store = CorrectionStore(directory: dir)
        let good = CorrectionEvent(intentKind: "action",
                                   original: "delete all", corrected: "confirm: delete all")
        try store.append(good)
        // Simulate a partial/garbage trailing line (e.g. a torn write).
        let handle = try FileHandle(forWritingTo: store.url)
        try handle.seekToEnd()
        try handle.write(contentsOf: Data("{ not valid json\n".utf8))
        try? handle.close()

        let loaded = try store.loadAll()
        XCTAssertEqual(loaded.count, 1, "corrupt line must be skipped, not fail the read")
        XCTAssertEqual(loaded.first, good)

        try? FileManager.default.removeItem(at: dir)
    }

    func test_loadAll_emptyWhenMissing() throws {
        let store = CorrectionStore(directory: tempDir())
        XCTAssertEqual(try store.loadAll().count, 0)
    }

    func test_concurrentAppends_doNotLoseOrInterleave() throws {
        let store = CorrectionStore(directory: tempDir())
        let n = 200
        DispatchQueue.concurrentPerform(iterations: n) { i in
            let e = CorrectionEvent(intentKind: "stress",
                                    original: "o\(i)", corrected: "c\(i)")
            try? store.append(e)
        }
        // O_APPEND atomic line writes ⇒ every event lands, none interleaves
        // into a corrupt line (loadAll would silently drop a torn line, so a
        // count < n catches interleaving too).
        let loaded = try store.loadAll()
        XCTAssertEqual(loaded.count, n)
        XCTAssertEqual(Set(loaded.map { $0.corrected }).count, n, "no lost/duplicate events")

        try? FileManager.default.removeItem(at: store.url.deletingLastPathComponent())
    }

    func test_defaults_areStamped() {
        let e = CorrectionEvent(intentKind: "dictation",
                                original: "x", corrected: "y")
        XCTAssertEqual(e.version, CorrectionEvent.currentVersion)
        XCTAssertFalse(e.id.isEmpty)
        XCTAssertGreaterThan(e.timestamp, 0)
    }
}
