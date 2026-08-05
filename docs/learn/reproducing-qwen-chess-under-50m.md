---
title: Reproducing Qwen Chess under a 50M-parameter ceiling
description: What the external Qwen Chess project actually proves, what posttrainllm can reproduce, and where the 8B-to-44M compression experiment begins.
---

# Reproducing Qwen Chess under a 50M-parameter ceiling

## The important correction

The external [Qwen Chess walkthrough](https://qwen-chess.replit.app/learn/)
uses “30M” as a corpus scale: roughly 30 million labelled chess positions. It
is not a 30M-parameter chess model. Its documented base is `Qwen/Qwen3-8B`,
trained with LoRA adapters including rank 128.

That makes the external result useful but different from our target:

| Question | External project | posttrainllm target |
|---|---|---|
| Base | Qwen3-8B | owned byte model |
| Trainable shape | LoRA on an 8B prior | full 44,527,616-parameter policy |
| Data scale | up to tens of millions of positions | staged: 8-row overfit, 10k pilot, then approved scale |
| Primary proof | full games and a weak-Stockfish ladder | same family, independently implemented |
| Legal execution | parsing/fallback and policy variants | legal-candidate scoring plus final membership check |
| Success claim | stronger chess-playing adapter | 44M specialist beats measured 4B/9B general models |

## What we adopt

1. **Explore weakly, label strongly.** Public positions provide diversity;
   the first move of the deepest available Stockfish PV provides the SFT label.
2. **Separate teacher and referee roles.** Training labels and evaluation scores
   come from disclosed Stockfish paths, not hidden model assistance.
3. **Measure full games.** Exact-best-move accuracy remains diagnostic; game
   completion, match score, legality, blunders, and a calibrated opponent ladder
   decide whether the policy is useful.
4. **Extend below Stockfish's ordinary floor carefully.** Weak rungs mix seeded
   random legal moves with node-limited Skill-0 Stockfish. Their ratings must be
   measured against our own pinned anchor, not copied from another project.
5. **Treat data composition as a first-class lever.** General positions and
   endgames need separate slices; later experiments may test a small reasoning
   blend only after terse policy learning works.

## What is independently rebuilt

- `scripts/chess_sft_corpus.py` compiles decompressed Lichess evaluation JSONL
  into deterministic, provenance-bearing character rows.
- `scripts/chess_sft_text.py` renders a bounded split into the plain byte stream
  consumed by the Python reference trainer without leaking held-out rows.
- `configs/model.chess-44m-v0.json` defines the owned 44.53M candidate.
- `scripts/chess_python_checkpoint.py` scores only legal UCI continuations from
  a Python-reference checkpoint; `scripts/chess_checkpoint_eval.py` measures
  held-out exact target and executed legality before full games.
- `scripts/chess_strength_ladder.py` runs paired-color games against pinned weak
  Stockfish policies and refuses to call smoke evidence a rating.
- Existing python-chess membership checks remain the final legality boundary.

The source data is the [Lichess evaluations database](https://database.lichess.org/),
published under CC0. Its four-field FENs are expanded and validated before use.

## What is not yet reproduced

- the external project's weights, private run state, hosted training economics,
  large-corpus checksums, or reported ladder numbers;
- a downloaded large Lichess snapshot;
- a generalizing 44M candidate—the completed 10k checkpoint learned some
  held-out move preference but no game advantage over random legal play;
- a promoted candidate on the full calibrated weak-engine ladder;
- 30-game comparisons against the 4B, 9B, and frontier policies.

The current recipe is rejected before those later stages, so no chess-strength
claim exists.

## Tiny-overfit result

The owner-approved correctness gate passed on 2026-08-05. A bounded stream from
the public source produced eight accepted positions from nine records; the
eight sequences were repeated 64 times. The 44,527,616-parameter model reached
8/8 exact legal targets at step 150 of the 200-step cap on MPS.

Accuracy was deliberately checked between training stages: 87.5% at step 50,
75% at step 100, then 100% at step 150. This is not contradictory to the
falling token loss. Cross-entropy optimizes every next byte, while the gate asks
whether one complete legal move outranks every alternative; close move margins
can temporarily change sign. At step 150 every target ranked first and the
smallest target-score margin was positive at 0.9763.

Evidence is in `evals/chess/character-chess-44m-tiny-overfit-v1.json`; the
549,286,640-byte resumable checkpoint remains local and gitignored. This passes
wiring and capacity only. It says nothing about held-out accuracy, game
strength, Elo, or superiority to larger models.

## First internal Stockfish rating

The memorization checkpoint subsequently played a separately approved rating
run. Sixty paired calibration games placed random legal play at 536 and three
increasingly strong random/Skill-0 mixtures at 732, 851, and 1027 relative to
Stockfish 18's UCI-1320 floor. The candidate then played 30 balanced games
across those five rungs.

It finished 0 wins, 9 draws, and 21 losses, with every action legal and 90% of
games ending naturally. The honest headline is **<536 Internal
Stockfish-ladder Elo**, because the 475 fitted estimate lies below the weakest
calibrated opponent. The **475** estimate and paired-opening bootstrap interval
of **416–550** remain diagnostic extrapolations only. Removing the three
160-ply cap draws gives a 457 extrapolation. The result is therefore not a
surprise: eight-position memorization taught legal local preferences, not chess
strategy. See `evals/chess/character-chess-44m-stockfish-rating-v1.json`.

This is a reproducible internal experimental scale, not FIDE or human Elo. Its
uncertainty interval conditions on the measured rung ratings and does not
propagate calibration uncertainty.

## Masked 10k pilot result

The final owner-approved shot corrected an important training mismatch before
judging the model. The generic byte trainer optimized the entire serialized
FEN-and-legal-list prompt; `scripts/chess_sft_train.py` instead masks every
prompt byte and computes loss only on the target move plus newline. The data
compiler was also corrected to canonicalize legal castling notation through
python-chess, because some normal-chess source records encode castling with the
king-to-rook Chess960 spelling.

The bounded corpus accepted 12,000 CC0 Lichess-eval positions, with 10,812
train, 588 validation, 600 test, and zero identity overlap. The run used the
first 10,000 train rows, batch 16, learning rate 3e-4, and 2,000 MPS steps.
Completion-only validation loss fell from 5.8171 to 1.3831.

Held-out move prediction improved, but not enough:

| Split | Rows | Exact | Analytic random | Gain | Top-3 |
|---|---:|---:|---:|---:|---:|
| Validation | 588 | 10.54% | 6.16% | +4.38 points | 22.79% |
| Test | 600 | 10.33% | 6.23% | +4.10 points | 23.00% |

Both splits had 100% legal execution. The consistent validation/test lift means
the model learned a real local move preference; it did not pass the frozen
+10-point pilot gate.

The transfer test settled the decision. Against random legal play, the raw
policy drew all six games and won none. The guarded policy also drew all six
and won none; its one-ply safety rules fired 22 times and changed eight moves,
but converted no win. The displayed 536 is merely equality with the only rung
in this six-game stop screen, not a qualified full-ladder or human Elo.

Therefore the current Character Chess lane stops here. We do not infer that the
model became worse than the eight-position checkpoint—the evaluations answer
different questions—but the 10k model did not acquire enough game skill to
justify 100k. Evidence is committed in
`evals/chess/character-chess-44m-pilot-10k-v1.json`; the 549 MB checkpoint and
full traces remain gitignored with committed hashes.

## Reproducing the current serving policy

The external project's current policy teacher-forces every legal UCI
continuation and plays the model-score argmax on every ply. Our Python
checkpoint policy already follows that rule.

The public implementation then re-ranks those same scored legal moves with
one-ply `python-chess` finishing guards: play mate-in-one, avoid allowing
opponent mate-in-one when a safe alternative exists, and avoid immediately
drawing a clearly won position. `scripts/chess_finishing_guards.py`
independently implements those board-only rules. It uses no Stockfish, opening
book, or search, and steps aside if it cannot offer a safer alternative.

Raw and guarded results are different policies. Every guarded decision records
the raw argmax, executed move, fired rule, and before/after candidate counts;
the ladder reports guard-fire and intervention rates. A guarded Elo improvement
is a system improvement, not evidence that the weights became smarter.

## Reproducing the evaluation and data curve

`configs/chess/move-quality-v1.json` freezes Stockfish 18 depth 12 as an offline
referee for average centipawn loss, blunders at 100 cp, and severe blunders at
300 cp. `scripts/chess_move_quality.py` consumes archived games, so the referee
cannot leak into move selection.

`configs/chess/qwen-reproduction-v1.json` freezes 10k, 100k, 1M, and 2M-row
learning-curve stages. Every stage has a terse control and an eight-percent
grounded-commentary arm, both with two-percent verified endgames. Commentary is
admitted only with a compatible recorded license and Stockfish-grounded legal
move. The 10k stage is a learning-signal gate, not a plausible 1400-Elo claim:
the external result starts from an 8B pretrained base while ours starts from a
44.5M byte model.

## Reproduction path and stop boundary

The compiler consumes decompressed JSONL so no Python decompression dependency
is required:

```bash
zstdcat /path/to/lichess_db_eval.jsonl.zst | \
  python3.12 scripts/chess_sft_corpus.py \
    --config configs/chess/lichess-eval-corpus-v1.json \
    --input - \
    --output runs/chess-44m/data/corpus.jsonl \
    --manifest runs/chess-44m/data/manifest.json
```

Then render the eight-row repeated correctness gate and train through the
existing Python reference path:

```bash
python3.12 scripts/chess_sft_text.py \
  --input runs/chess-44m/data/corpus.jsonl \
  --split train \
  --maximum-rows 8 \
  --repeat 64 \
  --output runs/chess-44m/data/tiny-overfit.txt \
  --manifest runs/chess-44m/data/tiny-overfit-manifest.json

python3.12 python_ref/train.py \
  --data runs/chess-44m/data/tiny-overfit.txt \
  --model-config configs/model.chess-44m-v0.json \
  --config configs/chess/training-tiny-overfit-v1.json \
  --out runs/chess-44m/checkpoints/tiny-overfit

python3.12 scripts/chess_checkpoint_eval.py \
  --checkpoint runs/chess-44m/checkpoints/tiny-overfit \
  --model-ref byte-character-chess-44m-v0 \
  --policy-id chess-44m-tiny-overfit \
  --data runs/chess-44m/data/corpus.jsonl \
  --split train \
  --maximum-rows 8 \
  --output runs/chess-44m/evals/tiny-overfit.json
```

The tiny gate and bounded 10k pilot ran with owner approval. The experiment
stopped at `inspect`; the later stages are not merely pending approval under
this recipe—they failed the predeclared promotion rule:

```text
compile -> tiny overfit -> 10k pilot -> inspect -> reject current recipe
```

The full 4B/9B comparison remains a requirement for any future promoted chess
candidate, but this checkpoint did not earn that expensive comparison. Any
future chess retry needs a materially different architecture, objective, or
target—not the unchanged 100k stage.

The eventual full-game command uses the same owned checkpoint directly:

```bash
python3.12 scripts/chess_strength_ladder.py \
  --config configs/chess/strength-ladder-v1.json \
  --candidate-backend python-checkpoint \
  --checkpoint runs/chess-44m/checkpoints/candidate \
  --model-ref byte-character-chess-44m-v0 \
  --policy-id chess-44m-v0 \
  --output runs/chess-44m/evals/strength-ladder.json
```
