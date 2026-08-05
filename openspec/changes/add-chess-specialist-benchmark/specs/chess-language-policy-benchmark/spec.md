# chess-language-policy-benchmark Specification

## Purpose

Measure whether stronger language models have a real chess capability advantage
and whether a future 30–50M specialist can exceed larger general LLMs under the
same character-only contract.

## ADDED Requirements

### Requirement: Common no-tools policy boundary

Every model SHALL receive the same system prompt, FEN, ply index, sorted legal
UCI moves, output limit, and time limit. Evaluated models SHALL NOT use an
engine, tool, code execution, search, rollout, opening book, or hidden state.

#### Scenario: One comparator receives engine analysis
- **WHEN** an evaluated entry can inspect engine scores or principal variations
- **THEN** validation rejects the comparison

### Requirement: Two evidence lanes

The benchmark SHALL report tactical-puzzle results as the primary dense ruler
and complete paired games as a secondary demonstrative outcome.

#### Scenario: A model wins one exhibition game but fails puzzles
- **WHEN** its tactical result does not pass the frozen gate
- **THEN** the game remains visible but cannot admit specialist training

### Requirement: Baseline and model cohort

The development screen SHALL include random legal selection, at least one
installed 4B local general model, one installed 8–9B local general model, and a
pinned frontier model whenever those runtimes are available.

#### Scenario: A requested model cannot load
- **WHEN** an entry fails before producing a complete result
- **THEN** the artifact records the failure and excludes it from aggregate claims

### Requirement: Frozen admission gate

Thresholds SHALL be frozen before model outputs are inspected. Specialist data
or training SHALL remain blocked unless the pinned frontier entry makes no
strict invalid decisions, materially exceeds random legal tactical accuracy,
and exceeds the strongest measured local general model on the primary metric.

#### Scenario: Frontier only matches the local model
- **WHEN** the frozen frontier-versus-local margin is not met
- **THEN** the benchmark is retained as a failed capability-gradient attempt and no specialist is trained

### Requirement: Paired full-game matches

Complete-game comparisons SHALL use fixed starting positions in pairs with
colors swapped and identical per-move contracts. Results SHALL report wins,
draws, losses, illegal forfeits, plies, latency, and trace IDs without making an
Elo claim from a development slice.

#### Scenario: Model emits an illegal move
- **WHEN** strict output is not currently legal
- **THEN** that game ends as an illegal-decision forfeit rather than being repaired

### Requirement: Specialist eligibility

A future specialist SHALL contain at most 50,000,000 parameters and use the
same policy boundary. Passing requires beating the named larger general LLM on
the frozen tactical suite without legality regression; match results and
resource measurements SHALL be reported alongside but SHALL NOT replace that
gate.

#### Scenario: Candidate is faster but less accurate
- **WHEN** the specialist improves latency but loses the tactical comparison
- **THEN** the result is retry or reject, not a capability-compression win

### Requirement: Honest portable artifact

The public artifact SHALL preserve model identity, revisions, raw decisions,
traces, metrics, costs, limitations, and reproduction commands. Development,
incomplete, failed, and frozen states SHALL render distinctly.

#### Scenario: Gate 0 fails
- **WHEN** the frontier capability gradient is not reproduced
- **THEN** the site retains the chess artifact and explains the failure rather than removing it
