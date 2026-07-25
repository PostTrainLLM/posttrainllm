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
- [x] 4.2 Prepare exact download/load commands plus disk, RAM, time, and cleanup estimates; obtain explicit approval before downloading weights, installing packages, compiling, or loading a substantial model.
- [x] 4.3 Run bounded zero-shot and greedy-decoding smokes for approved candidates, measuring correction score, noisy-text fragmentation, load success, peak RSS, TTFT, latency, and throughput on the same fixtures.
- [x] 4.4 Select the smallest plausibly capable base and freeze its prompt/template, precision, generation configuration, host, and baseline command; record `park` if none fits the envelope.
- [x] 4.5 Evaluate the selected frozen base on the complete held-out suite before training and name the exact trainable failure slices.

## 5. Train one staged candidate

- [x] 5.1 Verify or implement the minimum encoder-decoder adapter/training path needed by the selected base, with load parity, frozen-base, finite-gradient, save/load, and no-GPU or one-step tests before broader work.
- [x] 5.2 Freeze an ordinary supervised adapter recipe with data, geometry, optimizer, precision, seed, step budget, checkpoint cadence, eval gate, and stop rule.
- [x] 5.3 With explicit approval and the GPU lock, run the 1-10 KB repeated-data overfit gate; stop with `retry-training` if it cannot memorize the fixture.
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
- **4.2-4.5 complete:** the approved three-candidate bake-off selected FLAN-T5-small as the smallest plausibly trainable base. Complete predictions, tokenizer fragmentation, strict quality slices, RSS, TTFT, latency, throughput, runtime pins, and selection rationale are in `evals/autocorrect/base-bakeoff-v1.json`; no model was trained.
- **5.1-5.2 complete (2026-07-25):** the ordinary supervised recipe is frozen in `evals/autocorrect/adapter-recipe-v1.json` and the encoder-decoder LoRA path is implemented in `scripts/autocorrect_adapter.py`, documented in `docs/factory/autocorrect-adapter-recipe.md`. Measured on the real pinned FLAN-T5-small, forward-only on CPU with zero optimizer steps: 48 adapted modules, 344,064 trainable parameters (0.4471%), logits bit-identical after injection (max absolute delta 0.0), no base tensor modified. 19 offline tests pass via `bash evals/autocorrect-adapter-smoke.sh`; the 10 torch-backed tests use a tiny randomly-initialized T5 and skip cleanly where torch is absent, so CI reports 9/19 passed with 10 skipped rather than a false green. LoRA is hand-rolled: torch, transformers, and peft remain outside the project dependency surface. No adapter was trained and `train` refuses without an explicit operator-approval flag.
- **5.3 complete (2026-07-25), gate passed:** owner-approved, GPU lock held and released. Exact match reached 1.0 at step 50 of a 200 step budget; loss 1.585 -> 0.030 with no non-finite step; 0.28 min wall time, 1,135 MiB peak RSS on MPS, 344,064 trainable parameters. Evidence: `evals/autocorrect/tiny-overfit-result-v1.json` (adapters stay in gitignored `runs/autocorrect-tiny-overfit-v1/`). **The gate is weaker than its headline number:** the manifest derives all 8 rows from one source document, so every target is the identical string and exact match 1.0 is reachable by memorizing one sentence. It proves the training path runs end to end and has capacity to fit the fixture; it is not evidence of correction ability. A forward-only diagnostic probe on unseen inputs confirms the adapter did not collapse to a constant emitter but shows copy bias (an unseen typo copied through uncorrected), memorization leakage (a spurious `Please` prefix from the single training sentence), and one instruction echo. No stop rule fired and no decision was recorded, because the gate is a precondition rather than a candidate outcome.
- **5.4-5.7:** require immediate operator approval and the GPU lock for pilot training. 5.6-5.7 additionally require a measured 5.5 justification before any edit-aware objective is specified.
- **6.1-6.4:** require real model decoding plus sustained latency, RSS, throughput, and energy measurement; no decoding claim can be verified without those runs.
- **7.1-7.6:** require trained candidate/comparator outputs, measured Mac performance, and a canonical decision. Packaging, public-artifact updates, and OpenSpec archive remain invalid until then.
