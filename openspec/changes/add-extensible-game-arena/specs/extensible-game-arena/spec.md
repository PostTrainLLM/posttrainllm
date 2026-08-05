# Extensible Game Arena Specification

## ADDED Requirements

### Requirement: Competition-family-specific rating

The arena SHALL require every game to declare a supported competition family.
Head-to-head win/draw/loss games MAY emit internal Arena Elo. Independent-score
games SHALL emit score-distribution metrics and SHALL NOT emit Elo.

#### Scenario: A single-player game is imported

- **WHEN** a 2048 trial contains model and paired random scores
- **THEN** the arena reports paired score statistics and uncertainty
- **AND** no Elo field is present for that game

### Requirement: Arena Elo is not human chess Elo

Head-to-head ratings SHALL be labeled `Arena Elo`, SHALL name the exact pool and
protocol, and SHALL explicitly disclaim equivalence to FIDE, human, engine,
Chess.com, or Lichess ratings.

#### Scenario: Chess ratings are displayed

- **WHEN** the chess arena renders a rating estimate
- **THEN** the interface names it Arena Elo and exposes its sample and interval
- **AND** it makes no human-rating equivalence claim

### Requirement: Qualification is separate from estimation

The scorer SHALL calculate a deterministic provisional estimate when evidence
is mathematically sufficient, but SHALL mark policies `unrated` until frozen
minimum-game, per-policy coverage, connectivity, balance, and forfeit-quality
requirements pass.

#### Scenario: Four development games are scored

- **WHEN** the current Qwen chess artifact is imported
- **THEN** a provisional diagnostic estimate MAY be recorded
- **AND** both policies remain unrated because the qualification gates fail

### Requirement: Deterministic uncertainty

Every reported Arena Elo or paired-score estimate SHALL include a deterministic
seeded 95% uncertainty interval, bootstrap count, and scoring configuration.

#### Scenario: The report is rebuilt

- **WHEN** unchanged evidence and config are scored twice
- **THEN** ratings, intervals, qualification, and trace hash are byte-identical

### Requirement: Evidence-preserving adapters

Game adapters SHALL preserve participant identity, source artifact path, trace
hash when available, outcome, termination/failure semantics, and game-specific
metadata needed to interpret the score.

#### Scenario: An illegal-decision chess forfeit is imported

- **WHEN** the source game ended in `invalid-decision-forfeit`
- **THEN** the match result remains countable under the frozen policy
- **AND** the arena separately reports it as a forfeit

### Requirement: No puzzle-to-Elo conversion

The arena SHALL NOT convert tactical exact-move accuracy, centipawn loss,
single-player score, or arbitrary benchmark percentage into head-to-head Elo.

#### Scenario: A tactical matrix is supplied as match evidence

- **WHEN** evidence lacks two interacting participants and a win/draw/loss result
- **THEN** the head-to-head adapter rejects it

### Requirement: Extensible adapter registry

The implementation SHALL expose a registry where a new game can normalize its
evidence into an existing competition family without changing the generic
scorer or report schema.

#### Scenario: Another deterministic game is added

- **WHEN** its adapter emits valid head-to-head matches or paired-score trials
- **THEN** the existing scorer, validator, smoke, and dashboard can consume it

### Requirement: Candidate-only first report

The initial cross-game report SHALL use committed chess and 2048 evidence only,
perform no provider calls or model loading, and remain candidate evidence.

#### Scenario: The first arena report is generated in CI

- **WHEN** the no-model smoke runs
- **THEN** it reads local JSON, scores both competition families, and validates output
- **AND** it performs no network, GPU, training, or inference work

### Requirement: Inspectable public dashboard

The browser SHALL provide a responsive arena dashboard that exposes rank or
score, uncertainty, sample size, qualification failures, forfeits/failures,
source evidence, and links to existing game replays.

#### Scenario: A visitor compares arena entries

- **WHEN** the visitor switches between Chess and 2048
- **THEN** the vocabulary changes from Arena Elo to paired score metrics
- **AND** incomplete or unqualified evidence remains visibly labeled
