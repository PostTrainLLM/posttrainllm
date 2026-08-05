# 2048-policy-evaluation Specification

## Purpose
Measure 2048 policy quality and decision cost on identical seeded games so a
30–50M specialist LLM can be compared fairly with frozen larger general LLMs.
Algorithmic policies provide diagnostics, not the capability opponent.
## Requirements
### Requirement: Common policy boundary
Every evaluated language model SHALL receive the same versioned character
serialization of the board, score, move count, and legal-action set and SHALL
return exactly one action character within the declared per-move budget. The
model path SHALL NOT accept screenshots, pixels, OCR, or vision features.

#### Scenario: A visual adapter is proposed
- **WHEN** an adapter supplies either model with an image or learned visual representation
- **THEN** validation rejects it as outside the character-policy benchmark

#### Scenario: Candidate emits an illegal action
- **WHEN** a candidate returns an unknown, malformed, timed-out, or currently illegal action
- **THEN** the harness records an invalid decision without silently substituting a legal move

### Requirement: Reproducible diagnostic cohort
The harness SHALL include seeded random, immediate-gain greedy, and bounded-search
diagnostics on the same environment revision. Their actions SHALL NOT provide
training labels or determine whether a language-model specialist passes.

#### Scenario: Compare two agents
- **WHEN** two entries are included in one result cohort
- **THEN** their quality differences are computed from paired games sharing the same seed set and environment contract

### Requirement: Separate compliance and planning tracks
Every language-model entry SHALL report a strict raw-action track. The harness
MAY additionally report a legal-action-constrained track that restricts the
model's next-token choice to the currently legal action characters. The
constrained track SHALL be labeled diagnostic, SHALL preserve the model's
selected legal action, and SHALL NOT replace or repair the strict result.

#### Scenario: Strict model chooses a no-op direction
- **WHEN** the raw model output parses as an action that is not currently legal
- **THEN** the strict track records the invalid decision and the constrained track, if enabled, remains a separate result

#### Scenario: Visitor compares planning quality
- **WHEN** both strict and legal-action-constrained results exist
- **THEN** the report explains that strict measures protocol compliance plus planning while constrained isolates planning among legal actions

### Requirement: Complete quality measurements
Each result SHALL report per-game and aggregate score, maximum tile, 2048 reach
rate, legal-move rate, move count, terminal completion rate, and deterministic
uncertainty summaries across seeds.

#### Scenario: Agent never reaches 2048
- **WHEN** an evaluated agent completes the seed suite without producing a 2048 tile
- **THEN** the report records a measured zero reach rate while preserving its score and maximum-tile distribution

### Requirement: Complete performance measurements
Each result SHALL report warm per-decision p50 and p95 latency, decisions per
second, total evaluation wall time, and the hardware/runtime identity. Model
load time SHALL be reported separately when a model is used.

#### Scenario: Compare two language models
- **WHEN** the larger LLM and specialist are evaluated
- **THEN** the report distinguishes one-time loading from repeated decisions and includes model size, RAM, latency, throughput, and cost for both

### Requirement: Frozen larger-LLM opponent
Before trajectory generation or tuning, the experiment SHALL freeze the larger
model identity/revision, prompt, observation serialization, action parser,
decoding settings, context policy, and per-move limit. The larger LLM and small
specialist SHALL receive the same visible board and legal-action set. Neither
model may use tools, code execution, search, rollouts, lookahead, hidden RNG
state, or an algorithmic action selector.

#### Scenario: Larger LLM requests an agentic advantage
- **WHEN** an opponent configuration enables a tool, search procedure, code execution, hidden state, or external memory unavailable to the specialist
- **THEN** validation rejects the comparison before evaluation

#### Scenario: Cloud configuration uses a mutable alias
- **WHEN** a cloud entry identifies only an alias such as `sonnet`, `opus`, or a rolling model name
- **THEN** it may run as a development smoke but validation rejects it as a frozen benchmark opponent until the resolved immutable model identity is recorded

### Requirement: Larger-LLM-only supervision
Training trajectories MAY use decisions from the frozen larger LLM on the
trajectory-training namespace. They SHALL identify the model, prompt, adapter,
and decoding revisions. Algorithmic diagnostic actions and frozen-evaluation
states SHALL NOT enter the specialist dataset.

#### Scenario: Algorithmic action enters training data
- **WHEN** a trajectory identifies random, greedy, expectimax, or another non-LLM policy as its action source
- **THEN** data validation rejects the trajectory

### Requirement: Explicit proof gate
The first specialist proof SHALL require the candidate to contain no more than
50,000,000 parameters, be smaller than the larger-LLM opponent, make zero
invalid decisions on the strict track, achieve a positive paired mean
score delta, win more than half of paired games, and have a positive lower bound
on the paired score-delta confidence interval. Any unmet condition SHALL produce
a retry or reject outcome. Algorithmic diagnostic scores SHALL NOT affect this
decision.

#### Scenario: Candidate is efficient but weak
- **WHEN** a smaller candidate is faster or cheaper but does not beat the larger LLM on the capability thresholds
- **THEN** the experiment reports the candidate as not passing the proof gate

#### Scenario: Candidate passes the proof
- **WHEN** a smaller candidate satisfies every paired capability and legality threshold on the frozen suite
- **THEN** the experiment may report that the small specialist beat the named larger LLM, with efficiency measurements and limitations disclosed

#### Scenario: Candidate exceeds the size ceiling
- **WHEN** a candidate contains more than 50,000,000 parameters
- **THEN** it is ineligible for the specialist proof regardless of score, latency, or cost

### Requirement: Frontier benchmark-admission gate
The project SHALL NOT generate a specialist training run unless at least one
pinned frontier cloud model makes zero invalid decisions on the strict track
and beats `random-legal` on the legal-action-constrained paired suite with both
a positive mean score delta, at least a 60% paired win rate, at least a 1.10x
mean-score ratio, and a positive confidence-interval lower bound over 30 seeds.
Failure SHALL park or redesign the benchmark rather than manufacture an easy
specialist win against incapable general models.

#### Scenario: Local 8–9B model loses but frontier passes
- **WHEN** the local general model scores below `random-legal` but a pinned frontier model passes every admission threshold
- **THEN** the benchmark may proceed because it measures capability compression from frontier to the 30–50M specialist

#### Scenario: Frontier cannot beat random legal play
- **WHEN** no pinned frontier model passes the constrained paired random baseline
- **THEN** training remains blocked and the result is reported as a benchmark-calibration failure

### Requirement: Baseline-first execution
The environment and no-model baseline checks SHALL be validatable without model
loading or training, while any sustained benchmark sweep or training run SHALL
remain an explicit operator-approved action.

#### Scenario: Run lightweight verification
- **WHEN** repository tests validate transitions, determinism, record schemas, and a tiny baseline fixture
- **THEN** they complete without network access, model loading, GPU training, or a long seed sweep

### Requirement: Stable candidate adapter
The evaluator SHALL accept future policy candidates through a versioned adapter
without changing frozen seeds, environment rules, baseline definitions, or
scoring semantics.

#### Scenario: Add a tiny trained policy
- **WHEN** a 30–50M four-action specialist is ready for evaluation
- **THEN** it can join the existing cohort through the adapter while all other benchmark inputs and measurements remain unchanged

### Requirement: Reproducible prerecorded benchmark gallery
The site SHALL list admitted benchmarks and provide a detail surface containing
the versioned protocol, exact model identities, prerecorded per-decision inputs
and outputs, an interactive replay, limitations, and a runnable local command.
Development pilots SHALL be visually and semantically distinct from frozen
benchmark evidence. A missing specialist result SHALL render as pending rather
than being synthesized or omitted.

#### Scenario: Visitor inspects a prerecorded game
- **WHEN** the visitor selects a measured model and seed
- **THEN** the replay shows each character input, raw model output, parsed action, board transition, score, legality, terminal reason, and trace identity

#### Scenario: Specialist has not been trained
- **WHEN** no qualified custom SLM artifact exists
- **THEN** the comparison table shows an explicit awaiting-candidate state and makes no specialist win claim
