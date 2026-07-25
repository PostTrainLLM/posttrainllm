# Fine-Tune Report Card

## Purpose

Define the canonical, portable proof surface for a fine-tune decision: one
deterministic machine-readable report and static public rendering compiled from
existing factory-run evidence without loading or rerunning a model.

## Requirements

### Requirement: Canonical factory-run ingestion
The report-card compiler SHALL consume an existing factory-run directory and MUST NOT require model loading, training, generation, or GPU execution.

#### Scenario: Canonical run is provided
- **WHEN** a run directory contains valid config, dataset, baseline, candidate, provenance, artifact, and decision fragments
- **THEN** the compiler produces a versioned report-card payload from those files
- **AND** records the source file identity for each reported field

#### Scenario: Run is incomplete
- **WHEN** a required artifact is absent or invalid
- **THEN** the compiler either rejects the report card or marks the affected fields missing according to the publication policy
- **AND** does not infer the missing measurement

### Requirement: Honest measurement states
Every report-card value SHALL be classified as `measured`, `derived`, `historical`, `skipped`, `missing`, or `not-applicable` with provenance and explanatory notes where required.

#### Scenario: Performance was not recorded
- **WHEN** latency, RAM, throughput, cost, or timing evidence is absent
- **THEN** the corresponding value is marked missing
- **AND** the report does not render zero or an estimated number as measured

#### Scenario: Historical result is imported
- **WHEN** a legacy artifact supplies a value that lacks current canonical provenance
- **THEN** the value is marked historical
- **AND** its caveat is visible in both machine-readable and public output

### Requirement: Before-and-after evaluation
The report card SHALL show baseline, candidate, absolute delta, threshold, pass/fail, sample size, and eval identity for the primary gate and every regression or breadth gate.

#### Scenario: Target improves but breadth regresses
- **WHEN** the candidate passes the primary target and violates a regression threshold
- **THEN** the report shows both outcomes independently
- **AND** does not present the candidate as an unconditional win

#### Scenario: Slice evidence exists
- **WHEN** slice metrics are present
- **THEN** the report shows per-slice baseline, candidate, delta, sample size, and gate status

### Requirement: Eval validity and leakage disclosure
The report card MUST expose frontier-ceiling validation, frozen-eval identity, dataset/eval overlap checks, and known eval limitations before it can present a ship decision as verified.

#### Scenario: Frontier ceiling is unverified
- **WHEN** the benchmark lacks the required frontier-ceiling evidence
- **THEN** the report identifies the eval as unverified
- **AND** cannot label the ship decision fully verified

#### Scenario: Leakage check fails
- **WHEN** training data overlaps a held-out evaluation beyond the allowed policy
- **THEN** the report fails publication validation
- **AND** identifies the affected dataset and eval without hiding the candidate measurements

### Requirement: Decision semantics
The report card SHALL preserve the canonical `ship`, `reject`, `retry-data`, `retry-training`, `retry-eval`, and `park` decisions, including reason, confidence, failure evidence, lesson, and exactly one next action where applicable.

#### Scenario: Candidate is rejected
- **WHEN** `decision.json` records `reject`
- **THEN** the report prominently shows why the candidate did not ship
- **AND** retains the measured gains and failures that informed the decision

#### Scenario: Candidate ships with routing constraints
- **WHEN** a shipped artifact is safe only for a named route or task envelope
- **THEN** the report shows that constraint beside the ship decision
- **AND** does not describe the model as a general replacement

### Requirement: Stable machine and public outputs
The compiler SHALL emit versioned JSON and a deterministic static public report from the same validated payload.

#### Scenario: Output is rebuilt
- **WHEN** the same source artifacts and compiler version are processed twice
- **THEN** substantive JSON and public report content are identical

#### Scenario: Third party reads the report
- **WHEN** a visitor opens a published report without the repository or a GPU
- **THEN** the visitor can inspect the decision, measurements, caveats, and source evidence links

### Requirement: Publication gate
A report card MUST pass schema, provenance, evidence, leakage, decision, and public-safety validation before it is added to the public artifact registry.

#### Scenario: Validation fails
- **WHEN** any mandatory publication check fails
- **THEN** the compiler exits non-zero
- **AND** no publishable artifact is produced

#### Scenario: Report-only candidate passes
- **WHEN** a non-ship candidate has complete evidence and an honest retry/reject decision
- **THEN** it can be published as a report-only artifact
- **AND** it is not labeled as a shipped specialist

### Requirement: Dogfood coverage
The project SHALL produce report cards for successful, routed, retry, reject, and historical-evidence cases before treating the format as the canonical public proof surface.

#### Scenario: Existing artifact cohort is compiled
- **WHEN** the initial dogfood pass runs over the selected factory artifacts
- **THEN** each supported outcome class has at least one reviewed report or a documented absence
- **AND** review findings feed back into the schema and validation fixtures
