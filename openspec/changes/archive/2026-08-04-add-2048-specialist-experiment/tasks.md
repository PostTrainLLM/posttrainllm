## 1. Freeze the experiment contract

- [x] 1.1 Add versioned environment and lightweight development-eval configs with disjoint seed namespaces, budgets, baseline revisions, and proof thresholds.
- [x] 1.2 Add small tracked board/trajectory fixtures covering canonical transitions and runner output without containing future frozen evaluation seeds.

## 2. Implement the deterministic reference environment

- [x] 2.1 Implement the 4-by-4 board model, canonical four-direction move/merge scoring, legal-action detection, and terminal-state behavior in a dependency-free Python reference.
- [x] 2.2 Implement the pinned environment PRNG, deterministic reset/tile spawning, separate policy random stream, and no-RNG-advance invalid-move behavior.
- [x] 2.3 Implement canonical observation, transition, episode, trace-hash, and replay serialization with overwrite refusal.

## 3. Prove environment correctness

- [x] 3.1 Add golden merge, no-double-merge, directional-equivalence, spawn, legal-action, terminal-state, and invalid-action unit tests.
- [x] 3.2 Add fixed-seed reset/replay tests proving byte-identical observations, rewards, terminal reasons, and trace hashes.
- [x] 3.3 Add trajectory validation proving reward sums equal final score and train/eval seed or board overlap fails closed.
- [x] 3.4 Add a no-model smoke wrapper and run the targeted unit/smoke checks plus `git diff --check`.

## 4. Establish lightweight baselines

- [x] 4.1 Implement seeded `random-legal` and fixed-weight `greedy-one-ply` policies through the common policy boundary.
- [x] 4.2 Implement the paired-seed runner and deterministic aggregation for score, maximum tile, reach rate, legality, episode length, trace identity, and latency/throughput.
- [x] 4.3 Qualify only the tiny development fixture: both policies make zero invalid decisions, replay deterministically, and greedy beats random; do not run a sustained seed sweep.

## 5. Add the bounded-search diagnostic

- [x] 5.1 Obtain explicit owner approval before any sustained diagnostic calibration or benchmark sweep.
- [x] 5.2 Implement and unit-test versioned bounded expectimax without changing environment or scorer semantics.
- [x] 5.3 Freeze its diagnostic-only configuration on development seeds and record its quality/latency trade-off against random and greedy.

## 6. Freeze the larger-LLM opponent and prepare specialist data

- [x] 6.1 Freeze the 50,000,000-parameter candidate ceiling, strict-versus-constrained track semantics, prompt, character-board serializer, one-character action parser, decoding settings, context policy, per-move limit, and no-tools/no-search constraints.
- [x] 6.2 Implement versioned local and cloud opponent adapters with offline fake-command tests, tool-use rejection, mutable-alias disclosure, and cost/provenance capture.
- [x] 6.3 Run a bounded one-move development smoke for available Codex, Claude Sonnet, and Claude Opus backends; record resolved identities and refuse to call this frozen evidence. Freeze no training target unless a pinned frontier subsequently beats `random-legal` on the constrained paired suite with positive uncertainty.
- [x] 6.4 Resolve the 30-seed suite decision: do not freeze or run it because the development intelligence gradient failed.
- [x] 6.5 Confirm no larger-LLM trajectories are generated after the failed admission gate.
- [x] 6.6 Confirm no four-action specialist dataset is compiled from a rejected benchmark.

## 7. Train and evaluate the tiny policy

- [x] 7.1 Record that no candidate recipe is authorized because Gate 0 failed.
- [x] 7.2 Confirm no tiny-overfit or training gate is run for the rejected target.
- [x] 7.3 Confirm no candidate is trained or packaged and no GPU/model process remains.
- [x] 7.4 Confirm no specialist evaluation is represented without a frozen suite or trained candidate.
- [x] 7.5 Record the outcome as reject-benchmark-before-training, not retry-data or retry-training.

## 8. Build the reproducible benchmark gallery

- [x] 8.1 Compile path-scrubbed development-pilot results into a compact tracked replay artifact with exact seeds, traces, model identities, inputs, outputs, and limitations.
- [x] 8.2 Add a benchmark catalog and responsive Character 2048 detail page with model/seed selection, playback controls, raw decision inspection, and a pending custom-SLM lane.
- [x] 8.3 Publish the local reproduction contract and downloadable prerecorded outputs without representing development evidence as frozen proof.
- [x] 8.4 Relabel random/greedy as algorithmic sanity checks, explain their legal-action advantage, distinguish strict from constrained results, and state the 50M candidate ceiling prominently.
- [x] 8.5 Preserve the development replay as negative evidence and explicitly refuse to synthesize a frozen specialist result.

## 9. Close the experiment honestly

- [x] 9.1 Record the valid Sonnet screen and incomplete Opus screen with identities, costs, missing measurements, limitations, and no broader game-playing claim.
- [x] 9.2 Run strict OpenSpec validation and the smallest relevant repository checks.
- [x] 9.3 Update durable project status with the measured rejection and archive this completed experiment record.

Gate 0 outcome: **reject the current character-only benchmark.** Tasks 6.4–8.5
remain intentionally unexecuted: no frozen 30-seed suite, trajectories, data,
training, specialist evaluation, or replacement gallery evidence should be
created from a ruler that did not establish a robust frontier advantage over
random legal play.
