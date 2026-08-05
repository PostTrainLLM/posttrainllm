# Character game arena

This directory contains the first candidate cross-game arena report. It is an
evidence aggregator, not a universal leaderboard.

## Reproduce

```bash
bash evals/game-arena-smoke.sh
```

The smoke test runs the focused standard-library tests, rebuilds the report in
deterministic check mode, and strictly validates the OpenSpec change. It makes
no model, network, training, or GPU call.

## Interpret

- Character Chess is a head-to-head competition family, so the report may emit
  pool-specific **Arena Elo**. The current four-game estimates are diagnostics;
  both policies remain `unrated` because the sample and forfeit gates fail.
- Character 2048 is an independent paired-score family, so it emits paired
  score deltas and uncertainty, never Elo.
- Arena Elo is not FIDE, human, engine, Chess.com, or Lichess Elo.
- Qualification is frozen in `configs/game-arena/candidate-v1.json` and remains
  separate from the numerical estimate.

The browser copy is generated at
`browser/src/data/benchmarks/game-arena-candidate-v1.json`; it must remain
byte-identical to `candidate-v1.json`.
