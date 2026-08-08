# specialist-capability-graph Specification

## Purpose
TBD - created by archiving change add-specialist-capability-graph. Update Purpose after archive.
## Requirements
### Requirement: Additive versioned capability graph
The system SHALL define a versioned capability graph that references existing
specialist package ids while preserving `specialists/registry.json` as artifact
identity and package-evidence authority for graph-aware and graph-unaware
consumers.

#### Scenario: A current package is not in a graph
- **WHEN** a consumer reads the flat specialist registry without graph support
- **THEN** the package remains valid and unchanged
- **AND** absence from a capability graph does not rewrite its package status

### Requirement: Typed nodes and relationships
Every graph node SHALL have a stable id, declared kind, capability and schema
boundary, evidence-backed operating envelope, privacy/network class, resource
metadata, known failures, prohibited uses, verifier policy, and terminal or
fallback behavior, and every relationship SHALL use a recognized typed edge.

#### Scenario: A specialist node references a package
- **WHEN** the graph is validated
- **THEN** the package id resolves in the flat registry
- **AND** the graph references rather than copies its model card, eval report,
  and artifact lock authority

### Requirement: Fail-closed graph validation
The validator SHALL reject duplicate or dangling ids, incompatible schemas,
executable cycles, missing safe terminal behavior, unverified generative
acceptance, unsupported measurement claims, and credential or prohibited
private-payload content.

#### Scenario: Fallback edges form a cycle
- **WHEN** graph validation visits the executable fallback subgraph
- **THEN** validation fails with the bounded cycle path
- **AND** no runtime or benchmark adapter may execute the graph

#### Scenario: External credentials appear in graph data
- **WHEN** a key, token, secret, or credential-shaped field is detected
- **THEN** validation fails
- **AND** the sensitive value is not echoed in public diagnostics

### Requirement: Deterministic eligibility and selection
For the same validated graph, request metadata, installed-state snapshot,
policy, resource measurements, and router output, dry-run and execution SHALL
produce the same eligible set, exclusions, ordered first choice, and fallback
path.

#### Scenario: The smallest node is outside its operating envelope
- **WHEN** its capability, OOD, quality-floor, privacy, schema, or resource gate
  fails
- **THEN** it is excluded with a typed reason
- **AND** selection considers the next eligible node rather than silently
  lowering the policy floor

### Requirement: Verified result acceptance
A generative node result SHALL be returned only after its declared structural,
executable/final-state, or separately calibrated learned-verifier acceptance
policy passes; model self-confidence alone MUST NOT establish acceptance.

#### Scenario: The leaf is confident but the verifier rejects it
- **WHEN** the result fails the declared verifier
- **THEN** the result is recorded as rejected and is not returned
- **AND** the executor follows the next allowed fallback or returns typed safe
  failure

### Requirement: Bounded multi-tier escalation
The V1 executor SHALL attempt one selected node and an ordered fallback chain,
subject to configured hop, latency, resident-memory, energy when available, and
external-call/cost budgets.

#### Scenario: A leaf times out and a broader local node passes
- **WHEN** the leaf exceeds its timeout and policy permits another hop
- **THEN** the trace records `node-timeout`, the broader node is attempted, and
  its verified result may be returned

#### Scenario: Every attempted result is rejected
- **WHEN** the chain or budget is exhausted without acceptance
- **THEN** the executor returns a typed `no-accepted-result` or budget failure
- **AND** it never returns the last rejected answer

### Requirement: Explicit external authorization
An external fallback SHALL remain disabled unless the execution policy
explicitly permits network/external use and existing runtime authorization is
available outside the graph; graph files SHALL contain no credential.

#### Scenario: Local fallbacks fail under a local-only policy
- **WHEN** an external node is next but network use is not authorized
- **THEN** the executor records `network-not-authorized`
- **AND** it returns or continues to a safe local terminal without making an
  external call

### Requirement: Privacy-safe cascade traces
Every dry-run and execution SHALL emit a bounded trace with graph/policy
revision, capability/schema metadata, candidates and exclusions, selected
nodes, route confidence, load state, verifier outcomes, escalation reasons,
resource/cost evidence, and terminal outcome, while redacting request and output
content by default.

#### Scenario: A trace is prepared for public benchmark evidence
- **WHEN** publication policy does not allow raw prompts or outputs
- **THEN** the trace contains hashes and aggregates only
- **AND** no private request, tool result, credential, or raw model response is
  present

### Requirement: Honest model residency accounting
The system SHALL distinguish active parameters, per-request loaded bytes, peak
resident bytes, total installed artifact bytes, shared-base bytes,
task-specific adapter bytes, and cold versus warm end-to-end latency with
explicit measurement state.

#### Scenario: Two specialists share a resident base
- **WHEN** an adapter is selected for a base already resident
- **THEN** base bytes are not double-counted as task-specific installed or
  loaded adapter bytes
- **AND** peak residency and active parameters still reflect the actual request

### Requirement: Bounded residency policy
The runtime SHALL use a declared bounded residency policy and MAY prefer a
resident node only within an explicit quality tolerance; residency MUST NOT
override hard capability, privacy, verification, or quality-floor constraints.

#### Scenario: The resident node is cheaper but below the quality floor
- **WHEN** a non-resident node is the only eligible node meeting policy
- **THEN** the runtime selects or reports the non-resident node and its cold-load
  cost
- **AND** it does not route to the resident node solely to avoid loading

### Requirement: Everyday benchmark system integration
The graph executor SHALL expose a benchmark adapter that binds the graph and
policy revisions to task outcomes and reports route regret, false acceptance,
escalation precision/recall, over-escalation, hops, final tier, cold/warm
end-to-end latency, residency, active parameters, installed bytes, and external
calls/cost.

#### Scenario: Individual leaves have strong scores but the router fails
- **WHEN** end-to-end task success or false acceptance misses the system gate
- **THEN** the graph result fails or remains unqualified regardless of per-leaf
  benchmark scores

### Requirement: Lightweight infrastructure verification
The repository SHALL provide schema, validator, dry-run, policy, verifier,
cascade, privacy, resource-accounting, and benchmark-adapter tests using mock
nodes without model loading, training, sustained compute, provider calls, or
deployment.

#### Scenario: The no-model cascade smoke runs
- **WHEN** deterministic fixture nodes simulate acceptance, rejection, timeout,
  load failure, and exhaustion
- **THEN** every route and terminal result matches the declared graph and policy
- **AND** no model artifact or network authorization is required
