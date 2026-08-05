## ADDED Requirements

### Requirement: Versioned benchmark contracts
The system SHALL define machine-validated, versioned contracts for suites,
tasks, entries, runs, results, resource measurements, system-routing evidence,
and official evaluation receipts, and every artifact SHALL identify the exact
contract, task, instance set, runner, and scorer revisions used.

#### Scenario: A result is submitted
- **WHEN** an entry result is validated
- **THEN** its suite, task, instance-set, runner, and scorer identities resolve
  to one compatible versioned benchmark configuration
- **AND** unknown versions, dangling task ids, or inconsistent instance counts
  are rejected

### Requirement: Explicit competition tracks
Every entry SHALL declare exactly one of `generalist`, `adapted`, or `system`,
and the benchmark SHALL retain track-specific disclosure in machine and rendered
results.

#### Scenario: An adapted specialist is submitted
- **WHEN** an entry used benchmark-specific training data
- **THEN** it is classified as `adapted`
- **AND** its base, training sources, permitted benchmark split, row count,
  method, training time, and compute/cost evidence are recorded or explicitly
  marked missing

#### Scenario: A routed cascade is submitted
- **WHEN** more than one model, router, verifier, or fallback can participate
- **THEN** the entry is classified as `system`
- **AND** all eligible and invoked components plus graph/policy revisions are
  disclosed

### Requirement: Frontier-qualified tasks
An official ranked task SHALL declare and pass a near-ceiling frontier
qualification threshold on the same task contract and scorer before small-model
results are reported as capability retention.

#### Scenario: The frontier fails the ruler
- **WHEN** the declared frontier result falls below the configured qualification
  threshold or exposes ambiguous/ungroundable golds
- **THEN** the task remains `development` or `training-only`
- **AND** it contributes no official rank or reported Mac-versus-frontier gap

### Requirement: Verifiable everyday outcomes
Every V1 ranked task SHALL use a deterministic structural, executable, AST,
semantic-call, or final-state scorer as its primary authority, and judge-only
subjective scoring MUST NOT determine V1 success.

#### Scenario: A task changes files or records
- **WHEN** an entry completes the task
- **THEN** success is computed from the declared final state and invariants
- **AND** plausible prose without the required state change receives no success
  credit

### Requirement: Fair same-instance comparison
Entries shown in one headline comparison SHALL use the identical versioned
instance set, task-visible instructions, tool/environment surface, budgets,
repetition protocol, and scorer.

#### Scenario: Baseline sample count differs
- **WHEN** two runs do not share the same instance-set hash or comparable budget
- **THEN** the renderer does not place them in one headline win/loss table
- **AND** the difference is surfaced as an incompatibility rather than silently
  normalized

### Requirement: Sealed evaluation and leakage evidence
Official ranking SHALL use a sealed instance set or maintainer-held generation
seeds, SHALL keep secrets and private prompts outside the repository, and SHALL
emit a privacy-safe receipt containing evaluation identity, custody, overlap
checks, aggregate results, and replay metadata.

#### Scenario: An official evaluation completes
- **WHEN** the sealed evaluator accepts a run
- **THEN** the receipt records the instance-set hash, permitted training cutoff,
  overlap results, runner/scorer revisions, and bounded aggregate evidence
- **AND** it contains no credential, private prompt, raw personal data, or model
  output prohibited by the task publication policy

### Requirement: Reliability and regression reporting
Every official entry SHALL report repeated-run reliability when the task is
non-deterministic, primary and protected/regression slices, and skipped or
missing checks.

#### Scenario: A specialist wins its primary slice but harms breadth
- **WHEN** the primary score improves and a protected slice regresses
- **THEN** both values and thresholds appear beside the result
- **AND** the benchmark does not collapse them into an unqualified overall win

### Requirement: Selective-risk system metrics
Every `system` entry SHALL report false acceptance, first-hop acceptance rate
and accuracy, escalation rate, route accuracy or regret, escalation precision
and recall, over-escalation, hop distribution, final tier, and typed exhaustion
in addition to final task success. Threshold or learned-policy selection SHALL
use only a declared public-development or calibration layer and SHALL never fit
against the sealed official layer.

#### Scenario: A small specialist returns an incorrect result without fallback
- **WHEN** the primary scorer rejects the result but the system marks it accepted
- **THEN** the run records a false accept
- **AND** that instance cannot be counted as successful even if it avoided a
  larger-model call

#### Scenario: A selective policy is calibrated
- **WHEN** confidence, margin, entropy, OOD, or verifier signals choose whether the first node is accepted or escalated
- **THEN** the policy records its calibration instance-set identity, targets, signal contract, and revision
- **AND** calibration refuses a sealed-official instance set

#### Scenario: A specialist tree escalates through several tiers
- **WHEN** a system traverses one or more ordered fallback nodes
- **THEN** every eligible and selected node, hop, final tier, exhaustion state, and graph/policy revision remains attributable
- **AND** the first-hop metrics remain distinct from final cascade accuracy

### Requirement: Complete end-to-end resource accounting
The benchmark SHALL distinguish cold and warm end-to-end latency, active
parameters, resident bytes, installed artifact bytes, shared-base and adapter
bytes, energy, training/eval time, and local/external cost with explicit
measurement state.

#### Scenario: A routed result loads two models
- **WHEN** routing, loading, verification, or retry contributes to execution
- **THEN** total latency and peak residency include that work
- **AND** model-only timing may be shown only as an additional labeled metric

### Requirement: Deterministic public report
The benchmark SHALL compile validated results into deterministic JSON and a
static cohort report whose default views preserve track, task, slice,
reliability, selective-risk, and resource evidence and emphasize Pareto
trade-offs over a single composite score.

#### Scenario: The same validated cohort is rendered twice
- **WHEN** source artifacts and renderer revision are unchanged
- **THEN** substantive JSON and report output are identical
- **AND** missing measurements render as missing rather than zero

### Requirement: Lightweight infrastructure verification
The repository SHALL provide a no-model test path that validates schemas,
runner orchestration, scorers, receipts, privacy checks, and report determinism
without training, model loading, provider calls, sustained compute, or deploy.

#### Scenario: CI runs the benchmark smoke
- **WHEN** only synthetic fixture entries and outcomes are available
- **THEN** all infrastructure acceptance and rejection paths execute locally
- **AND** no network credential, GPU/model runtime, or production surface is
  required
