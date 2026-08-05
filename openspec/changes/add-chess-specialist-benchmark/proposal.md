## Why

Character 2048 failed to show that stronger language models play better than a
valid random executor. Chess offers a denser and more legible test: independent
tactical positions provide exact high-volume measurements, while complete
games make the policy behavior demonstrable. The experiment must still prove
that a frontier model has a real advantage before any 30–50M specialist is
trained.

## What Changes

- Add a pinned chess-rules dependency for evaluation correctness rather than
  implementing move legality, check, castling, promotion, and repetition anew.
- Add a deterministic character-only policy contract using FEN, side to move,
  and a canonical list of legal UCI moves.
- Add a development tactical suite with exact best-move and move-quality
  scoring, plus random-legal, local 4B/8–9B, and pinned frontier screens.
- Add complete paired games from fixed opening positions with colors swapped,
  identical time/output limits, and no engine or tool access for either model.
- Add path-scrubbed evidence artifacts and a browser experience with Puzzle
  Arena and Match Arena modes, following the Character 2048 replay language.
- Retain a failed or incomplete chess screen as a negative artifact if the
  capability gradient does not reproduce.
- Keep synthetic-data generation, specialist training, packaging, and public
  win claims blocked until the benchmark-admission gate passes.

## Capabilities

### New Capabilities

- `deterministic-chess-evaluation`: Versioned chess positions, legal moves,
  transitions, terminal outcomes, tactical labels, and replay traces.
- `chess-language-policy-benchmark`: Common random/local/frontier/specialist
  interface, admission gates, full-game matches, and public evidence artifact.

### Modified Capabilities

- `2048-policy-evaluation`: The benchmark catalog becomes an archive of both
  accepted and failed game-policy experiments rather than a single-game page.

## Impact

- Adds small Python evaluator scripts, fixtures, configs, tests, and smoke
  commands under existing repository surfaces.
- Adds `python-chess` as an evaluation-only pinned dependency; it is not a
  browser or production-runtime dependency.
- Adds one generated replay artifact and one Astro benchmark route. No deploy,
  model training, package publication, or production integration is included.
