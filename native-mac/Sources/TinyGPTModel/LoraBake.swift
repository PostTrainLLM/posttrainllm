import Foundation

/// Fold a LoRA (or DoRA) adapter delta into a dense Linear weight.
///
/// Safetensors / PyTorch store `weight` as `[out, in]`. Adapter matrices
/// are `loraA [in, r]`, `loraB [r, out]`. Plain LoRA baking:
///
///     W_new = W_base + scale · (loraA @ loraB)ᵀ
///
/// DoRA baking matches `DoraLinear.callAsFunction` — the baked weight is
/// the active matrix the runtime would use with no adapter attached:
///
///     V       = W_base + scale · (loraA @ loraB)ᵀ
///     W_new   = diag(m) · rowwise_unit(V)
public enum LoraBake {
    public struct Matrices: Sendable {
        public let loraA: [Float]
        public let aShape: [Int]   // [in, r]
        public let loraB: [Float]
        public let bShape: [Int]   // [r, out]
        /// Per-output-row magnitude. Non-nil selects DoRA baking.
        public let m: [Float]?
        public let scale: Float

        public init(loraA: [Float], aShape: [Int],
                    loraB: [Float], bShape: [Int],
                    m: [Float]? = nil, scale: Float) {
            self.loraA = loraA; self.aShape = aShape
            self.loraB = loraB; self.bShape = bShape
            self.m = m; self.scale = scale
        }
    }

    public struct Error: Swift.Error, CustomStringConvertible, Sendable {
        public let message: String
        public init(_ message: String) { self.message = message }
        public var description: String { message }
    }

    /// Bake adapter matrices into `weight` (row-major `[out, in]`).
    public static func bake(weight: [Float], shape: [Int],
                            matrices: Matrices) throws -> [Float] {
        let baked = try computeLoRADelta(weight: weight, shape: shape,
                                         matrices: matrices)
        if let m = matrices.m {
            return try applyDoraMagnitude(V: baked.V, shape: shape, m: m)
        }
        return baked.weightPlusDelta
    }

    // MARK: - internals

    private struct LoRADelta {
        let V: [Float]
        let weightPlusDelta: [Float]
    }

    private static func computeLoRADelta(weight: [Float], shape: [Int],
                                         matrices: Matrices) throws -> LoRADelta {
        guard shape.count == 2 else {
            throw Error("weight shape \(shape) is not 2-D")
        }
        let outF = shape[0]
        let inF = shape[1]
        let n = outF * inF
        guard weight.count == n else {
            throw Error("weight buffer size \(weight.count) != shape product \(n)")
        }
        guard matrices.aShape.count == 2,
              matrices.aShape[0] == inF,
              matrices.aShape[1] == matrices.bShape[0],
              matrices.bShape.count == 2,
              matrices.bShape[1] == outF else {
            throw Error("shape mismatch: weight [\(outF), \(inF)], A=\(matrices.aShape), B=\(matrices.bShape)")
        }
        if let m = matrices.m, m.count != outF {
            throw Error("magnitude length \(m.count) != out=\(outF)")
        }

        let r = matrices.aShape[1]
        var V = weight
        let scale = matrices.scale
        matrices.loraB.withUnsafeBufferPointer { bPtr in
            matrices.loraA.withUnsafeBufferPointer { aPtr in
                V.withUnsafeMutableBufferPointer { vPtr in
                    for j in 0..<outF {
                        for i in 0..<inF {
                            var acc: Float = 0
                            for k in 0..<r {
                                acc += bPtr[k * outF + j] * aPtr[i * r + k]
                            }
                            vPtr[j * inF + i] += scale * acc
                        }
                    }
                }
            }
        }
        return LoRADelta(V: V, weightPlusDelta: V)
    }

    /// `W_new[j, i] = m[j] · V[j, i] / ‖V[j, :]‖₂` — matches `DoraLinear`.
    private static func applyDoraMagnitude(V: [Float], shape: [Int],
                                           m: [Float]) throws -> [Float] {
        let outF = shape[0]
        let inF = shape[1]
        guard m.count == outF else {
            throw Error("magnitude length \(m.count) != out=\(outF)")
        }
        var Wnew = [Float](repeating: 0, count: V.count)
        let eps: Float = 1e-9
        for j in 0..<outF {
            var rowSq: Float = 0
            for i in 0..<inF {
                let v = V[j * inF + i]
                rowSq += v * v
            }
            let rowNorm = sqrt(rowSq + eps)
            let mag = m[j]
            for i in 0..<inF {
                Wnew[j * inF + i] = mag * V[j * inF + i] / rowNorm
            }
        }
        return Wnew
    }
}