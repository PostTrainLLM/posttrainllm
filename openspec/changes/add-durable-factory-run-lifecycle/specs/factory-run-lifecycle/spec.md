## ADDED Requirements

### Requirement: Versioned lifecycle record
Every lifecycle-managed factory run SHALL have an authoritative
`run-status.json` containing a schema version, matching run id, monotonic
revision, canonical phase, update time, and last-transition provenance.

#### Scenario: New run is initialized
- **WHEN** lifecycle management is initialized for a new factory run
- **THEN** the system writes a valid `created` status at revision one
- **AND** the status run id matches the canonical run configuration

#### Scenario: Status identity conflicts with the run
- **WHEN** `run-status.json` names a different run id than `config.json`
- **THEN** validation fails without modifying either file

### Requirement: Legal and terminal transitions
The system SHALL enforce the documented lifecycle transition graph, SHALL
require a reason for alternate skipped-stage edges, and MUST reject regressive
or post-terminal transitions.

#### Scenario: Normal factory phase advances
- **WHEN** a caller requests a legal transition from the current phase using
  the current revision
- **THEN** the system records the next phase and increments the revision once

#### Scenario: Alternate flow skips an inapplicable stage
- **WHEN** a report-only or evaluation-only run requests a documented alternate
  transition
- **THEN** the system requires and records a machine-readable skip reason

#### Scenario: Terminal run is changed
- **WHEN** a caller attempts to transition a `decided` or `failed` run
- **THEN** the system rejects the update
- **AND** directs retry work to a new linked run

### Requirement: Decision remains the outcome authority
Lifecycle state SHALL remain operational metadata and MUST NOT replace,
reinterpret, or fabricate the canonical `decision.json` outcome.

#### Scenario: Run reaches decided
- **WHEN** a run transitions to `decided`
- **THEN** a valid canonical `decision.json` exists
- **AND** lifecycle metadata references the transition without duplicating the
  ship, reject, retry, or park judgment

#### Scenario: Run reaches evaluated
- **WHEN** a run reaches `evaluated` without a terminal decision
- **THEN** consumers do not present it as shipped, rejected, or complete

### Requirement: Atomic concurrency-safe persistence
Lifecycle mutations SHALL use same-filesystem atomic replacement and a
short-lived per-run lock, and MUST compare the caller's expected revision before
committing an update.

#### Scenario: Writer is interrupted before replacement
- **WHEN** a writer stops after creating a temporary status file but before
  atomic replacement
- **THEN** readers continue to observe the previous complete status
- **AND** reconciliation can remove the abandoned temporary file

#### Scenario: Stale writer attempts an update
- **WHEN** a caller supplies an expected revision older than the durable
  revision
- **THEN** the transition fails without overwriting the newer state

#### Scenario: Two writers race
- **WHEN** two writers request transitions from the same revision
- **THEN** at most one transition commits
- **AND** the losing writer receives a stale-revision or lock-conflict result

### Requirement: Repairable run discovery
The system SHALL support current and latest run discovery through atomic,
advisory pointers and MUST verify each pointer against the target run's
authoritative status before returning it.

#### Scenario: Valid pointer is read
- **WHEN** a pointer resolves within the configured run root and its run id,
  revision, and phase match `run-status.json`
- **THEN** discovery returns the referenced run

#### Scenario: Pointer is stale or missing
- **WHEN** a pointer is absent, malformed, escapes the run root, or disagrees
  with the target status
- **THEN** discovery does not trust it
- **AND** reconciliation can rebuild pointers by scanning valid run statuses

#### Scenario: Multiple active runs exist
- **WHEN** more than one non-terminal run exists
- **THEN** `factory-run list` reports all of them
- **AND** the current pointer is not interpreted as proof of exclusivity

### Requirement: Metadata-only lifecycle CLI
The CLI SHALL provide commands to initialize, inspect, transition, list, and
reconcile lifecycle metadata without loading models, running evals, accessing
the network, or requiring a GPU.

#### Scenario: Operator inspects a run
- **WHEN** the operator requests lifecycle status in human-readable or JSON form
- **THEN** the command returns the validated phase, revision, time, provenance,
  and any sanitized failure state

#### Scenario: Operator previews reconciliation
- **WHEN** the operator runs reconciliation in dry-run mode
- **THEN** the command reports stale locks, temporary files, invalid pointers,
  and proposed repairs without changing files

#### Scenario: Metadata command is executed
- **WHEN** any lifecycle-only command runs
- **THEN** it does not initialize MLX, load a checkpoint, start a server, train,
  evaluate, package, publish, or deploy

### Requirement: Durable boundary integration
Factory integrations SHALL advance lifecycle state only after the durable
artifacts for that boundary have been written and validated.

#### Scenario: Eval fragment write fails
- **WHEN** evaluation output cannot be written or validated
- **THEN** the run does not advance to `evaluated`
- **AND** the prior durable phase remains readable

#### Scenario: Assembly succeeds
- **WHEN** the assembler durably writes and validates the report/provenance
  artifacts
- **THEN** a lifecycle-managed run can advance through `reporting`
- **AND** it reaches `decided` only after canonical decision validation passes

#### Scenario: Command fails after run creation
- **WHEN** an integrated command fails after a lifecycle-managed run exists
- **THEN** it may record a `failed` transition with a bounded sanitized error
- **AND** it does not copy raw logs or private payloads into the status

### Requirement: Honest legacy compatibility
Existing factory folders without lifecycle metadata SHALL remain readable
during migration, and any imported status MUST identify itself as imported and
MUST NOT fabricate unobserved phase history.

#### Scenario: Complete legacy run is imported
- **WHEN** a legacy folder has a valid canonical decision and required evidence
- **THEN** import may create a `decided` lifecycle snapshot marked imported
- **AND** records the evidence used to justify that phase

#### Scenario: Partial legacy run is imported
- **WHEN** a legacy folder contains only a subset of valid fragments
- **THEN** import records no phase beyond what those fragments prove
- **AND** does not synthesize missing timestamps, commands, or outcomes

#### Scenario: Legacy run is only inspected
- **WHEN** an existing run without lifecycle metadata is validated before the
  migration gate becomes mandatory
- **THEN** existing run and publication semantics remain unchanged

### Requirement: Private-data and authority boundaries
Lifecycle files and any Foundry projection SHALL contain only bounded
operational metadata and MUST NOT include secrets, private rows, prompts,
completions, raw predictions, checkpoint bytes, optimizer state, or raw log
content. Lifecycle completion MUST NOT grant publication authority.

#### Scenario: Failure contains private command output
- **WHEN** a command fails with output containing a prompt, dataset row, secret,
  or raw model response
- **THEN** lifecycle recording stores only an allowed error code and sanitized
  bounded summary

#### Scenario: Run reaches decided
- **WHEN** lifecycle state becomes `decided` and all local checks pass
- **THEN** model publication, release, and deployment remain pending explicit
  human authorization
