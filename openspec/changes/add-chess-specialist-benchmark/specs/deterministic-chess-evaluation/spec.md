# deterministic-chess-evaluation Specification

## Purpose

Provide a versioned chess correctness oracle for tactical decisions and full
games without giving evaluated language models engine or search access.

## ADDED Requirements

### Requirement: Canonical chess state

The evaluator SHALL normalize each position as six-field FEN and SHALL derive a
lexicographically sorted list of legal UCI moves from the pinned rules runtime.

#### Scenario: Position contains castling or en passant rights
- **WHEN** a fixture is loaded
- **THEN** those rights survive normalization and determine the legal move set

### Requirement: Strict language-model action

The strict parser SHALL accept exactly one UCI move that is legal in the
current position and SHALL reject prose, SAN, malformed, and illegal outputs
without substituting another move.

#### Scenario: Model returns commentary around a legal move
- **WHEN** raw output is `I choose e2e4`
- **THEN** the evaluator records an invalid decision

### Requirement: Reproducible tactical verification

Each tactical fixture SHALL carry a stable identifier, provenance, FEN,
expected best move set, theme tags, split, and label-runtime identity. The
evaluator SHALL report exact best-move accuracy and legal-move rate.

#### Scenario: Multiple moves are equivalent
- **WHEN** the label source declares more than one accepted best move
- **THEN** any declared move receives exact credit and the complete set remains visible

### Requirement: Complete game transitions

The environment SHALL apply only legal moves, record every pre/post FEN, and
terminate on checkmate, stalemate, insufficient material, legal repetition or
move-count draw claims, or an invalid-decision forfeit.

#### Scenario: Promotion move is played
- **WHEN** the policy returns a legal promotion UCI move
- **THEN** the promoted piece and resulting FEN are recorded without ambiguity

### Requirement: Stable traces

Tactical decisions and games SHALL use canonical JSON hashing so identical
inputs, outputs, rules revision, and transitions produce identical trace IDs.

#### Scenario: Replay is regenerated
- **WHEN** the same recorded decisions are replayed under the same revisions
- **THEN** every state transition and trace hash matches
