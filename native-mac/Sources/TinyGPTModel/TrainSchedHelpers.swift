// Pure helpers — scheduler math + sliding-window loss spike detector.
// Hoisted out of `TrainSupport.swift` so the unit tests in
// `TinyGPTModelTests` can reach them. Train.swift calls these directly.
import Foundation

// MARK: - Warmup-stable-decay (WSD) schedule

/// Shape of the WSD decay phase (B11). `1-sqrt` is the MiniCPM default;
/// `cosine`/`linear` are provided for ablations and parity with other
/// schedulers. Parse from a CLI string via `init(rawValue:)`.
public enum WSDDecayShape: String, Sendable, CaseIterable {
    case oneMinusSqrt = "1-sqrt"
    case cosine
    case linear
}

/// Warmup-stable-decay (WSD) learning rate, MiniCPM / SmolLM-style.
///
/// - `0 ≤ step < warmup`: linear ramp from 0 → maxLR
/// - `warmup ≤ step < total − decaySteps`: stable at maxLR
/// - `total − decaySteps ≤ step < total`: `decayShape` decay maxLR → minLR
/// - `step ≥ total`: minLR
///
/// The 1−√(t) decay shape (Hu et al., 2024, MiniCPM §4.3) decays faster
/// than half-cosine in the early decay window and is empirically the
/// better choice for the final-anneal phase on small models — it stays
/// the default. `cosine` (half-cosine) and `linear` are selectable via
/// `--decay-shape` for ablations.
///
/// The stable middle phase makes WSD friendly to mid-run resume and to
/// extending pretraining without re-tuning a cosine envelope. Use
/// `decaySteps` as your annealing window — switch corpus to a curated
/// high-quality subset when step crosses `total − decaySteps`.
public func lrAtWSD(step: Int, total: Int, warmup: Int, decaySteps: Int,
                    maxLR: Float, minLR: Float,
                    decayShape: WSDDecayShape = .oneMinusSqrt) -> Float {
    if step < warmup {
        return maxLR * Float(step + 1) / Float(max(1, warmup))
    }
    if step >= total { return minLR }
    let decayStart = total - max(0, decaySteps)
    if step < decayStart { return maxLR }
    let progress = Float(step - decayStart) / Float(max(1, decaySteps))
    switch decayShape {
    case .oneMinusSqrt:
        let shape = Float(Foundation.sqrt(Double(progress)))
        return maxLR - (maxLR - minLR) * shape
    case .linear:
        return maxLR - (maxLR - minLR) * progress
    case .cosine:
        let c = 0.5 * (1 + Float(Foundation.cos(Double.pi * Double(progress))))
        return minLR + (maxLR - minLR) * c
    }
}

// MARK: - Loss spike detector

/// Sliding-window loss spike detector. v1 is **observe-only**: each
/// `observe(loss:step:)` call returns whether the latest loss exceeds
/// `factor × moving-average` over the last `window` steps. The caller
/// chooses the response (log, save an emergency checkpoint, pause).
///
/// Auto-rollback to a prior checkpoint is a v2 follow-up — the current
/// Adam-state-doesn't-persist limitation means a rollback already implies
/// a partial restart pain (see `--resume` docs on `tinygpt train`). v1
/// gives the operator an early warning so they can investigate or
/// `--resume` with a lower LR.
public struct LossSpikeDetector {
    public let window: Int
    public let factor: Float
    private var buf: [Float] = []
    private var lastSpikeStep: Int = -1

    public init(window: Int = 50, factor: Float = 3.0) {
        self.window = max(2, window)
        self.factor = max(1.01, factor)
        self.buf.reserveCapacity(self.window)
    }

    /// Observe one step's loss. Returns `(isSpike, movingAverage)`. The
    /// detector silently warms up for the first `window` observations.
    /// Sustained spikes are debounced: the next signal can fire at earliest
    /// `window/2` steps after the last one.
    public mutating func observe(loss: Float, step: Int) -> (spike: Bool, ma: Float) {
        guard buf.count >= window else {
            buf.append(loss)
            return (false, 0)
        }
        let sum = buf.reduce(0, +)
        let ma = sum / Float(buf.count)
        buf.removeFirst()
        buf.append(loss)
        let cooled = (step - lastSpikeStep) > window / 2
        let isSpike = loss.isFinite && ma.isFinite && loss > factor * ma && cooled
        if isSpike { lastSpikeStep = step }
        return (isSpike, ma)
    }
}

// MARK: - Loss spike recovery controller (B12)

/// What the train loop should do when the detector fires.
public enum SpikeRecoveryMode: String, Sendable, CaseIterable {
    case off    // detector not consulted
    case warn   // log only (v1 behaviour)
    case on     // auto-recover: cut LR, abort after too many spikes
}

/// The action the controller decides on a detected spike.
public enum SpikeAction: Equatable, Sendable {
    case none
    case warn(ma: Float)
    case dropLR(multiplier: Float, ma: Float)
    case abort(spikes: Int)
}

/// Spike-recovery controller layered on `LossSpikeDetector` (B12).
///
/// Recovery mechanism is an adaptive **LR cut** (multiply the schedule by
/// `lrDropFactor` each spike) rather than a checkpoint rollback: it needs
/// no checkpoint I/O and never discards optimiser (Adam) state, so it's
/// strictly safer than restore-and-resume. After `maxDrops` spikes the run
/// aborts — a sustained spike storm means the LR/data is wrong, not a blip.
public struct SpikeController {
    public let mode: SpikeRecoveryMode
    public let lrDropFactor: Float
    public let maxDrops: Int
    public private(set) var lrMultiplier: Float = 1.0
    public private(set) var drops: Int = 0

    public init(mode: SpikeRecoveryMode, lrDropFactor: Float = 0.5, maxDrops: Int = 3) {
        self.mode = mode
        self.lrDropFactor = min(0.999, max(0.01, lrDropFactor))
        self.maxDrops = max(1, maxDrops)
    }

    /// Decide what to do given a detected spike. Updates `lrMultiplier`.
    public mutating func onSpike(ma: Float) -> SpikeAction {
        switch mode {
        case .off:  return .none
        case .warn: return .warn(ma: ma)
        case .on:
            drops += 1
            if drops > maxDrops { return .abort(spikes: drops) }
            lrMultiplier *= lrDropFactor
            return .dropLR(multiplier: lrMultiplier, ma: ma)
        }
    }
}
