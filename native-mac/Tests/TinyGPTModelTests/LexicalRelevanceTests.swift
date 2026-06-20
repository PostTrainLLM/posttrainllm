import XCTest
@testable import TinyGPTModel

/// B25 (V1) — lexical query→sentence relevance for extractive compression.
final class LexicalRelevanceTests: XCTestCase {
    let sentences = [
        "RoPE encodes positions via rotation.",
        "The cat sat on the mat.",
        "Rotary position embeddings rotate query and key vectors.",
    ]
    let query = "what is RoPE rotary position"

    func test_tokenize_dropsShortTokens() {
        // "a" and "of" length<2? "of" is len 2 (kept); single chars dropped.
        XCTAssertEqual(LexicalRelevance.tokenize("A cat, of 9 RoPE-x!"),
                       ["cat", "of", "rope"])
    }

    func test_relevantSentencesScoreHigher() {
        let s = LexicalRelevance.scoreSentences(query: query, sentences: sentences)
        XCTAssertEqual(s.count, 3)
        XCTAssertEqual(s[1], 0.0, accuracy: 1e-9, "off-topic sentence scores 0")
        XCTAssertGreaterThan(s[0], 0)
        XCTAssertGreaterThan(s[2], 0)
    }

    func test_thresholdKeepsRelevantDropsOffTopic() {
        let s = LexicalRelevance.scoreSentences(query: query, sentences: sentences)
        let keep = LexicalRelevance.selectKeep(scores: s, sentences: sentences, threshold: 0.01)
        XCTAssertEqual(keep, [0, 2], "keeps the two RoPE sentences, drops the cat")
    }

    func test_keepFrac_budgetsByLengthHighestFirst() {
        let s = LexicalRelevance.scoreSentences(query: query, sentences: sentences)
        // tiny budget → at least one sentence, and it's a relevant one
        let keep = LexicalRelevance.selectKeep(scores: s, sentences: sentences, keepFrac: 0.05)
        XCTAssertFalse(keep.isEmpty)
        XCTAssertFalse(keep.contains(1), "off-topic sentence not selected first")
        XCTAssertEqual(keep, keep.sorted(), "kept indices returned in original order")
    }

    func test_maxSentences_caps() {
        let s = LexicalRelevance.scoreSentences(query: query, sentences: sentences)
        let keep = LexicalRelevance.selectKeep(scores: s, sentences: sentences,
                                               threshold: 0.0, maxSentences: 1)
        XCTAssertEqual(keep.count, 1)
    }

    func test_emptyQuery_scoresZero() {
        let s = LexicalRelevance.scoreSentences(query: "", sentences: sentences)
        XCTAssertEqual(s, [0, 0, 0])
    }
}
