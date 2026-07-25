## 1. Keep the target parked and freeze the contract

- [x] 1.1 Start this change only after the active factory target is complete or the owner explicitly reprioritizes it; record the decision in `docs/NEXT.md` before implementation.
- [x] 1.2 Write the versioned noisy-text-to-corrected-text protocol, protected-span rules, supported language/domain, maximum input length, and non-goals as committed fixtures.
- [x] 1.3 Define the error taxonomy and qualitative failure taxonomy, including missed edit, wrong edit, overcorrection, meaning change, formatting damage, and protected-span damage.
- [x] 1.4 Freeze numeric quality, regression, model-size, RSS, TTFT, end-to-end latency, energy, and stop thresholds before any training.

## 2. Build the honest evaluation first

- [x] 2.1 Identify a permissively licensed or consented natural typo/correction source; record its exact revision, terms, retrieval method, and exclusions before downloading or committing data.
- [x] 2.2 Create a tiny reviewed fixture set with natural errors, clean controls, rare words, names, numbers, URLs, Unicode, whitespace, casing, punctuation, and code-like spans.
- [x] 2.3 Implement the strict evaluator for error reduction rate, exact match, residual character error, clean preservation, unnecessary edits, protected-span preservation, and slice metrics, with unit tests for zero-error and negative-error-reduction cases.
- [x] 2.4 Implement source-first split, normalized overlap detection, lexical holdout, manifest hashing, and a no-model validation smoke that fails on leakage or incomplete provenance.
- [x] 2.5 Calibrate the frozen unambiguous test rows with the preferred free Codex CLI frontier backend available at execution time; fix or drop broken rows before candidate outputs are inspected.
- [x] 2.6 Determine whether Apple autocorrect can be invoked on the same full-span protocol; otherwise document it as a non-equivalent observational baseline rather than fabricating a direct comparison.

## 3. Build the corruption data path

- [x] 3.1 Implement a versioned Mac keyboard layout and deterministic corruption simulator for substitution, insertion, omission, transposition, repetition, spaces, and shift/case errors.
- [x] 3.2 Emit a machine-readable edit trace for every corrupted row and add fixtures covering each error family, seeded reproduction, disabled families, and clean controls.
- [x] 3.3 Build only tiny-overfit and pilot manifests first; validate licenses, source-first split isolation, hashes, row counts, drop reasons, error-family rates, and reproducibility.
- [x] 3.4 Compare simulator error distributions with the natural held-out set and tune only training-side simulator configuration without changing the frozen natural test.

## 4. Select and prove the smallest base

- [x] 4.1 Research a bounded shortlist of current Mac-runnable encoder-decoder or byte/character-aware bases and pin identifiers, revisions, licenses, parameter counts, artifact sizes, tokenizer behavior, and MLX/adaptation paths.
- [ ] 4.2 Prepare exact download/load commands plus disk, RAM, time, and cleanup estimates; obtain explicit approval before downloading weights, installing packages, compiling, or loading a substantial model.
- [ ] 4.3 Run bounded zero-shot and greedy-decoding smokes for approved candidates, measuring correction score, noisy-text fragmentation, load success, peak RSS, TTFT, latency, and throughput on the same fixtures.
- [ ] 4.4 Select the smallest plausibly capable base and freeze its prompt/template, precision, generation configuration, host, and baseline command; record `park` if none fits the envelope.
- [ ] 4.5 Evaluate the selected frozen base on the complete held-out suite before training and name the exact trainable failure slices.

## 5. Train one staged candidate

- [ ] 5.1 Verify or implement the minimum encoder-decoder adapter/training path needed by the selected base, with load parity, frozen-base, finite-gradient, save/load, and no-GPU or one-step tests before broader work.
- [ ] 5.2 Freeze an ordinary supervised adapter recipe with data, geometry, optimizer, precision, seed, step budget, checkpoint cadence, eval gate, and stop rule.
- [ ] 5.3 With explicit approval and the GPU lock, run the 1-10 KB repeated-data overfit gate; stop with `retry-training` if it cannot memorize the fixture.
- [ ] 5.4 With explicit approval, train one bounded ordinary-loss pilot, capture loss/RSS/time/artifact metadata, and verify that every spawned process stops.
- [ ] 5.5 Evaluate the ordinary-loss pilot on the unchanged complete suite and record whether copy bias or missed-edit slices justify an edit-aware objective.
- [ ] 5.6 If justified, specify and implement byte alignment plus token-weight mapping with numerical and gradient tests for insertions, deletions, substitutions, transpositions, Unicode, padding, and end-of-sequence behavior.
- [ ] 5.7 Freeze and run at most one edit-aware pilot with the ordinary-loss recipe as its ablation; reject it if target slices do not improve or overcorrection rises beyond the frozen bar.

## 6. Gate decoding and streaming

- [ ] 6.1 Record greedy decoding quality, latency, RSS, throughput, and energy as the decoding baseline.
- [ ] 6.2 If trace review identifies recoverable search errors, implement bounded batched beam search with frozen width, length penalty, output limit, stopping, and cumulative log-probability scoring.
- [ ] 6.3 Implement longest-common-prefix streaming after beam pruning, emitting only complete UTF-8 graphemes, with tests proving no retraction and final-output prefix consistency.
- [ ] 6.4 Compare greedy and beam modes on the complete frozen suite and accept beam search only if it clears both the quality delta and every performance gate.

## 7. Assemble evidence and decide

- [ ] 7.1 Run the approved final candidate and all comparators once on the frozen suite; compute bootstrap confidence intervals and keep natural, synthetic, clean, protected-span, and length/error-type slices separate.
- [ ] 7.2 Review blinded failures for meaning changes, overcorrection, simulator artifacts, benchmark ambiguity, memorization/overlap, and comparator protocol mismatch.
- [ ] 7.3 Emit or assemble the canonical factory run folder with config, dataset, training log, baseline/candidate evals, slice metrics, trace review, provenance, performance, artifact metadata, report, and one allowed decision.
- [ ] 7.4 Run the smallest schema validation first, then the report-only publish check; record `ship`, `reject`, `retry-data`, `retry-training`, `retry-eval`, or `park` without moving the frozen bars.
- [ ] 7.5 Only for `ship`, create the specialist package with model card, lock, correction contract, tokenizer/template, decoding mode, eval report, Mac resource measurements, routing limits, known failures, and resolvable local artifact path.
- [ ] 7.6 Update `PROJECT_STATUS.md`, `docs/NEXT.md`, the attempt ledger, and public artifact inventory with measured evidence; archive this OpenSpec change only after all accepted tasks and checks are complete.

## Pending blockers (recorded 2026-07-25)

- **2.5 complete:** Codex CLI 0.145.0 with `gpt-5.6-sol` scored all 18 rows perfectly on 2026-07-25; no rows needed repair or removal, and no candidate output had been inspected.
- **4.2-4.5:** the three-candidate Apache-2.0 shortlist, revisions, exact commands, and conservative resource/cleanup estimates are frozen in `docs/factory/autocorrect-model-shortlist.md`. Immediate approval is still required before downloads, dependency installation, compilation, model loading, or GPU work.
- **5.1-5.7:** require a selected base and immediate operator approval for any dependency installation, compilation, model load, GPU-lock acquisition, overfit run, or pilot training.
- **6.1-6.4:** require real model decoding plus sustained latency, RSS, throughput, and energy measurement; no decoding claim can be verified without those runs.
- **7.1-7.6:** require trained candidate/comparator outputs, measured Mac performance, and a canonical decision. Packaging, public-artifact updates, and OpenSpec archive remain invalid until then.
