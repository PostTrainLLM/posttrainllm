# Chess development evidence

This directory retains every bounded development screen, including superseded
artifacts. The primary ruler is exact agreement with a Stockfish-labelled move;
complete games are secondary demonstrations and are not an Elo estimate.

## Current evidence

- `fixtures/development-puzzles-v1.json`: 20 deterministic, engine-generated,
  development-only tactical-gap positions.
- `random-legal-development-v2.json`: 2,000-seed calibration. Mean exact-move
  accuracy is 6.7375%; a single representative cohort scored 15% by chance.
- `qwen3-4b-development-v2.json`: Qwen3 4B, 0% exact and 95% legal.
- `qwen3.5-9b-development-v1.json`: Qwen3.5 9B, 10% exact and 90% legal.
- `codex-gpt-5.5-development-v1.json`: Codex `gpt-5.5` development alias,
  65% exact and 100% legal. The mutable alias cannot anchor a frozen public
  benchmark.
- `gate-0-decision-v1.json`: Gate 0 passes for frozen-suite design, not for
  specialist training or a capability claim.
- `qwen4b-v-qwen9b-paired-games-v1.json`: four paired demonstration games.
  Two nominal 4B wins are 9B notation forfeits and two games are short
  repetition draws, so this artifact must not be used for model ranking.

## Expanded candidate verification (2026-08-05)

This is a **candidate-only audit**, not a frozen benchmark and not permission to
train a specialist. `fixtures/candidate-pool-v2.json` contains 100 new positions
with no overlap with the original 20. Stockfish 18 MultiPV analysis at depths 16
and 20 kept the same top move on all 100; 86 passed the predeclared 150 cp final
gap and PV-legality gates. `fixtures/candidate-verification-v1.json` is a
deterministic, legal-move-count-stratified 40-position review slice.

`candidate-model-matrix-v1.json` normalizes the bounded model screens. Accuracy
uses every assigned position in the denominator, including timeouts and budget
failures. Coverage differs by design, so a 10-position score is not directly
rankable against a 40-position score.

| Policy | Positions | Exact | Raw legal / available | Executed moves legal | Redirect | Recorded direct cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex GPT-5.5, medium | 40 | 70% | 100% | 100% | 0% | subscription, not exposed |
| Codex GPT-5.5, high ceiling audit | 40 | 60% | 97.5% | 100% | 2.5% | subscription, not exposed |
| Codex GPT-5.4, medium | 40 | 75% | 97.5% | 100% | 2.5% | subscription, not exposed |
| Codex GPT-5.4-mini, medium | 10 | 80% | 100% | 100% | 0% | subscription, not exposed |
| Claude Sonnet 5 | 20 | 65% | 90% | 100% | 10% | $0.494 plus unknown timeout cost |
| Claude Opus 4.8 | 10 | 70% | 70% | 100% | 30% | $1.361 plus unknown timeout cost |
| Devin GLM-5.2 | 20 | 70% | 100% | 100% | 0% | $0 |

GLM-5.2 used five auditable four-position batches because attempted batches of
40 and 10 exceeded Devin's output ceiling; those failed attempts remain in this
directory. The representative random-legal cohort scored 12.5%, but that was
the 95th percentile of the 2,000-seed calibration; calibrated mean accuracy was
6.6825% (analytic expectation 6.4816%).

The constrained lane does not hide availability failures. Every returned move
is checked against python-chess's canonical legal UCI set. A missing, invalid,
timed-out, or provider-failed response abstains or redirects and is never sent
to the executor. The 10-position strict raw-output diagnostic for both GPT-5.5
and GPT-5.4 was 80% exact and 100% raw legal, but only the membership check is a
hard legality guarantee.

Model agreement is secondary review, not label authority. Raising GPT-5.5 from
medium to high reasoning did not repair the ceiling: it changed 11 choices,
fixed one medium-reasoning miss, broke five previous hits, and timed out once,
reducing exact accuracy from 70% to 60%. Since no frontier lane approaches the
repo's ~100% ceiling gate, the candidate suite cannot yet grade a Mac model.
The admitted pool is ready for human review, not freezing; every frontier miss
must be audited and the ruler repaired or replaced before specialist training.

## Superseded attempts retained on purpose

- `random-legal-development-v1.json` contains only the lucky 3/20
  representative cohort. It is superseded by the 2,000-seed calibration in
  v2, not deleted.
- `qwen3-4b-development-v1.json` was produced before the runner preserved the
  raw invalid output on parse failures. Its scores are unchanged, but v2 is the
  evidence-bearing artifact.

No generalizing 30–50M specialist has been established. A later bounded
eight-position memorization gate passed, but it is not strength evidence. The
tactical suite still requires a broad, held-out, human-audited replacement
whose pinned frontier anchor scores near 100% before it can grade a model.

## Sub-50M full-game reproduction scaffold (2026-08-05)

The external Qwen Chess project's “30M” describes roughly 30 million training
positions on a Qwen3-8B base, not a 30M-parameter model. We therefore reuse its
public-data and full-game-evaluation ideas without treating its weights or
reported strength as reproduced.

The independent reference path now consists of:

- `scripts/chess/chess_sft_corpus.py`: deterministic compiler from decompressed CC0
  Lichess evaluation JSONL to character-policy rows and a provenance manifest;
- `configs/model.chess-44m-v0.json`: an owned 44,527,616-parameter byte model;
- `scripts/chess/chess_sft_text.py` and `scripts/chess/chess_python_checkpoint.py`: the
  explicit bridge from compiled rows to the Python trainer and from its
  checkpoint back into legal-candidate evaluation;
- `scripts/chess/chess_strength_ladder.py`: paired-color full games against pinned
  random, weak Stockfish-mixture, and UCI-strength rungs;
- `configs/chess/specialist-recipe-v1.json`: tiny-overfit, pilot, stop, and
  qualification gates, now closed after the bounded pilot failed promotion.

`strength-ladder-smoke-v1.json` is the bounded real-engine integration proof:
Stockfish 18 played four eight-ply paired games against a deterministic
first-legal policy. All four reached the smoke move cap, every candidate action
was legal, colors were balanced, and the result correctly stayed `unrated`.
It is not model evidence and makes no Elo claim.

`character-chess-44m-tiny-overfit-v1.json` records the first real 44.53M
checkpoint gate. It reached 8/8 exact targets and 100% legal execution at step
150, after non-monotonic intermediate exact rates of 87.5% and 75%. This proves
the data, trainer, checkpoint, and constrained scorer connect correctly; it
does not measure held-out chess ability.

`character-chess-44m-stockfish-rating-v1.json` records the first full internal
ladder diagnostic for that same memorization checkpoint. Five weak rungs
were calibrated over 60 paired games to Stockfish 18's UCI-1320 floor, then the
candidate played 30 balanced games. It scored 0 wins, 9 draws, and 21 losses
with 100% legal execution. Its headline result is **<536 Internal
Stockfish-ladder Elo**, because 536 is the weakest calibrated rung. The fitted
**475** estimate with a paired-opening bootstrap interval of **416–550** is a
diagnostic extrapolation only. Excluding three artificial 160-ply draws changes
the extrapolation to 457, so the conclusion is stable:
the eight-position checkpoint is approximately random-level and is not a chess
specialist. This number is not human, FIDE, Lichess, or Chess.com Elo.

`character-chess-44m-pilot-10k-v1.json` records the final bounded 10k attempt.
Completion-only SFT fixed the earlier objective mismatch: prompt bytes were
masked and only the canonical move plus newline contributed to loss. Across
588 validation rows the step-2000 checkpoint scored 10.54% exact versus 6.16%
analytic random (+4.38 points); across 600 test rows it scored 10.33% versus
6.23% (+4.10). Both splits were 100% legal, so this is genuine but small local
move-learning signal. It missed the frozen +10-point promotion gate.

The full-game stop screen was decisive: raw and guarded policies each finished
0 wins, 6 draws, and 0 losses against random legal play. The guard fired 22
times and changed eight moves but created no win. Its displayed 536 is only
equality with a single calibrated random-floor rung over six games, not a
qualified rating. The current Character Chess training lane is therefore
rejected before 100k. The checkpoint and detailed traces remain local and
gitignored; their hashes are committed in the evidence summary.

The Qwen-style reproduction contract adds separately rated raw always-score and
engine-free finishing-guard policies. `scripts/chess/chess_move_quality.py` grades
archived moves with Stockfish depth 12 for average cp loss plus 100/300 cp
blunder rates; Stockfish is evaluation-only. Frozen 10k/100k/1M/2M composition
stages live in `configs/chess/qwen-reproduction-v1.json`; the 10k stage ran
under explicit approval, and its failure rejects later stages under this
recipe.

The fixture compiler accepted two of six records and rejected the duplicate,
shallow, illegal-PV, and malformed records with separate counted reasons. Unit
tests rerun the compiler twice and require byte-identical rows and manifests.

Million-row compilation, the 100k/1M/2M stages, and 4B/9B/frontier match sweeps
were not run. They are rejected under the current recipe because the bounded
10k pilot missed its learning-signal gate and showed no win advantage over
random legal play. See `docs/learn/reproducing-qwen-chess-under-50m.md`.
