## 1. Freeze the development contract

- [x] 1.1 Pin the evaluation-only rules dependency and record runtime identity.
- [x] 1.2 Add versioned environment, model-opponent, puzzle, match, and gate configs.
- [x] 1.3 Validate fixture provenance, split identity, legal moves, and thresholds.

## 2. Implement the correctness boundary

- [x] 2.1 Add FEN normalization, canonical legal-UCI ordering, parsing, transitions, and terminal outcomes.
- [x] 2.2 Add deterministic random-legal puzzle and game policies.
- [x] 2.3 Add canonical per-decision and complete-game trace hashing.
- [x] 2.4 Cover castling, en passant, promotion, checkmate, draw, and malformed-output paths.

## 3. Implement language-model adapters

- [x] 3.1 Add shared strict prompt/output contract and optional constrained diagnostic.
- [x] 3.2 Add bounded MLX local-model puzzle and match runners.
- [x] 3.3 Add a bounded Codex CLI runner that fails closed on tools, identity drift, timeout, or provider errors.

## 4. Run Gate 0

- [x] 4.1 Record the random-legal baseline on the unchanged development puzzles.
- [x] 4.2 Run the installed 4B and 8–9B general models with pinned decoding.
- [x] 4.3 Run one pinned frontier comparator within the bounded approved screen.
- [x] 4.4 Compute the frozen admission decision and retain all failures or incomplete attempts.

## 5. Add complete-game demonstrations

- [x] 5.1 Run paired opening games with colors swapped for admitted model entries.
- [x] 5.2 Record PGN-equivalent move traces, outcomes, illegal forfeits, latency, and cost.
- [x] 5.3 Keep match claims secondary to the tactical admission ruler.

## 6. Publish the replay surface

- [x] 6.1 Compile path-scrubbed puzzle and match evidence into a portable site artifact.
- [x] 6.2 Add Chess to the benchmark archive with honest development/failure status.
- [x] 6.3 Build Puzzle Arena and Match Arena replay modes with exact input/output inspection.
- [x] 6.4 Verify keyboard behavior and 390, 768, and 1440 pixel layouts.

## 7. Verify and decide

- [x] 7.1 Run focused environment/adapter tests and no-model smoke checks.
- [x] 7.2 Run frontend typecheck/build, OpenSpec validation, and artifact validation.
- [x] 7.3 Record cost, latency, limitations, result, and next action in `PROJECT_STATUS.md`.
- [ ] 7.4 If Gate 0 passes, propose the frozen-suite design separately; propose the 30–50M training recipe only after that suite passes the frontier-ceiling gate. Otherwise retain and archive the failed benchmark artifact.
