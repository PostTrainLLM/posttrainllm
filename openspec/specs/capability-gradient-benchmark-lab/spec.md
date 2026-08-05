# capability-gradient-benchmark-lab Specification

## Purpose
TBD - created by archiving change add-capability-gradient-benchmark-lab. Update Purpose after archive.
## Requirements
### Requirement: Capability gradient gate before specialist training
The system SHALL define a capability gradient gate that must pass before any
specialist training is allowed on a benchmark task: a pinned frontier LLM
must materially beat a valid random/legal executor on the same task, scorer,
and instance set. The gate threshold, frontier model identity, and
random-legal baseline score SHALL be recorded before any specialist result is
reported on that task.

#### Scenario: 2048 fails the gradient gate
- **WHEN** the frontier LLM's score on character-only 2048 does not exceed
  the random-legal baseline by the configured margin
- **THEN** 2048 is marked `gate-failed` and no specialist training is allowed
  on it
- **AND** the ranked alternative candidates are used instead

### Requirement: Ranked candidate scorecard
The system SHALL provide a machine-readable scorecard that ranks at least six
deterministic text-only candidate tasks, including both game-like and
everyday-action tasks. Each candidate SHALL declare: exact state/action
protocol, legal random executor definition, intelligence-sensitive success
metric, deterministic verifier, leakage plan, estimated 30-50M data/training
fit, expected frontier evaluation cost, an explicit reject condition, whether
its baseline is measured or projected, its public-proof role, and a separately
justified prospect for a 30-50M specialist to beat a larger LLM.

#### Scenario: A candidate is evaluated for selection
- **WHEN** the scorecard is consulted
- **THEN** every candidate has a gradient-likelihood rating, a 30-50M fit
  rating, a reject condition, a leakage plan, and an evidence-qualified
  specialist-versus-larger-LLM prospect
- **AND** the top two non-overlapping candidates are marked as selected

### Requirement: Non-overlapping selected candidates
The two selected candidates for reference environment implementation SHALL
test different reasoning modes (one game-like tactical, one everyday-action
constraint-based) so that a specialist trained on one does not trivially
transfer to the other.

Selection for reference implementation SHALL NOT imply frontier-gate passage,
specialist qualification, or eligibility for a public benchmark claim.

#### Scenario: Two candidates test the same capability
- **WHEN** two selected candidates both test spatial board tactics
- **THEN** the scorecard is rejected
- **AND** a non-overlapping replacement is selected

### Requirement: Dependency-free reference environments
Each selected candidate SHALL have a dependency-free Python reference
environment with seeded reset/step, legal action enumeration, a canonical
trace format, a random-legal baseline executor, and a deterministic verifier.
The environment SHALL be importable and testable without network access, model
loading, GPU, or any third-party package.

#### Scenario: An environment is imported in CI
- **WHEN** the test suite imports the environment module
- **THEN** reset, step, legal actions, random-legal baseline, and verifier
  all execute using only the Python standard library
- **AND** no network call, model load, or GPU operation occurs

### Requirement: Deterministic seeded execution
Every environment SHALL produce identical state sequences and outcomes for
the same seed and action list across runs, platforms, and Python versions.
Seeds SHALL partition training and evaluation instance spaces.

#### Scenario: The same seed is reset twice
- **WHEN** an environment is reset with seed S and stepped through actions A
- **THEN** the resulting state, reward, and termination are byte-identical to
  a second run with the same seed and actions

### Requirement: Mechanically verifiable development probes
Development probes SHALL be included only if every item is verifiable by the
environment's own deterministic verifier. Each probe set SHALL carry
provenance (author, content origin, date, method), be marked development-only, and
create no specialist training labels or frozen evaluation material.

#### Scenario: A probe is not mechanically verifiable
- **WHEN** a development probe cannot be verified by the environment's
  verifier
- **THEN** the probe is rejected and not committed
- **AND** no unverifiable probe enters the repository

### Requirement: No-model infrastructure verification
The repository SHALL provide a no-model test path that validates scorecard
consistency, environment determinism, legal-action correctness, random-legal
baseline behavior, canonical-trace replay, verifier accept/reject, and probe
validation without training, model loading, provider calls, sustained
compute, or deploy.

#### Scenario: CI runs the lab smoke
- **WHEN** only the stdlib Python runtime is available
- **THEN** all environment, scorecard, and probe checks execute locally
- **AND** no network credential, GPU, model runtime, or production surface is
  required

### Requirement: Measured baseline claims cannot drift
Every implemented environment SHALL record a deterministic development cohort,
its exact baseline metric, an accepted calibration range, and whether
unsatisfiable instances exist when the metric includes abstention. CI SHALL
recompute those claims from the environment rather than validating prose only.

#### Scenario: A scorecard understates its random baseline
- **WHEN** the recorded baseline value or accepted band disagrees with the
  deterministic development cohort
- **THEN** the no-model smoke fails before a frontier model is called

### Requirement: Specialist proof is a separate gate
A task that passes `frontier > random` SHALL remain ineligible for a public
claim until a no-more-than-50M specialist is evaluated against the same named
larger LLM on a frozen cohort and materially beats it. Algorithmic solvers MAY
validate mechanics but SHALL NOT be the headline opponent.

#### Scenario: Frontier beats random but specialist evidence is absent
- **WHEN** the frontier capability-gradient gate passes but no qualified
  specialist-versus-larger-LLM result exists
- **THEN** the task remains a frontier-gradient candidate and no specialist win
  or public benchmark admission is reported
