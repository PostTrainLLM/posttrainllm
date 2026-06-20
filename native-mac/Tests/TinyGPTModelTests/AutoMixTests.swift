import XCTest
@testable import TinyGPTModel

/// B21 — micro-AutoMixer pure-math cores: the Dirichlet `MixSampler` and the
/// quadratic `SurrogateFit` + acquisition. These are the search engine; the
/// orchestrator just wires them around train/eval subprocesses.
final class AutoMixTests: XCTestCase {

    // MARK: MixSampler

    func test_mixes_areValidSimplexPoints() {
        let mixes = MixSampler.sampleMixes(k: 4, count: 20, alpha: 1.0, seed: 123)
        XCTAssertEqual(mixes.count, 20)
        for m in mixes {
            XCTAssertEqual(m.count, 4)
            XCTAssertEqual(m.reduce(0, +), 1.0, accuracy: 1e-5, "mix must sum to 1")
            XCTAssertTrue(m.allSatisfy { $0 >= 0 }, "weights non-negative")
        }
    }

    func test_uniformAnchor_isFirstAndExact() {
        let mixes = MixSampler.sampleMixes(k: 5, count: 3, seed: 1, includeUniform: true)
        XCTAssertEqual(mixes[0], Array(repeating: Float(1.0 / 5.0), count: 5))
    }

    func test_deterministic_bySeed() {
        let a = MixSampler.sampleMixes(k: 3, count: 6, seed: 42)
        let b = MixSampler.sampleMixes(k: 3, count: 6, seed: 42)
        let c = MixSampler.sampleMixes(k: 3, count: 6, seed: 7)
        XCTAssertEqual(a, b, "same seed → identical mixes")
        XCTAssertNotEqual(a, c, "different seed → different mixes")
    }

    // MARK: SurrogateFit + proposer

    /// Fit on a known concave quadratic score = −Σ(xᵢ−tᵢ)² (max at the target
    /// mix) and check the surrogate + proposer steer toward the target.
    func test_surrogate_recoversOptimumDirection() {
        let target: [Float] = [0.6, 0.3, 0.1]
        func trueScore(_ x: [Float]) -> Float {
            -zip(x, target).reduce(Float(0)) { $0 + ($1.0 - $1.1) * ($1.0 - $1.1) }
        }
        let train = MixSampler.sampleMixes(k: 3, count: 30, seed: 99)
        let scores = train.map(trueScore)
        let surrogate = QuadraticSurrogate.fit(mixes: train, scores: scores)

        let best = scores.max()!
        let candidates = MixSampler.sampleMixes(k: 3, count: 300, seed: 2024, includeUniform: false)
        let prop = SurrogateProposer.propose(surrogate: surrogate, candidates: candidates, bestObserved: best)

        let uniform: [Float] = [1.0/3, 1.0/3, 1.0/3]
        func dist(_ a: [Float], _ b: [Float]) -> Float {
            (zip(a, b).reduce(Float(0)) { $0 + ($1.0 - $1.1) * ($1.0 - $1.1) }).squareRoot()
        }
        // proposed mix is nearer the true optimum than the uniform anchor…
        XCTAssertLessThan(dist(prop.mix, target), dist(uniform, target))
        // …and the surrogate scores the target region above uniform.
        XCTAssertGreaterThan(surrogate.predict(prop.mix), surrogate.predict(uniform))
        // surrogate fit is accurate on a truly-quadratic target
        XCTAssertEqual(surrogate.predict(target), 0.0, accuracy: 0.02)
    }

    /// The linear solver recovers the solution of a small known system.
    func test_solve_smallSystem() {
        // [[2,1],[1,3]] x = [3,5] → x = [0.8, 1.4]
        let x = solve([[2, 1], [1, 3]], [3, 5])
        XCTAssertEqual(x[0], 0.8, accuracy: 1e-9)
        XCTAssertEqual(x[1], 1.4, accuracy: 1e-9)
    }
}
