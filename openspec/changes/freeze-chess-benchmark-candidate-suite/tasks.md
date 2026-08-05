## 1. Freeze the expansion contract

- [x] 1.1 Add versioned candidate-generation, deep-label, verification-slice, model-matrix, and legal-selection configs.
- [x] 1.2 Validate engine/model identities, budgets, seeds, thresholds, and non-overlap before outputs are inspected.
- [x] 1.3 Retain the original 20-position suite and every failed or superseded attempt unchanged.

## 2. Verify chess labels

- [x] 2.1 Implement Stockfish MultiPV label verification at depth 16 and depth 20.
- [x] 2.2 Record top-move stability, score gaps, alternatives, PV legality, and trace hashes.
- [x] 2.3 Reject duplicate, unstable, illegal-PV, and insufficient-gap candidates.
- [x] 2.4 Add focused tests for stable, changed, mate, ambiguous, and malformed engine evidence.

## 3. Guarantee legal execution

- [x] 3.1 Implement the canonical legal-action enum/mask boundary.
- [x] 3.2 Record raw legality, constraint application, executed legality, abstention, and redirection separately; provider token-level intervention is not observable.
- [x] 3.3 Prove that illegal, prose, empty, timeout, and provider-error outputs never reach the executor.
- [x] 3.4 Preserve the strict raw-output lane as a diagnostic.

## 4. Add independent model adapters

- [x] 4.1 Add a safe/no-tools/no-session Claude CLI adapter with resolved-identity and usage capture.
- [x] 4.2 Extend Codex evaluation to per-position legal-enum structured output and explicit alias-failure evidence.
- [x] 4.3 Freeze the available lower-GPT, Claude, and free Devin GLM-5.2 verification matrix before scoring.
- [x] 4.4 Add parser, identity, schema, timeout, and provider-failure validation.

## 5. Build and screen the candidate pool

- [x] 5.1 Generate and validate 100 deterministic non-overlapping candidate positions.
- [x] 5.2 Run deep Stockfish verification and compile the admitted candidate set.
- [x] 5.3 Select the deterministic 40-position multi-model verification slice.
- [x] 5.4 Run bounded Claude, GLM-5.2, and available lower-GPT screens; retain unavailable/incomplete attempts.

## 6. Report and decide

- [x] 6.1 Publish per-model exact, raw/executed legality, constraint, latency, usage/cost, and failure metrics.
- [x] 6.2 Publish label-stability and cross-model agreement/disagreement examples without treating consensus as truth.
- [x] 6.3 Update the chess replay surface and `PROJECT_STATUS.md` with limitations and next action.
- [x] 6.4 Run focused tests, smoke checks, artifact validation, and strict OpenSpec validation.
- [x] 6.5 Decide: admitted pool is ready for human miss audit, not freezing; the frontier-ceiling gate failed.
