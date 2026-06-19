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

- Same seed + prefetcher disabled → bit-exact replay.
- Same seed + prefetcher on → batches drawn in the same per-thread
  order, but which batches land in foreground vs prefetch can drift
  if the OS schedules differently. Loss values stay within ~1e-5 in
  observed runs; step-1 loss is still bit-identical because the
  prefetcher hasn't issued any draws by that point.

If you need the strongest replay guarantee, run with the prefetcher
off (a hidden flag exists; see Train.swift `--no-prefetch`). For the
common case — sanity-checking a spike, A/B sweeps — the default
prefetched path is fine.

## Verifying determinism

```bash
tinygpt train --preset tiny --steps 3 --seed 42 --no-spike-detect \
  --corpus data/examples/tiny-corpus.txt --out /tmp/det-A.tinygpt

tinygpt train --preset tiny --steps 3 --seed 42 --no-spike-detect \
  --corpus data/examples/tiny-corpus.txt --out /tmp/det-B.tinygpt
```

Step-1 losses should agree exactly. Step-2 onward depend on whether
the prefetcher is on (see above).

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
