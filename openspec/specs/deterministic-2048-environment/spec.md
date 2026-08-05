# deterministic-2048-environment Specification

## Purpose
Provide a reproducible, judge-free 2048 environment whose transitions, rewards,
and trajectories can serve as the correctness oracle for a Mac-local game-policy
specialist experiment.
## Requirements
### Requirement: Canonical board transitions
The environment SHALL represent a 4-by-4 board containing zero or power-of-two
tile values and SHALL apply canonical 2048 compression, single-merge-per-tile,
move-score, and directional behavior.

#### Scenario: Equal tiles merge once
- **WHEN** a legal move brings four equal tiles together in one row
- **THEN** the environment produces two doubled tiles rather than recursively merging the result again in the same move

#### Scenario: Directional transforms agree
- **WHEN** equivalent boards are rotated or reflected with their requested move
- **THEN** the resulting board and score delta preserve the corresponding canonical 2048 transformation

### Requirement: Spawn and invalid-move semantics
The environment SHALL spawn exactly one new tile after a state-changing legal
move and SHALL not spawn, mutate state, increment move count, or consume random
state after an invalid or non-state-changing move.

#### Scenario: Successful move spawns once
- **WHEN** a requested move changes the board
- **THEN** the move result contains exactly one newly spawned tile chosen by the seeded environment distribution

#### Scenario: Non-changing move is rejected
- **WHEN** a requested direction cannot change the board
- **THEN** the environment reports the move as invalid and leaves board, score, move count, and seeded random state unchanged

### Requirement: Seeded reproducibility
The environment SHALL reproduce the same initial state and complete trajectory
for the same seed and action sequence, independent of wall-clock time or process
history.

#### Scenario: Replay a trajectory
- **WHEN** two fresh environments receive the same seed and action sequence
- **THEN** every observation, spawned tile, score delta, terminal flag, and final state is identical

### Requirement: Legal actions and terminal state
The environment SHALL expose the legal subset of `up`, `down`, `left`, and
`right`, and SHALL declare a game terminal exactly when no direction can change
the board.

#### Scenario: Full board with a merge remains live
- **WHEN** a full board contains at least one horizontally or vertically adjacent equal pair
- **THEN** the environment reports at least one legal action and does not mark the game terminal

#### Scenario: Full board without a merge ends
- **WHEN** a full board has no horizontally or vertically adjacent equal pair
- **THEN** the environment reports no legal actions and marks the game terminal

### Requirement: Auditable trajectory records
The environment SHALL emit machine-readable per-step records containing seed,
step index, pre-move board, legal actions, chosen action, post-move board, score
delta, cumulative score, maximum tile, and terminal state.

#### Scenario: Record a complete game
- **WHEN** an agent plays from reset until terminal state
- **THEN** the emitted records are sufficient to deterministically replay and verify every transition without invoking that agent

### Requirement: Leakage-safe policy examples
Generated policy examples SHALL carry their game seed and SHALL prevent a game
seed or exact normalized board state from crossing declared train and evaluation
splits.

#### Scenario: Reject a leaking split
- **WHEN** a proposed train/evaluation manifest shares a seed or normalized board state across splits
- **THEN** validation fails before either split is accepted as benchmark evidence
