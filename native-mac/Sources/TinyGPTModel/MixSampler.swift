// B21 — Dirichlet sampler over corpora for the micro-AutoMixer.
//
// Samples candidate data-mix ratios (one weight per corpus, summing to 1)
// from a symmetric Dirichlet(α). Deterministic given a seed (Splitmix64), so
// the search is reproducible. Pure math — no MLX, fully unit-testable.
import Foundation

public enum MixSampler {

    /// Sample `count` mixes over `k` corpora from a symmetric Dirichlet(α).
    /// Each mix is length-`k`, non-negative, sums to 1. When `includeUniform`,
    /// the first mix is the uniform anchor (1/k each) and `count-1` are drawn.
    public static func sampleMixes(k: Int, count: Int, alpha: Float = 1.0,
                                   seed: UInt64, includeUniform: Bool = true) -> [[Float]] {
        precondition(k >= 1 && count >= 1, "k and count must be >= 1")
        var gen = Splitmix64Generator(state: seed == 0 ? 0xD1CE_5EED_F00D : seed)
        var mixes: [[Float]] = []
        if includeUniform { mixes.append(Array(repeating: 1.0 / Float(k), count: k)) }
        while mixes.count < count { mixes.append(dirichlet(k: k, alpha: alpha, gen: &gen)) }
        return mixes
    }

    /// One symmetric-Dirichlet(α) draw via Gamma(α,1) normalisation.
    static func dirichlet(k: Int, alpha: Float, gen: inout Splitmix64Generator) -> [Float] {
        let g = (0..<k).map { _ in gammaMarsaglia(shape: Double(max(1e-3, alpha)), gen: &gen) }
        let s = g.reduce(0, +)
        if s <= 0 { return Array(repeating: 1.0 / Float(k), count: k) }
        return g.map { Float($0 / s) }
    }

    /// Marsaglia–Tsang Gamma(shape, 1) sampler (shape > 0); boost trick for shape < 1.
    static func gammaMarsaglia(shape: Double, gen: inout Splitmix64Generator) -> Double {
        if shape < 1 {
            let u = Double.random(in: 1e-12..<1, using: &gen)
            return gammaMarsaglia(shape: shape + 1, gen: &gen) * pow(u, 1.0 / shape)
        }
        let d = shape - 1.0 / 3.0
        let c = 1.0 / (9.0 * d).squareRoot()
        while true {
            let x = standardNormal(gen: &gen)
            let v0 = 1 + c * x
            if v0 <= 0 { continue }
            let v = v0 * v0 * v0
            let u = Double.random(in: 1e-12..<1, using: &gen)
            if log(u) < 0.5 * x * x + d - d * v + d * log(v) { return d * v }
        }
    }

    /// Standard normal via Box–Muller.
    static func standardNormal(gen: inout Splitmix64Generator) -> Double {
        let u1 = Double.random(in: 1e-12..<1, using: &gen)
        let u2 = Double.random(in: 0..<1, using: &gen)
        return (-2 * log(u1)).squareRoot() * cos(2 * Double.pi * u2)
    }
}
