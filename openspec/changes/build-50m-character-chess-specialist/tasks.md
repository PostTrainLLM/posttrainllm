## 1. Freeze the reproduction contract

- [x] 1.1 Record which Qwen Chess ideas are adopted, independently rebuilt, or not reproducible.
- [x] 1.2 Freeze the 44M candidate architecture, data source, split rule, legal-selection semantics, opponent ladder, and qualification gates.
- [x] 1.3 Strictly validate this OpenSpec change before implementation.

## 2. Build the data reference path

- [x] 2.1 Implement a dependency-free streaming Lichess-eval compiler with fail-closed FEN, PV, legality, and threshold validation.
- [x] 2.2 Emit deterministic SFT rows and a provenance manifest with disjoint hash-based splits.
- [x] 2.3 Add tiny valid/malformed fixtures and focused compiler tests.

## 3. Build the full-game ladder reference path

- [x] 3.1 Implement pinned Stockfish, node-limited, UCI-Elo, and random-mixture policies.
- [x] 3.2 Implement paired-color candidate matches and completion, legality, forfeit, score, and confidence summaries.
- [x] 3.3 Keep internal rating qualification separate from diagnostic estimation.
- [x] 3.4 Add deterministic scripted/engine smoke evidence without loading a model.

## 4. Freeze the candidate recipe

- [x] 4.1 Add the 30–50M-compliant byte-model config and verify its parameter estimate.
- [x] 4.2 Define the tiny-overfit, pilot, stop, regression, and full qualification gates.
- [x] 4.3 Document the later operator commands without downloading data or starting training.

## 5. Run the owner-approved experiment

- [ ] 5.1 Compile the pinned large corpus and record its checksum, counts, time, and disk cost.
- [x] 5.2 Pass the repeated tiny-data overfit gate before any scale-up.
- [x] 5.3 Train the bounded 10k candidate and retain checkpoints, traces, time, RAM, and supervised-byte counts.
- [ ] 5.4 Compare the candidate with 4B, 9B, and frontier policies on the same frozen full-game ladder.
- [x] 5.5 Publish a reject decision with no human-Elo claim; do not run 100k under this recipe.

## 6. Verify the no-model implementation

- [x] 6.1 Run focused tests, chess smoke checks, JSON validation, and strict OpenSpec validation.
- [x] 6.2 Update the chess evidence README and `PROJECT_STATUS.md` with the reproduction boundary and remaining heavy gates.

## 7. Reproduce the current Qwen serving and evaluation recipe

- [x] 7.1 Correct below-ladder rating semantics so the current checkpoint reports `<536`, retaining 475 only as diagnostic extrapolation.
- [x] 7.2 Implement and unit-test engine-free mate delivery, mate avoidance, and won-position draw avoidance over model-scored legal candidates.
- [x] 7.3 Give raw and guarded policies distinct revisions and record guard intervention reasons and rates in full-game traces.
- [x] 7.4 Add a pinned offline Stockfish move-quality grader for average cp loss, 100 cp blunders, and 300 cp severe blunders.
- [x] 7.5 Freeze 10k, 100k, 1M, and 2M data-composition stages with provenance and matched terse/commentary arms.
- [x] 7.6 Run focused no-model tests, smoke checks, strict OpenSpec validation, and update durable docs.

## 8. Run the separately approved reproduction campaign

- [x] 8.1 Compile the bounded 10k general-position terse stage and verify manifests, split isolation, and source license; record the deliberate endgame/commentary composition deviation.
- [x] 8.2 Train the 10k terse arm with answer-only loss, evaluate held-out move quality, and reject the 100k stage after missing the frozen gain gate and winning 0/12 raw-plus-guarded random-floor games.
- [ ] 8.3 Not pursued: the 10k gate rejected matched 100k terse/commentary arms before any 1M scale-up.
- [ ] 8.4 Rate the promoted raw and guarded policies separately over at least 200 games and report guard fire rates.
- [ ] 8.5 Compare the promoted 44M policy with 4B, 9B, and frontier policies on the identical ladder and publish the final decision.
