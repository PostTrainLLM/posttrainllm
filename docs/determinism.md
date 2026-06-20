# Determinism contract

`tinygpt train --seed <UInt64>` now seeds **both** of TinyGPT's two
randomness surfaces:

1. **MLXRandom** — drives every MLX op that draws random numbers:
   model parameter init (He / Xavier / etc.), GPU-side dropout,
   embedding noise (NEFTune), and any other MLX-sourced randomness
   inside the forward/backward pass.
2. **BatchRng** — a Splitmix64-backed host generator that wraps every
   corpus sampler's window pick (`ByteCorpus.sampleBatchRaw`,
   `TokenizedCorpus.sampleBatchRaw`, `IOSampler`, `SFTCorpus`,
   `PreferenceCorpus` — see `Sources/TinyGPTModel/BatchRng.swift`).

Both are seeded together in `Train.run`. Two runs with the same
`--seed` now produce:

- Identical initial weights ✅
- Identical training-batch sequence ✅
- Step-1 loss bit-identical (assuming the same prefetcher behaviour;
  see below) ✅

## The remaining caveat — prefetching

The prefetcher runs `sampleBatchRaw` on a background thread to overlap
data prep with the previous step's GPU compute. When seeded, that
background thread still calls `BatchRng.randomInt(in:)`, which is
NSLock-guarded — so the *individual draws* are deterministic — but the
*interleaving* between prefetch lookahead and the main loop's
foreground draws is scheduler-dependent. In practice this means:

Same seed → batches drawn in the same per-thread order, but which
batches land in foreground vs prefetch can drift if the OS schedules
differently. **Observed: same-seed loss stays within ~1e-5; step-0 is
bit-identical** because the prefetcher hasn't issued any draws by that
point. A *different* seed diverges ~1e-1 — four orders of magnitude
larger, so the harness below cleanly separates "reproducible" from
"different run".

There is currently **no flag to disable the prefetcher**, so bit-exact
replay past step 0 is not available on the GPU path. For the common
case — sanity-checking a spike, A/B sweeps — the ~1e-5 reproducibility
is more than enough (the knob-under-test moves loss by far more).

## Verifying determinism

The C9 harness runs the same training twice at one seed and asserts
step-0 is bit-exact, the same-seed divergence stays within tolerance
(`DETERMINISM_TOL`, default 1e-2), and a different seed produces a
distinct trajectory:

```bash
bash evals/determinism-smoke.sh
# step-0 bit-exact: 6.103198
# same-seed max divergence: 2.67e-05 (<= 1e-02) — reproducible, not bit-exact past step 0
# cross-seed divergence:    1.85e-01 (distinct trajectory)
```

A real determinism regression (an unseeded sampler, a stray RNG draw)
would diverge by O(1) and trip the harness; ordinary GPU FP noise
(O(1e-5)) passes.

Unit tests pinning the contract live at
`Tests/TinyGPTModelTests/BatchRngTests.swift`:

- `testSameSeedSameSequence` — same seed → same draws
- `testDifferentSeedsDifferentSequence` — different seed → different
- `testResetClearsState` — `reset()` then re-seed → canonical sequence
- `testSplitmix64MatchesExpectedBitPattern` — pins the on-disk
  reproducibility contract; if this changes meaning, run-to-run
  replay across versions has been broken

## Where this matters

- **Spike investigations.** A reproducible init AND a reproducible
  batch sequence means you can re-run the same configuration to see
  whether a loss spike is intrinsic (recurs every run) or sampling-
  driven (occurs in one). See `--no-spike-detect` and
  `--spike-window` / `--spike-factor` flags on `tinygpt train`.
- **A/B sweeps.** When comparing `--lr-schedule cosine` vs `wsd` or
  two `--depth` values, fixing `--seed` removes both init AND batch-
  order variance — A/B differences are now attributable to the knob
  under test.
- **Crash recovery.** `--resume <path.tinygpt>` restores weights;
  resume + the same `--seed` gets you "continue the exact same run"
  modulo the prefetcher caveat above.

## V1 → V2 changelog (for the curious)

- **V1 (until 2026-06-17)**: only MLXRandom was seeded. `--seed` made
  model init reproducible; batch sampling drifted run-to-run.
- **V2 (2026-06-17, this doc)**: BatchRng + Splitmix64 added; both
  surfaces seeded together. Closes the gap noted in §"Roadmap to full
  bit-exact replay" of the previous version of this doc.

See `docs/PLAN.md` §3 C9 for status.
