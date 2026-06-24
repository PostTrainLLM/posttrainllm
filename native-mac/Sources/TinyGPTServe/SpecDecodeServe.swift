import Foundation
import MLX
import TinyGPTModel

// Cache-aware speculative decoding for `serve` (greedy / temperature 0).
//
// Why a serve-specific implementation instead of reusing
// `SpeculativeDecode.step` from the CLI: that version is NON-cached — it
// re-feeds the full context to both models every step (O(T) per step). serve's
// decode loop is built around a per-request KV cache (the uncached + LoRA path
// leaks MLX graph nodes and SIGSEGVs at ~500 tokens), and a measurement showed
// the uncached path is a net LOSS on serve workloads even though acceptance is
// high. This version keeps a KV cache for BOTH the target and the draft,
// advancing them through `forwardCached` and rolling them back with
// `KVCache.rewind` on rejection.
//
// Single target forward per burst via SEED-CARRY: the last token emitted by a
// burst is not committed to the cache; it is carried as `seed` and fed as the
// FIRST element of the next verify batch ([seed, p_0..p_{k-1}]). That batch's
// k+1 output positions give the distribution after the seed and after each
// proposal — so the correction/bonus token is read straight from the verify
// logits with no extra forward. (An earlier version paid a second target
// forward per burst to re-establish the next logits, which roughly halved the
// win.)
//
// Measured gate (4B target + 0.6B draft, T=0): acceptance 3.03 tok/forward,
// draft/target per-forward cost c≈0.155 → projected ~1.7× with seed-carry.
//
// Losslessness: every emitted token equals the target's greedy argmax given the
// committed context, so output is BYTE-IDENTICAL to the plain cached
// single-token greedy loop. Speculation only changes wall-clock.
extension Serve.Server {

    /// Burst size: the draft proposes this many tokens per target verify.
    static let speculativeK = 4

    /// Build a fresh KV cache for the draft model, prefilled on the same
    /// bounded prompt the target was prefilled on.
    func specPrefillDraft(draft: AnyModel, draftNLayers: Int,
                          kept: [Int], tokenDType: DType) -> KVCache {
        let cache = KVCache(nLayers: draftNLayers)
        let arr = MLXArray(kept.map { Int32($0) }, [1, kept.count]).asType(tokenDType)
        let logits = draft.forwardCached(arr, cache: cache)
        eval(logits[0..., logits.shape[1] - 1, 0...])
        return cache
    }

    /// One cache-aware greedy speculative iteration.
    ///
    /// Preconditions: temperature == 0, no grammar constraint. Caches hold the
    /// committed context EXCLUDING `seed` (the last emitted token). Returns the
    /// newly emitted tokens (1...k+1); the LAST one is the next seed. After the
    /// call both caches hold the prior context + `seed` + the accepted
    /// proposals (the returned seed stays held out for the next call).
    func specStepGreedy(draft: AnyModel,
                        targetCache: KVCache, draftCache: KVCache,
                        seed: Int, k: Int, tokenDType: DType) -> [Int] {
        // 1. Draft: feed the carried seed, then propose k tokens greedily.
        //    Both advance draftCache (by 1 + k).
        let seedArr = MLXArray([Int32(seed)], [1, 1]).asType(tokenDType)
        var draftLast = draft.forwardCached(seedArr, cache: draftCache)[0..., 0, 0...]
        eval(draftLast)
        var proposals: [Int] = []
        proposals.reserveCapacity(k)
        for _ in 0..<k {
            let p = Int(argMax(draftLast, axis: -1).item(Int32.self))
            proposals.append(p)
            let arr = MLXArray([Int32(p)], [1, 1]).asType(tokenDType)
            draftLast = draft.forwardCached(arr, cache: draftCache)[0..., 0, 0...]
            eval(draftLast)
        }

        // 2. Target verifies [seed, p_0..p_{k-1}] in ONE forward (cache grows
        //    by k+1). vLogits[:, j, :] is the distribution AFTER the j-th input:
        //    j=0 follows the seed (predicts the slot of p_0); j=i follows p_{i-1}
        //    (predicts p_i); j=k follows p_{k-1} (the bonus slot).
        let vIn = MLXArray(([seed] + proposals).map { Int32($0) }, [1, k + 1]).asType(tokenDType)
        let vLogits = model.forwardCached(vIn, cache: targetCache)
        eval(vLogits)

        // 3. Greedy accept: proposal j is accepted iff it equals the target's
        //    argmax at d_j = vLogits[:, j, :]. First mismatch emits the target's
        //    token (correction) and stops; all-accept appends the bonus token.
        var emitted: [Int] = []
        emitted.reserveCapacity(k + 1)
        var accepted = k
        for j in 0..<k {
            let tj = Int(argMax(vLogits[0..., j, 0...], axis: -1).item(Int32.self))
            emitted.append(tj)
            if tj != proposals[j] {
                accepted = j
                break
            }
        }
        if accepted == k {
            let bonus = Int(argMax(vLogits[0..., k, 0...], axis: -1).item(Int32.self))
            emitted.append(bonus)
        }

        // 4. Commit: both caches are at +(k+1) [seed + k proposals]. Keep the
        //    seed + `accepted` proposals; drop the rest. The last emitted token
        //    (correction/bonus) is the next seed and stays OUT of the cache.
        let drop = k - accepted
        if drop > 0 {
            targetCache.rewind(by: drop)
            draftCache.rewind(by: drop)
        }
        return emitted
    }
}
