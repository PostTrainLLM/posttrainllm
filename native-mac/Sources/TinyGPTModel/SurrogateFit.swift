// B21 — quadratic surrogate + acquisition for the micro-AutoMixer.
//
// Fits score ≈ quadratic(mix) by ridge least-squares over the corpus weights,
// then proposes the next mix to try by maximising predicted improvement over
// the best score seen so far (the V1 acquisition; GP/true-EI is the V2 target,
// per the PRD). Pure math — no MLX, fully unit-testable.
//
// DoReMi (Xie et al. 2023) is the rigorous mixture-optimisation reference;
// this is the 200-LOC quadratic-surrogate scale-down for one Mac.
import Foundation

public struct QuadraticSurrogate: Sendable {
    public let k: Int
    public let weights: [Double]   // one per quadratic feature

    /// Feature map: [1, x_0…x_{k-1}, x_i·x_j (i≤j)].
    static func features(_ x: [Float]) -> [Double] {
        let xd = x.map(Double.init)
        var f: [Double] = [1.0]
        f.append(contentsOf: xd)
        for i in 0..<xd.count { for j in i..<xd.count { f.append(xd[i] * xd[j]) } }
        return f
    }

    /// Ridge least-squares fit of score onto the quadratic features.
    public static func fit(mixes: [[Float]], scores: [Float], ridge: Double = 1e-3) -> QuadraticSurrogate {
        precondition(mixes.count == scores.count && !mixes.isEmpty, "mixes/scores mismatch")
        let k = mixes[0].count
        let X = mixes.map(features)
        let p = X[0].count
        var A = [[Double]](repeating: [Double](repeating: 0, count: p), count: p)
        var b = [Double](repeating: 0, count: p)
        for (row, y) in zip(X, scores) {
            for i in 0..<p {
                b[i] += row[i] * Double(y)
                for j in 0..<p { A[i][j] += row[i] * row[j] }
            }
        }
        for i in 0..<p { A[i][i] += ridge }
        return QuadraticSurrogate(k: k, weights: solve(A, b))
    }

    public func predict(_ x: [Float]) -> Double {
        zip(Self.features(x), weights).reduce(0) { $0 + $1.0 * $1.1 }
    }
}

public struct MixProposal: Sendable, Equatable {
    public let mix: [Float]
    public let predicted: Double
    public let improvement: Double   // predicted − bestObserved (the acquisition)
}

public enum SurrogateProposer {
    /// Pick the candidate maximising predicted improvement over `bestObserved`.
    public static func propose(surrogate: QuadraticSurrogate, candidates: [[Float]],
                               bestObserved: Float) -> MixProposal {
        precondition(!candidates.isEmpty, "need candidates")
        var best = MixProposal(mix: candidates[0],
                               predicted: surrogate.predict(candidates[0]),
                               improvement: surrogate.predict(candidates[0]) - Double(bestObserved))
        for c in candidates.dropFirst() {
            let p = surrogate.predict(c)
            let imp = p - Double(bestObserved)
            if imp > best.improvement {
                best = MixProposal(mix: c, predicted: p, improvement: imp)
            }
        }
        return best
    }
}

/// Solve A·x = b (A square, symmetric-PD here) via Gaussian elimination with
/// partial pivoting. Small p (≤ ~30 for ≤6 corpora), so this is plenty.
func solve(_ Ain: [[Double]], _ bin: [Double]) -> [Double] {
    var A = Ain, b = bin
    let n = b.count
    for col in 0..<n {
        var piv = col
        for r in (col + 1)..<n where abs(A[r][col]) > abs(A[piv][col]) { piv = r }
        if piv != col { A.swapAt(piv, col); b.swapAt(piv, col) }
        let d = A[col][col]
        if abs(d) < 1e-18 { continue }
        for r in (col + 1)..<n {
            let f = A[r][col] / d
            if f == 0 { continue }
            for c in col..<n { A[r][c] -= f * A[col][c] }
            b[r] -= f * b[col]
        }
    }
    var x = [Double](repeating: 0, count: n)
    for r in stride(from: n - 1, through: 0, by: -1) {
        var s = b[r]
        for c in (r + 1)..<n { s -= A[r][c] * x[c] }
        x[r] = abs(A[r][r]) < 1e-18 ? 0 : s / A[r][r]
    }
    return x
}
