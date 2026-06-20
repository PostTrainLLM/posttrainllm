import XCTest
@testable import TinyGPTModel

/// B13 — checkpoint history step-parsing + ordering.
final class CheckpointBatchLoaderTests: XCTestCase {
    func test_parseStep() {
        XCTAssertEqual(CheckpointBatchLoader.parseStep("run.step-1500.tinygpt"), 1500)
        XCTAssertEqual(CheckpointBatchLoader.parseStep("m.step-0.tinygpt"), 0)
        XCTAssertNil(CheckpointBatchLoader.parseStep("final.tinygpt"))
        XCTAssertNil(CheckpointBatchLoader.parseStep("step-.tinygpt"))
    }

    func test_orderedSortsAndDropsNonStep() {
        let files = ["r.step-300.tinygpt", "r.step-100.tinygpt", "final.tinygpt", "r.step-200.tinygpt"]
        let ord = CheckpointBatchLoader.ordered(files)
        XCTAssertEqual(ord.map(\.step), [100, 200, 300])
        XCTAssertEqual(ord.map(\.file), ["r.step-100.tinygpt", "r.step-200.tinygpt", "r.step-300.tinygpt"])
    }
}
