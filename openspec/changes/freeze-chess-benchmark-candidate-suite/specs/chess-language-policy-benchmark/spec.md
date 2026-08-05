## MODIFIED Requirements

### Requirement: Every policy uses one shared observation and explicit action track

Every policy SHALL receive the same canonical FEN, ply, and sorted legal-UCI
set. Each result SHALL declare either the strict raw-output track or the
legal-constrained action track. Constrained results SHALL disclose intervention
and SHALL NOT overwrite strict diagnostics.

#### Scenario: Constrained cloud baseline

- **WHEN** a cloud model is evaluated with a legal-enum response schema
- **THEN** the artifact identifies the constrained track
- **AND** reports exact move quality independently from executed legality

#### Scenario: Future local specialist

- **WHEN** a local specialist chooses a move
- **THEN** non-legal actions are masked before selection or only legal
  candidates are scored
- **AND** the executor performs a final membership check
