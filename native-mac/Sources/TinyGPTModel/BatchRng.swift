import Foundation

/// C9 — seeded batch-sampling RNG.
///
/// `Int.random(in:)` and friends backed by `SystemRandomNumberGenerator`
/// are not seedable; that means corpus samplers (`Trainer`'s built-in
/// byte/token/IO-window samplers, `SFTCorpus`, `PreferenceCorpus`) draw
/// different windows on every run even when the user passes `--seed N`.
/// Model-init randomness goes through MLXRandom which IS seedable, so
/// only batch sampling was the open determinism gap before this.
///
/// `BatchRng` is a process-wide handle: call `seed(_:)` from
/// `posttrainllm train` when `--seed` is supplied; then sampler code calls
/// `randomInt(in:)` instead of `Int.random(in:)`. When unseeded, the
/// helper falls back to `Int.random(in:)` so production behaviour is
/// unchanged (no global determinism imposed implicitly).
///
/// Splitmix64 is the seeded generator (small, fast, statistically
/// strong — same family used by the JDK's `SplittableRandom`). The
/// helper is `NSLock`-guarded so concurrent samplers in the SFT
/// bucketed path don't race on the generator state.
public enum BatchRng {

    private static let lock = NSLock()
    nonisolated(unsafe) private static var generator: Splitmix64Generator? = nil

    /// Seed the process-wide batch-sampling generator. Idempotent —
    /// calling with the same seed reproduces the same sequence.
    public static func seed(_ s: UInt64) {
        lock.lock(); defer { lock.unlock() }
        generator = Splitmix64Generator(state: s == 0 ? 0xDEADBEEFCAFEBABE : s)
    }

    /// Clear the seeded state. Subsequent `randomInt` calls fall back
    /// to `Int.random`. Mostly useful in tests.
    public static func reset() {
        lock.lock(); defer { lock.unlock() }
        generator = nil
    }

    /// `Int.random(in: range)` when unseeded; deterministic Splitmix64
    /// draw when seeded. Drop-in.
    public static func randomInt(in range: Range<Int>) -> Int {
        precondition(!range.isEmpty, "BatchRng.randomInt called with empty range")
        lock.lock(); defer { lock.unlock() }
        if var gen = generator {
            let v = Int.random(in: range, using: &gen)
            generator = gen  // persist updated state across calls
            return v
        }
        return Int.random(in: range)
    }
}

/// Splitmix64 — small (~10 lines), fast, statistically strong (passes
/// BigCrush). Used as JDK's `SplittableRandom` core. Output is uniformly
/// distributed UInt64; the host stdlib uses it via `Int.random(in:using:)`.
public struct Splitmix64Generator: RandomNumberGenerator {
    public var state: UInt64

    public init(state: UInt64) { self.state = state }

    public mutating func next() -> UInt64 {
        state = state &+ 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}
