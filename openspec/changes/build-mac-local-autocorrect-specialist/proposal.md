## Why

Autocorrect should let the owner type quickly, then repair mistakes locally without interrupting composition or sending text to a cloud model. This is a strong future specialist-factory target because the task is narrow, data can be simulated and verified, and quality, latency, RAM, and battery tradeoffs are directly measurable on a Mac.

## What Changes

- Define one local text-repair contract: noisy text in, corrected text out, with intended wording and formatting preserved.
- Freeze an honest evaluation before training, including natural held-out typos, synthetic keyboard noise, clean-text regressions, unseen-word slices, Apple autocorrect, and a frontier calibration model.
- Build provenance-safe paired data from licensed clean text plus a configurable Mac-keyboard corruption simulator; split clean source text before corruption or augmentation.
- Compare the smallest viable encoder-decoder candidates and tokenization strategies with a no-training baseline before selecting one base.
- Train the cheapest useful candidate first, beginning with ordinary sequence loss and adding edit-aware weighting only when frozen copy-bias slices justify it.
- Add bounded beam decoding and optional stable-prefix streaming only after greedy decoding establishes the quality and latency baseline.
- Emit the canonical factory run, then package a specialist only after it clears frozen quality, regression, latency, RAM, and local-only gates.
- Apply the no-model foundation tranche after the owner's 2026-07-25 OpenSpec-completion reprioritization. This does not authorize downloads, installs, frontier/model calls, model loading, compilation, training, or long benchmarks; those tasks remain separately gated.

## Capabilities

### New Capabilities

- `mac-local-autocorrect-specialist`: Defines the task contract, data generation, staged training recipe, evaluation, decoding, performance gates, and conditional packaging for a small Mac-local autocorrect model.

### Modified Capabilities

None. The repository has no existing OpenSpec capability specifications, and this future target composes the existing factory contracts without changing them.

## Impact

- Expected future surfaces: `scripts/` for corruption/data preparation and scoring, `evals/autocorrect/` for small fixtures and frozen manifests, `docs/techniques/` for the accepted recipe, `runs/` for ignored evidence, and `specialists/` only after a ship decision.
- Training and inference should reuse MLX and existing factory commands where they fit. Model-specific encoder-decoder support or custom loss hooks are added only after a bounded feasibility check.
- Any tokenizer, model, dataset, or decoding implementation named in the motivating account is a candidate to reproduce, not trusted evidence. Exact revisions, licenses, metrics, and implementation details must be independently frozen and measured.
- The work is local-only and adds no browser surface, Pace runtime dependency, cloud service, deployment, or production integration.
- The committed no-model foundation is under `evals/autocorrect/` and
  `docs/factory/autocorrect-foundation.md`. Model/frontier calls, downloads,
  package installation, compilation, model loading, training, and sustained
  evaluation remain pending explicit approval under the repository safety
  rules.
