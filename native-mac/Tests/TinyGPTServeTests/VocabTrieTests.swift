import XCTest
@testable import TinyGPTServe

final class VocabTrieTests: XCTestCase {
    private final class PrefixFSM: ServeByteFSM {
        private let accepted: [[UInt8]]
        private var consumed: [UInt8]
        let isComplete: Bool

        init(accepted: [String], consumed: [UInt8] = [], isComplete: Bool = false) {
            self.accepted = accepted.map { Array($0.utf8) }
            self.consumed = consumed
            self.isComplete = isComplete
        }

        func cloneForServe() -> ServeByteFSM {
            PrefixFSM(accepted: accepted.map { String(decoding: $0, as: UTF8.self) },
                      consumed: consumed,
                      isComplete: isComplete)
        }

        func acceptBytes(_ bytes: [UInt8]) -> Bool {
            let candidate = consumed + bytes
            guard accepted.contains(where: { $0.starts(with: candidate) }) else {
                return false
            }
            consumed = candidate
            return true
        }

        func acceptByte(_ byte: UInt8) -> Bool {
            acceptByteDefault(byte)
        }
    }

    func testMaskWalksSharedPrefixesAndSkipsInvalidOrEmptyTokens() {
        let trie = VocabTrie(tokenBytes: [[], Array("a".utf8), Array("ab".utf8),
                                                Array("ac".utf8), Array("b".utf8)])
        var mask = [Float](repeating: -.infinity, count: trie.vocabSize)

        trie.mask(fsm: PrefixFSM(accepted: ["ab", "b"]), into: &mask)

        XCTAssertEqual(mask[1], 0)
        XCTAssertEqual(mask[2], 0)
        XCTAssertEqual(mask[4], 0)
        XCTAssertEqual(mask[0], -.infinity)
        XCTAssertEqual(mask[3], -.infinity)
    }

    func testMaskLeavesOutputUntouchedWhenGrammarIsComplete() {
        let trie = VocabTrie(tokenBytes: [Array("a".utf8)])
        var mask = [Float](repeating: -.infinity, count: 1)

        trie.mask(fsm: PrefixFSM(accepted: ["a"], isComplete: true), into: &mask)

        XCTAssertEqual(mask, [-.infinity])
    }
}
