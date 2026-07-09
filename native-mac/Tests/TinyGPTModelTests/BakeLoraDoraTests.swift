import XCTest
@testable import TinyGPTModel

final class BakeLoraDoraTests: XCTestCase {

    func test_doraBake_matchesRuntimeEffectiveWeight() throws {
        let outF = 5, inF = 7, r = 3
        let scale: Float = 2.0
        var rng = SeededRNG(seed: 42)

        let base = (0..<outF * inF).map { _ in rng.nextFloat(-0.5, 0.5) }
        let loraA = (0..<inF * r).map { _ in rng.nextFloat(-0.2, 0.2) }
        let loraB = (0..<r * outF).map { _ in rng.nextFloat(-0.2, 0.2) }
        let m = (0..<outF).map { _ in rng.nextFloat(0.1, 2.0) }

        let matrices = LoraBake.Matrices(
            loraA: loraA, aShape: [inF, r],
            loraB: loraB, bShape: [r, outF],
            m: m, scale: scale)
        let shape = [outF, inF]

        let baked = try LoraBake.bake(weight: base, shape: shape, matrices: matrices)
        // Independent reference implementation of the DoraLinear forward's
        // effective weight (Lora.swift): V = W + scale·(A@B)ᵀ, then
        // m ⊙ V / sqrt(‖V_row‖² + 1e-9). Comparing bake() against another
        // LoraBake entry point would share internals and prove nothing.
        var expected = [Float](repeating: 0, count: outF * inF)
        for j in 0..<outF {
            var row = [Float](repeating: 0, count: inF)
            for i in 0..<inF {
                var ab: Float = 0
                for k in 0..<r { ab += loraA[i * r + k] * loraB[k * outF + j] }
                row[i] = base[j * inF + i] + scale * ab
            }
            let norm = sqrt(row.reduce(Float(0)) { $0 + $1 * $1 } + 1e-9)
            for i in 0..<inF { expected[j * inF + i] = m[j] * row[i] / norm }
        }
        assertAllClose(baked, expected, tol: 1e-5)
    }

    func test_plainLoraBake_unchanged() throws {
        let outF = 4, inF = 6, r = 2
        let scale: Float = 0.5
        var rng = SeededRNG(seed: 7)

        let base = (0..<outF * inF).map { _ in rng.nextFloat(-1, 1) }
        let loraA = (0..<inF * r).map { _ in rng.nextFloat(-0.3, 0.3) }
        let loraB = (0..<r * outF).map { _ in rng.nextFloat(-0.3, 0.3) }

        let matrices = LoraBake.Matrices(
            loraA: loraA, aShape: [inF, r],
            loraB: loraB, bShape: [r, outF],
            m: nil, scale: scale)
        let shape = [outF, inF]

        let baked = try LoraBake.bake(weight: base, shape: shape, matrices: matrices)
        let expected = plainLoraWeight(base: base, shape: shape,
                                       loraA: loraA, loraB: loraB, scale: scale)
        assertAllClose(baked, expected, tol: 1e-5)
    }

    // MARK: - helpers

    private func plainLoraWeight(base: [Float], shape: [Int],
                                 loraA: [Float], loraB: [Float],
                                 scale: Float) -> [Float] {
        let outF = shape[0], inF = shape[1], r = inF > 0 ? loraA.count / inF : 0
        var out = base
        for j in 0..<outF {
            for i in 0..<inF {
                var acc: Float = 0
                for k in 0..<r {
                    acc += loraB[k * outF + j] * loraA[i * r + k]
                }
                out[j * inF + i] += scale * acc
            }
        }
        return out
    }

    private func assertAllClose(_ a: [Float], _ b: [Float], tol: Float,
                                file: StaticString = #file, line: UInt = #line) {
        XCTAssertEqual(a.count, b.count, file: file, line: line)
        for i in 0..<a.count {
            XCTAssertEqual(a[i], b[i], accuracy: tol, "index \(i)", file: file, line: line)
        }
    }
}

/// Tiny deterministic PRNG — no MLX / Metal required.
private struct SeededRNG {
    private var state: UInt64
    init(seed: UInt64) { state = seed != 0 ? seed : 1 }

    mutating func nextFloat(_ lo: Float, _ hi: Float) -> Float {
        state = state &* 6364136223846793005 &+ 1
        let unit = Float(state >> 33) / Float(UInt32.max)
        return lo + unit * (hi - lo)
    }
}
