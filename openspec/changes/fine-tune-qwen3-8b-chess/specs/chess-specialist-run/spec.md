## ADDED Requirements

### Requirement: Frozen chess action protocol
The system SHALL define one versioned chess action protocol before dataset generation or baseline evaluation. Version 1 SHALL provide standard chess FEN, side to move, and optional recent UCI move history as input and SHALL accept exactly one legal UCI move as output. The parser MUST reject commentary, multiple moves, malformed coordinates, moves illegal in the supplied position, and output after the move.

#### Scenario: Legal move is accepted
- **WHEN** the model returns exactly one syntactically valid UCI move that is legal in the supplied FEN
- **THEN** the evaluator records a parsed legal action and applies that move to the board

#### Scenario: Free-form or illegal output is rejected
- **WHEN** the model returns commentary, more than one move, invalid UCI syntax, or a move illegal in the supplied FEN
- **THEN** the evaluator records a parse or legality failure and does not repair the answer for scoring

#### Scenario: Chess960 and variants are excluded
- **WHEN** a row represents Chess960, a chess variant, or a malformed standard-chess position
- **THEN** the data pipeline rejects the row before it enters a split

### Requirement: Exact base and environment freeze
The run SHALL pin the exact Qwen3-8B Hugging Face model identifier, immutable model revision, tokenizer/chat-template revision, precision, quantization format, generation settings, Stockfish version, Stockfish settings, chess-rules-library version, random seeds, and host description before baseline measurement. Changing any frozen field SHALL create a new run identity.

#### Scenario: Reproducible run configuration
- **WHEN** a baseline or candidate evaluation is started
- **THEN** its run configuration contains every frozen model, engine, protocol, seed, and host field

#### Scenario: Frozen field changes
- **WHEN** the operator changes the model revision, prompt template, engine depth or nodes, generation settings, or test data
- **THEN** the system refuses to append results to the old run identity and requires a new run

### Requirement: Licensed and leakage-controlled dataset
The data pipeline SHALL ingest only sources whose redistribution and model-training terms are recorded and approved. It SHALL normalize each example to the frozen protocol, validate the position and target move, deduplicate canonical positions, split by game or generated trajectory before extracting positions, and prevent a canonical position from appearing across train, development, and test splits. Every emitted manifest MUST include source identifiers, licenses, revisions or dates, row counts, filters, split seed, hashes, and Stockfish labelling settings where applicable.

#### Scenario: Source provenance is complete
- **WHEN** a dataset is built
- **THEN** every output row can be traced to an approved source game or a reproducible engine-generation record and the manifest contains hashes and processing settings

#### Scenario: Cross-split position collision
- **WHEN** the same canonical position is found in more than one split
- **THEN** all copies are assigned to one split or removed before the dataset is accepted

#### Scenario: Invalid teacher move
- **WHEN** a source or engine-labelled target move is not legal in its input position
- **THEN** the row is rejected and the rejection count is reported

### Requirement: Coverage of chess decision states
The training and evaluation manifests SHALL report coverage across opening, middlegame, endgame, tactical, quiet, winning, equal, losing, in-check, promotion, castling, and en-passant slices. Training data SHALL include model-reachable recovery positions and suboptimal/adverse states rather than only expert mainline positions.

#### Scenario: Slice coverage report
- **WHEN** a dataset manifest is finalized
- **THEN** it reports row counts for every required chess-state slice and explicitly marks any underfilled slice

#### Scenario: Recovery-state inclusion
- **WHEN** the pilot dataset is accepted for training
- **THEN** it includes legal positions reached after non-teacher moves or sampled lower-quality play, with engine-labelled recovery actions

### Requirement: Baseline-first decision
The exact frozen Qwen3-8B base SHALL be evaluated before adaptation on the complete frozen offline position suite and the smaller baseline match suite. Training SHALL proceed only when the report identifies a material, trainable gap and records why the base is insufficient.

#### Scenario: Base already clears ship bars
- **WHEN** the zero-shot base clears all chess quality, regression, and performance ship bars
- **THEN** the run decision is `reject` or `park` for fine-tuning and no training is performed

#### Scenario: Trainable failure slice exists
- **WHEN** the base misses one or more ship bars and trace review attributes the miss to a failure suitable for post-training
- **THEN** the run may advance to the tiny-overfit gate with the failure slices recorded in the recipe

### Requirement: Staged and gated training recipe
The recipe SHALL use supervised behavior cloning with LoRA or QLoRA as the first adaptation stage. It SHALL pass a 1–10 KB repeated-data overfit gate before a pilot run and pass the pilot's frozen evaluation before a larger run. Preference optimization or verifiable-reward training MAY be added only as a new candidate after SFT results identify a specific remaining failure. Each stage MUST pin data, adapter geometry, optimizer settings, context length, step budget, checkpoint cadence, and stop rules.

#### Scenario: Tiny overfit fails
- **WHEN** training cannot drive loss down and memorize a 1–10 KB repeated legal-move dataset
- **THEN** the system stops before pilot or full training and records `retry-training`

#### Scenario: SFT pilot improves the target
- **WHEN** the SFT pilot improves the frozen target slices without breaching regression or stability limits
- **THEN** the operator may approve a larger SFT run using a separately frozen configuration

#### Scenario: Preference or reward stage is proposed
- **WHEN** SFT leaves a measured move-selection or recovery failure
- **THEN** a new recipe names that failure, its preference or verifiable reward, its data, its gates, and its stop rule before training

### Requirement: Honest 8B quantized training path
An 8B run reported as QLoRA SHALL keep the base in a real packed 4-bit representation during training and SHALL train only adapter parameters. The existing simulated quantize-dequantize `posttrainllm sft --qlora` path MUST NOT be labelled as packed-base QLoRA. The implementation SHALL either prove the native packed-base gradient path or use a pinned `mlx_lm` training environment while keeping posttrainllm's run, eval, and packaging formats.

#### Scenario: Native packed-base path passes feasibility
- **WHEN** one bounded training step on a packed quantized layer produces finite non-zero adapter gradients, leaves base weights frozen, decreases toy-task loss, and stays within the memory guardrail
- **THEN** the native path is eligible for the tiny-overfit gate

#### Scenario: Native packed-base path fails
- **WHEN** gradients, memory, loading parity, or adapter saving fail the bounded feasibility check
- **THEN** native implementation stops and the run either switches to the documented `mlx_lm` fallback or records `park` with the native prerequisite in `blocked_by`, without starting an 8B sweep

#### Scenario: Simulated path is selected
- **WHEN** the only available path materializes or dequantizes the 8B base for training
- **THEN** the system refuses to describe the result as the intended Mac-feasible QLoRA run

### Requirement: Engine-calibrated offline evaluation
The evaluator SHALL validate its ruler before grading the model. The pinned Stockfish reference SHALL produce 100% legal moves and SHALL clear the tactical and move-quality ceiling checks. Candidate evaluation SHALL report legal-move rate, strict parse rate, tactical success, median and p90 centipawn loss with mate-aware handling, blunder rate at a frozen threshold, and every metric by required slice. Engine-equivalent alternatives SHALL receive semantic credit rather than exact-reference penalties.

#### Scenario: Reference engine fails the ceiling gate
- **WHEN** the pinned Stockfish reference fails legality or does not clear the frozen tactical or move-quality ceiling
- **THEN** the affected benchmark is fixed or dropped before any candidate score is reported

#### Scenario: Candidate chooses an equivalent move
- **WHEN** the candidate move differs from a stored principal variation but falls within the frozen engine-equivalence tolerance
- **THEN** the evaluator awards equivalent move-quality credit instead of marking it wrong by string match

#### Scenario: Candidate emits an illegal move
- **WHEN** the candidate move cannot legally be played in the supplied position
- **THEN** legality is scored as failure and centipawn loss is assigned the frozen maximum penalty

### Requirement: Paired game evaluation
The evaluator SHALL run a small smoke match before any full match. The full match SHALL use paired openings with colors reversed, fixed opponent settings, fixed clocks or node budgets, deterministic adjudication rules, and illegal output as an immediate loss. It SHALL report win/draw/loss, score rate, confidence interval, color split, illegal-loss count, and game records.

#### Scenario: Smoke match is unstable
- **WHEN** the candidate crashes, times out, leaks processes, or emits an illegal move above the frozen tolerance in the smoke match
- **THEN** the full match is not started and the run records the failure

#### Scenario: Paired opening is evaluated
- **WHEN** an opening seed enters the full match suite
- **THEN** baseline and candidate are each evaluated from both colors under identical opponent and resource settings

### Requirement: Frozen ship and regression gates
Before training, the run SHALL freeze numeric thresholds. At minimum, a ship decision SHALL require legal-move rate of at least 99.5%, strict parse rate of at least 99.5%, no worse tactical success than baseline and an absolute tactical improvement of at least 5 percentage points when tactics are the targeted gap, at least 15% relative reduction in median centipawn loss, no increase in blunder rate, a higher paired-match score than baseline, and no more than 3 percentage points of loss on the repo's frozen general-language regression gate. Performance SHALL include train time, eval time, peak training RSS, peak inference RSS, prompt/decode throughput, and move latency; candidate inference MUST NOT regress median move latency by more than 20% against the same quantized base under identical settings.

#### Scenario: Chess improves but breadth regresses
- **WHEN** the candidate clears chess gates but loses more than 3 percentage points on the frozen general-language regression gate
- **THEN** the decision is not `ship` and the report records the candidate as routed-only, retryable, or rejected

#### Scenario: Offline metrics improve but games do not
- **WHEN** legality, tactics, and centipawn loss clear their bars but paired-match score is not higher than baseline
- **THEN** the decision is `retry-eval`, `retry-data`, `retry-training`, or `reject`, but not `ship`

#### Scenario: All gates clear
- **WHEN** the candidate clears every frozen quality, regression, stability, and performance threshold
- **THEN** the run may record `ship` and proceed to specialist packaging

### Requirement: Canonical factory artifacts and conditional packaging
Every attempted candidate SHALL emit or assemble the canonical factory run folder with configuration, dataset manifest, logs, baseline and candidate results, slice metrics, trace review, provenance, performance, report, artifact metadata, and decision. A committed specialist package SHALL be created only for a `ship` decision and SHALL document protocol, base revision, adapter, prompt, eval results, performance, routing constraints, and known limitations.

#### Scenario: Candidate does not ship
- **WHEN** the decision is anything other than `ship`
- **THEN** the run report is retained as evidence but no specialist package is created

#### Scenario: Candidate ships
- **WHEN** the decision is `ship` and the factory publish check passes without report-only allowances
- **THEN** the package metadata is created under `specialists/` and points to a resolvable local or published artifact

### Requirement: Heavy-work safety
Model downloads, package installations, compilation, Stockfish labelling sweeps, 8B training, and full match evaluation SHALL require explicit operator approval immediately before execution. The implementation SHALL acquire the repository GPU lock for applicable work, start with the smallest bounded check, record spawned processes, and terminate every process it starts.

#### Scenario: Approval is absent
- **WHEN** a task would begin a heavy or long-running operation without explicit operator approval
- **THEN** execution pauses after preparing the exact command, expected duration, storage, memory, and rollback or cleanup plan

#### Scenario: Approved operation completes or fails
- **WHEN** an approved engine, model, training, or evaluation process exits
- **THEN** its result is recorded and all child or background processes started by the task are verified stopped
