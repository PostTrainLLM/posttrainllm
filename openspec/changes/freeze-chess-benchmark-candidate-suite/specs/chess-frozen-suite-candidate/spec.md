## ADDED Requirements

### Requirement: Candidate labels are stable engine evidence

The system SHALL admit a candidate label only when pinned Stockfish 18 returns
the same top UCI move at depth 16 and depth 20, the final MultiPV evidence
satisfies the configured separation rule, the principal variation is legal,
and the normalized position is unique.

#### Scenario: Deeper search changes the best move

- **WHEN** the depth-16 and depth-20 top moves differ
- **THEN** the candidate is rejected as label-unstable
- **AND** both analyses remain in the evidence artifact

#### Scenario: Stable separated move

- **WHEN** both depths select the same move and the final best-vs-second gap
  meets the configured threshold
- **THEN** the candidate may enter the admitted pool

### Requirement: Model agreement is secondary evidence

The system SHALL report Claude/GPT agreement and disagreement with the engine
label but SHALL NOT use language-model consensus to create or overwrite a
chess label.

#### Scenario: Every language model disagrees with Stockfish

- **WHEN** all evaluated language models select a different legal move
- **THEN** the position is flagged for human review
- **AND** its engine label remains unchanged unless engine or human audit finds
  a concrete defect

### Requirement: Executed moves are legal by construction

The system SHALL construct the action space from the canonical current legal
UCI set, SHALL validate the selected action before transition, and SHALL never
execute a value outside that set.

#### Scenario: Structured selection succeeds

- **WHEN** the model selects a member of the legal enum
- **THEN** the executor applies that move
- **AND** records executed legality as true

#### Scenario: Model or provider returns an invalid value

- **WHEN** output is illegal, malformed, empty, timed out, or unavailable
- **THEN** the executor abstains or invokes a disclosed redirect policy
- **AND** no invalid move is applied

### Requirement: Constraint help remains visible

The system SHALL report raw legality, constraint intervention, executed
legality, abstention, and redirection as separate metrics.

#### Scenario: Constraint repairs an otherwise invalid decision

- **WHEN** the raw lane is invalid but constrained selection returns a legal
  move
- **THEN** executed legality is true
- **AND** intervention is true
- **AND** raw legality remains false

### Requirement: Expansion attempts are reproducible and retained

The system SHALL freeze seeds, suite identity, engine settings, model matrix,
budgets, and trace hashes before scoring and SHALL retain failed, unavailable,
or superseded attempts.

#### Scenario: Requested model alias is unavailable

- **WHEN** a configured model cannot be resolved without fallback
- **THEN** the attempt is recorded as unavailable
- **AND** no other model is substituted under that identity
