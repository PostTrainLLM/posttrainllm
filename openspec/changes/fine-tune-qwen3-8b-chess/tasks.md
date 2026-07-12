## 1. Freeze the target and recipe boundary

- [ ] 1.1 Select the exact Qwen3-8B base or instruct checkpoint, pin its immutable revision and chat template, and record why it is the smallest appropriate model for this requested run.
- [ ] 1.2 Record approved chess data sources, licenses, redistribution/training constraints, expected storage, and whether only manifests or derived rows may be committed.
- [ ] 1.3 Write the chess recipe card under `docs/techniques/` with target, current unknowns, SFT-first method, data stages, baseline, gates, slices, performance fields, stop rules, and prior evidence.
- [ ] 1.4 Freeze protocol v1, canonical-position hashing, seeds, prompt/history limits, generation settings, Stockfish options, engine-equivalence tolerance, blunder threshold, and numeric ship bars in a versioned eval manifest.

## 2. Build the no-GPU chess correctness layer

- [ ] 2.1 Propose the smallest maintained chess-library integration and Stockfish acquisition method, explain each development-only dependency, and obtain approval before installation.
- [ ] 2.2 Add tiny committed standard-chess fixtures covering ordinary moves, check, checkmate, stalemate, castling, en passant, promotion, malformed FEN, illegal moves, and prose/multi-move output.
- [ ] 2.3 Implement strict protocol formatting and parsing with fixture tests that accept exactly one legal UCI action and never repair a scored response.
- [ ] 2.4 Implement canonical-position hashing and tests proving that clocks are ignored while side-to-move, castling, and en-passant state remain significant.
- [ ] 2.5 Implement slice classification for phase, evaluation state, tactical/quiet positions, check, castling, promotion, en passant, and recovery states with deterministic fixture tests.
- [ ] 2.6 Run the smallest no-GPU chess test command and document it beside the fixtures.

## 3. Build provenance-safe data preparation

- [ ] 3.1 Implement source adapters that preserve source/game/trajectory identity and reject rows without approved provenance.
- [ ] 3.2 Split games or trajectories before extracting positions, deduplicate canonical positions across splits, validate every target move, and report every rejection reason.
- [ ] 3.3 Implement deterministic Stockfish labelling for approved positions with pinned engine settings, legal target validation, near-equivalent move metadata, and resumable outputs.
- [ ] 3.4 Generate only the tiny-overfit and small pilot manifests first; verify hashes, licenses, split isolation, slice counts, row counts, and reproducibility before any large build.
- [ ] 3.5 Add a manifest validator and a no-engine fixture smoke test that fails on missing provenance, cross-split position collisions, invalid targets, or underreported slices.

## 4. Build and calibrate chess evaluation

- [ ] 4.1 Implement strict parse/legality scoring, mate-aware capped centipawn loss, engine-equivalence credit, blunder rate, and required slice metrics.
- [ ] 4.2 Implement deterministic tactical evaluation that supports engine-validated equivalent solutions rather than single-string exact match.
- [ ] 4.3 Implement paired-match orchestration with reversed colors, fixed openings/opponent/resources, PGN capture, illegal-move losses, timeout/adjudication rules, confidence intervals, and process cleanup.
- [ ] 4.4 Add a tiny fake-engine or stubbed-engine smoke suite so parser, scorer, match bookkeeping, and failure handling run without a model or long engine loop.
- [ ] 4.5 With explicit approval, run a bounded Stockfish timing/calibration sample, freeze nodes or depth, and verify the engine clears legality and benchmark-ceiling gates.
- [ ] 4.6 Freeze the complete offline test and paired-opening manifests after calibration; hash them and prevent training or prompt demonstrations from reading them.

## 5. Establish the frozen Qwen3-8B baseline

- [ ] 5.1 Prepare the exact model download/load command, disk/RAM estimate, cache path, cleanup plan, and bounded one-prompt smoke; obtain explicit approval before downloading or loading the 8B model.
- [ ] 5.2 Run one bounded protocol smoke and fix only harness/template incompatibilities before freezing baseline generation behavior.
- [ ] 5.3 With explicit approval, evaluate the frozen base on the full offline suite and small baseline match suite, recording quality, breadth, latency, RSS, throughput, duration, and complete provenance.
- [ ] 5.4 Review baseline traces by failure slice and record either `park/reject` because the base already clears the bars or one concrete trainable gap that justifies adaptation.

## 6. Prove an honest 8B adapter-training path

- [ ] 6.1 Test the native packed 4-bit loader against the pinned model with a bounded logit/load parity check and record peak RSS.
- [ ] 6.2 With explicit approval, run exactly one packed-base adapter training step and verify finite non-zero adapter gradients, frozen base weights, finite/decreasing toy loss, adapter save/load, GPU-lock use, and process cleanup.
- [ ] 6.3 If the native gate fails, stop native expansion and pin a minimal `mlx_lm` fallback environment and equivalent adapter/export contract; do not use simulated quantization as 8B QLoRA evidence.
- [ ] 6.4 With explicit approval, run the 1–10 KB repeated-data overfit gate through the selected trainer and stop with `retry-training` if it cannot memorize the legal-move fixture.

## 7. Run the staged chess candidate

- [ ] 7.1 Freeze one pilot SFT configuration, including LoRA targets/rank/alpha, precision, optimizer, learning rate, context length, batch/accumulation, steps, checkpoints, seed, memory guardrail, and stop rule.
- [ ] 7.2 With explicit approval, train only the pilot dataset, monitor loss/RSS/stability, save the adapter and log, and verify that all spawned processes stop.
- [ ] 7.3 Evaluate the pilot on the complete frozen offline suite, general-language regression gate, performance gate, and smoke match; compare every metric and slice to the frozen base.
- [ ] 7.4 Record `reject`, `retry-data`, `retry-training`, or approval for one larger SFT run based on the frozen pilot rules; do not start an unplanned hyperparameter sweep.
- [ ] 7.5 If approved, freeze and run one larger SFT recipe, then evaluate it on the unchanged offline, breadth, performance, and full paired-match gates.
- [ ] 7.6 Propose any preference or verifiable-reward stage as a separate recipe only if the SFT report identifies a specific residual move-selection or recovery failure.

## 8. Assemble evidence and decide

- [ ] 8.1 Emit or assemble the canonical factory run folder with config, dataset, train log, baseline/candidate evals, slice metrics, trace review, provenance, artifact metadata, performance fields, report, and decision.
- [ ] 8.2 Run the smallest factory schema validation first, then the report-only publish check, and fix schema or provenance failures without changing frozen eval results.
- [ ] 8.3 Record exactly one allowed decision with evidence: `ship`, `reject`, `retry-data`, `retry-training`, `retry-eval`, or `park`.
- [ ] 8.4 Only for `ship`, create the specialist package with model card, lock, prompt/protocol, eval report, performance, routing constraints, known limits, and resolvable artifact path; run publish-check without report-only allowances.
- [ ] 8.5 Update `PROJECT_STATUS.md`, `docs/NEXT.md`, the attempt ledger, and public artifact inventory with the measured result; archive this OpenSpec change only after all accepted tasks and checks are complete.
