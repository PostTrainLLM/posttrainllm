# Character Chess Specialist Specification

## ADDED Requirements

### Requirement: Parameter-count truth

The candidate specialist SHALL contain from 30,000,000 through 50,000,000
parameters, measured by the repository's canonical model estimator. Training-row
counts SHALL NOT be presented as model parameter counts.

#### Scenario: External 30M evidence is referenced

- **WHEN** the Qwen Chess 30M campaign is described
- **THEN** it is labeled as approximately 30 million training positions on an 8B base
- **AND** it is not counted as a sub-50M specialist

### Requirement: Reproducible public-data compiler

The data path SHALL accept decompressed Lichess evaluation JSONL, validate the
four-field FEN and best PV move, apply frozen quality filters, and emit
deterministic character-policy rows plus a provenance manifest.

#### Scenario: The same snapshot is compiled twice

- **WHEN** source bytes and config are unchanged
- **THEN** row order, splits, row hashes, counts, and output hashes are identical

#### Scenario: A malformed or illegal label is encountered

- **WHEN** the FEN, evaluation, PV, or first move cannot be validated
- **THEN** the row is rejected with a counted reason
- **AND** it never enters any training or evaluation split

### Requirement: Disjoint held-out splits

Split assignment SHALL derive from a seeded hash of canonical FEN identity and
SHALL prevent the same position from appearing in multiple splits.

#### Scenario: Repeated source FENs occur

- **WHEN** duplicate evaluations appear in the source stream
- **THEN** only the first admissible canonical position is emitted
- **AND** later duplicates are counted as rejected

### Requirement: Guaranteed legal execution

The primary full-game policy SHALL score only the current legal UCI candidates
or mask every illegal candidate before selection, then validate membership
again before executing. Strict raw generation SHALL remain a separate
diagnostic.

#### Scenario: The raw model prefers an illegal string

- **WHEN** legal-candidate selection is active
- **THEN** the executed action is selected only from python-chess's legal set
- **AND** the report records the strict failure or constraint intervention separately

### Requirement: Full-game calibrated ladder

The evaluation SHALL support pinned Stockfish, node-limited weak play,
seeded random-mixture rungs, paired colors, frozen openings, and complete game
traces.

#### Scenario: A candidate plays one ladder rung

- **WHEN** paired games complete
- **THEN** the report records wins, draws, losses, completion, raw and executed legality, invalid forfeits, and source traces

### Requirement: Honest internal ratings

Any numerical rating SHALL be labeled internal Arena Elo, name its exact pool
and anchor, include uncertainty and sample size, and remain `unrated` until
minimum games, connectivity, color balance, and forfeit gates pass.

#### Scenario: Only smoke games exist

- **WHEN** fewer than 30 completed candidate games are available
- **THEN** the candidate remains unrated
- **AND** no FIDE, Lichess, Chess.com, engine, or human Elo equivalence is claimed

#### Scenario: Candidate falls below the calibrated ladder

- **WHEN** the fitted estimate is below the weakest calibrated opponent
- **THEN** the headline rating is `<weakest-rung-rating`
- **AND** any fitted number is labeled diagnostic extrapolation rather than a qualified rating

### Requirement: Separately rated serving policies

The raw always-score legal argmax and any deterministic finishing-guard policy
SHALL have distinct revisions, traces, intervention metrics, and ratings.

#### Scenario: A finishing guard changes the selected move

- **WHEN** mate delivery, mate avoidance, or draw avoidance narrows the model-ranked candidates
- **THEN** the trace records the fired guard, before/after candidate counts, raw argmax, and executed move
- **AND** the result is not attributed to the model weights alone

### Requirement: Engine-free finishing guards

Finishing guards SHALL inspect only the current board, move history, and legal
candidates already scored by the model. They SHALL NOT use Stockfish, an
opening book, or search at serving time.

#### Scenario: Every candidate is unsafe

- **WHEN** a guard cannot offer at least one safer candidate
- **THEN** it steps aside and preserves the model's original ranking

### Requirement: Stockfish move-quality diagnostic

Archived candidate moves SHALL be gradeable by a pinned Stockfish referee for
average centipawn loss, blunder rate at 100 cp, and severe-blunder rate at 300
cp, separately by serving policy.

#### Scenario: A game trace is graded

- **WHEN** a legal candidate move is compared with Stockfish's best move
- **THEN** the score is from the mover's perspective at the frozen limit
- **AND** Stockfish is disclosed as an offline referee unavailable at inference

### Requirement: Staged composition experiment

The reproduction SHALL define 10k, 100k, 1M, and 2M learning-curve stages with
exact source counts, checksums, split identity, and terse-only versus grounded-
commentary arms before each training run.

#### Scenario: Commentary data is proposed

- **WHEN** grounded commentary is included
- **THEN** its license and Stockfish-grounded move are verified
- **AND** an otherwise matched terse-only arm remains available for attribution

### Requirement: Heavy work remains operator-gated

Large dataset downloads, million-row compilation, sustained engine matches,
and model training SHALL require explicit owner approval and repository workload
guardrails.

#### Scenario: Offline infrastructure is complete

- **WHEN** no-model tests pass
- **THEN** the implementation may document the heavy commands
- **AND** it does not execute them automatically
