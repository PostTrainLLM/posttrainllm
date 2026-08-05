# Proposal: Extensible game arena

## Why

The existing Character Chess and Character 2048 experiments are inspectable,
but each owns a bespoke scorer and page. Chess needs a defensible head-to-head
rating with uncertainty; 2048 needs paired score evidence. Calling both “Elo”
would be misleading, while leaving them isolated makes every next game repeat
the same infrastructure.

## What changes

- Add a versioned, game-independent arena contract with a small adapter registry.
- Support two honest competition families:
  - head-to-head win/draw/loss evidence with regularized internal Arena Elo;
  - single-player score evidence with paired deltas and bootstrap uncertainty.
- Import the existing chess and 2048 artifacts into one candidate arena report.
- Mark ratings provisional until frozen participation and sample-size gates pass.
- Add a public arena dashboard that exposes ratings, confidence, qualification,
  forfeits, source artifacts, and the distinction between Elo and score tracks.

## In scope

- Standard-library Python schema validation, deterministic scoring, adapters,
  tests, smoke checks, and a generated JSON report.
- Chess as the first head-to-head adapter and 2048 as the first score adapter.
- Existing recorded evidence only for the first trial.
- An extension contract for future deterministic, character-only games.

## Out of scope

- Human/FIDE Elo equivalence, matchmaking, live multiplayer, accounts, or a
  hosted inference service.
- New cloud calls, model loading, training, engine assistance, or a specialist
  claim.
- Combining incomparable games into one universal intelligence number.
- Treating tactical-puzzle accuracy as chess Elo.

## Impact

- New files under `configs/game-arena/`, `scripts/`, `evals/game-arena/`,
  `tests/`, and `browser/src/pages/benchmarks/`.
- The benchmark catalog gains an Arena entry.
- No production dependency, deployment, migration, model call, or training run.
