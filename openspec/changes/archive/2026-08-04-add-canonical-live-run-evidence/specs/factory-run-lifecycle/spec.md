## MODIFIED Requirements

### Requirement: Durable boundary integration
Factory integrations SHALL advance lifecycle state only after the durable
artifacts for that boundary have been written and validated. Live command
integration MUST be explicit, MUST validate frozen run identity before model
work, and MUST NOT infer missing target, dataset, evaluation, decision, or
publication evidence.

#### Scenario: SFT starts for a prepared run
- **WHEN** `sft` receives an explicit lifecycle-managed run directory in the
  `data-ready` phase
- **THEN** it validates the run config and dataset before loading a model
- **AND** advances to `training` with command provenance

#### Scenario: SFT finishes successfully
- **WHEN** the adapter has been durably saved
- **THEN** the command writes a bounded training log, measured training time,
  and a valid unshipped artifact fragment
- **AND** advances to `trained` only after those artifacts validate

#### Scenario: Evaluation completes
- **WHEN** `eval-gate` evaluates the frozen primary suite for a run in the
  `trained` phase
- **THEN** it writes valid baseline and candidate fragments from the same gate
- **AND** advances to `evaluated` only after both fragments validate

#### Scenario: Comparison rows are materialized
- **WHEN** `eval-compare` receives an explicit run directory and compatible E0
  rows
- **THEN** it writes deterministic per-slice baseline/candidate evidence
- **AND** does not change lifecycle phase or decision state

#### Scenario: Live integration is not requested
- **WHEN** a supported command runs without the explicit run-directory flag
- **THEN** its prior behavior and output locations remain unchanged

#### Scenario: Run context is incomplete or incompatible
- **WHEN** config, dataset, lifecycle identity, phase, primary-suite evidence,
  or model grouping is missing or inconsistent
- **THEN** the command fails closed without claiming the next durable phase
- **AND** does not invent a decision or missing evidence

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
- **THEN** it may preserve the last honest active phase or record a `failed`
  transition with a bounded sanitized error
- **AND** it does not copy raw logs or private payloads into the status
