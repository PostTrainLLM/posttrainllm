# Proposal: Build a 50M-parameter Character Chess specialist

## Why

The Qwen Chess project demonstrates a credible full-game recipe: stream public
Stockfish-labelled positions, train a chess policy, guarantee legal execution,
and rate it against a calibrated weak-engine ladder. Its headline “30M” refers
to training rows, however; the actual base is Qwen3-8B with rank-128 LoRA. That
does not satisfy this repository's 30–50M-parameter specialist objective.

The existing posttrainllm chess work proves a language-model capability
gradient on tactical selection, but its exact-best-move ruler fails the
frontier-ceiling gate. We need a second, full-game strength track that can
measure useful chess rather than agreement with one engine move.

## What changes

- Record a reproducibility boundary for the external Qwen Chess recipe.
- Add a deterministic streaming compiler for the CC0 Lichess evaluations
  database, producing character-policy SFT rows with provenance and frozen
  train/validation/test partitioning.
- Add a versioned 44M-parameter byte-model candidate configuration inside the
  owner's 30–50M ceiling.
- Add a deterministic weak-Stockfish opponent ladder, paired-color full games,
  legality/completion metrics, and candidate-only rating evidence.
- Reproduce the external project's current serving policy as two separately
  reported tracks: always-score legal argmax, then the same model scores with
  one-ply mate/draw finishing guards and intervention accounting.
- Add Stockfish move-quality diagnostics (average centipawn loss, 100 cp
  blunders, and 300 cp severe blunders) and a staged data-composition contract.
- Keep tactical exact-move evaluation as a diagnostic while making full-game
  strength the candidate specialist's primary target.

## In scope

- Python reference implementation, tiny fixtures, configs, tests, no-model
  smoke checks, and documentation.
- Stockfish 18 as teacher/referee/opponent, with each role disclosed.
- Strict raw-output and legal-candidate-selection tracks kept separate.
- Raw model strength and guarded serving strength kept separate; any policy
  change invalidates the prior rating label until rerated.
- An operator-gated path for later data download, training, and model matches.

## Out of scope for the initial implementation

- Downloading the multi-gigabyte Lichess database.
- Generating millions of rows, training the 44M model, or running sustained
  Stockfish/model match sweeps without separate owner approval.
- Claiming reproduction of Qwen Chess's weights, Elo, or training economics.
- Treating internal ladder ratings as FIDE, Lichess, Chess.com, or human Elo.

## Impact

- New files under `configs/chess/`, `scripts/`, `evals/chess/`, `tests/`, and
  `docs/learn/`.
- Focused extensions to the existing chess smoke suite.
- No production dependency, deployment, model call, training run, or large
  dataset download in the first implementation.
