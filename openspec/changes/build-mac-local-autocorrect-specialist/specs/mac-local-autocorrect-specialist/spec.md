## ADDED Requirements

### Requirement: Minimal correction contract
The system SHALL define a versioned text-to-text contract that accepts one UTF-8 prose span and returns only its minimally corrected UTF-8 text. It MUST preserve intended wording, order, whitespace, casing, punctuation, names, numbers, URLs, and code-like spans except where the frozen example identifies a typing error, and it MUST NOT emit explanations or markup.

#### Scenario: Typing errors are repaired
- **WHEN** an input contains one or more unambiguous typing errors represented by the supported error taxonomy
- **THEN** the output repairs those errors and otherwise matches the intended clean text

#### Scenario: Valid text is preserved
- **WHEN** an input is already correct
- **THEN** the output is byte-for-byte identical to the input

#### Scenario: Rewriting is rejected
- **WHEN** an output changes valid wording, tone, facts, formatting, or protected spans beyond the required typo repair
- **THEN** the evaluator records an unnecessary edit or meaning-preservation failure

### Requirement: Local-only execution
The packaged correction path SHALL load and run without network access and SHALL NOT transmit or persist input text outside the operator-selected local process and artifact paths. Any remote model used for dataset review or frontier calibration MUST be outside the shipped correction path and MUST use only approved evaluation text.

#### Scenario: Network is unavailable
- **WHEN** the shipped specialist is loaded and evaluated with network access disabled
- **THEN** correction succeeds with the same model behavior as the connected run

#### Scenario: Remote calibration is used
- **WHEN** a remote frontier model grades or corrects evaluation examples
- **THEN** the run records the exact approved inputs, backend, model revision, command, date, and cost separately from local inference

### Requirement: Provenance-safe paired data
The data pipeline SHALL use only clean-text and natural-correction sources with recorded training and redistribution terms. It MUST assign source documents to train, development, and test splits before corruption or augmentation; keep every derivative of a source in one split; reject exact and normalized cross-split overlap; and emit source, license, revision, processing, count, rejection, seed, and content-hash metadata.

#### Scenario: Dataset is reproduced
- **WHEN** the same source revisions, configuration, and seed are supplied
- **THEN** the pipeline emits identical manifests, splits, corruption traces, and hashes

#### Scenario: Source-derived leakage is found
- **WHEN** clean or corrupted derivatives of the same source appear in more than one split
- **THEN** the dataset validator rejects the manifest before baseline evaluation or training

#### Scenario: Training terms are unknown
- **WHEN** a source lacks recorded permission for the intended training or redistribution use
- **THEN** the pipeline excludes that source and reports the rejected row count

### Requirement: Versioned Mac-keyboard corruption simulator
The system SHALL provide a deterministic, configurable corruption simulator for a versioned Mac keyboard layout. It MUST support adjacent-key substitution, insertion, omission, transposition, repeated-key, space, and shift/case errors; emit the applied edit trace; allow each error family to be enabled and weighted independently; and leave the clean source recoverable for scoring.

#### Scenario: Seeded corruption is repeated
- **WHEN** the same clean row, layout, corruption configuration, and seed are used
- **THEN** the simulator emits the same noisy row and edit trace

#### Scenario: Error family is disabled
- **WHEN** a corruption family has zero configured probability
- **THEN** the simulator emits no edit from that family and reports zero occurrences for it

#### Scenario: Clean control is requested
- **WHEN** the configured example is a no-corruption control
- **THEN** noisy and clean text are identical and the edit trace is empty

### Requirement: Bounded base selection
Before training, the run SHALL compare a bounded set of pinned Mac-runnable bases on zero-shot correction quality, tokenizer or byte fragmentation, license, artifact size, MLX load and adapter feasibility, greedy latency, and peak RSS. It MUST select the smallest plausibly capable base or record `park` when no candidate satisfies the feasibility envelope.

#### Scenario: Smaller base is viable
- **WHEN** multiple candidates satisfy the frozen feasibility criteria
- **THEN** the run selects the smallest candidate for the first tiny-overfit and pilot stages

#### Scenario: Named model is unavailable
- **WHEN** a model mentioned in prior notes lacks a suitable immutable release, acceptable license, or working Mac path
- **THEN** the bake-off excludes it without changing the task or inventing an equivalent result

### Requirement: Staged and ablated training recipe
The first trained candidate SHALL use ordinary supervised noisy-to-clean sequence training with adapters and SHALL pass the repository's 1-10 KB repeated-data overfit gate before a pilot. An edit-aware objective MAY advance only after the ordinary-loss baseline is frozen and the report identifies copy bias or missed-edit slices. Every candidate MUST pin its model revision, data, adapter geometry, optimizer settings, precision, seed, step budget, checkpoint cadence, eval gate, and stop rule.

#### Scenario: Tiny overfit fails
- **WHEN** a candidate cannot memorize the repeated tiny correction dataset with finite stable loss
- **THEN** the run stops before pilot training and records `retry-training`

#### Scenario: Ordinary loss is sufficient
- **WHEN** ordinary supervised training clears every frozen quality and regression bar
- **THEN** the run does not add a custom loss solely because it appeared in the motivating account

#### Scenario: Additional method is proposed
- **WHEN** edit-aware loss, contrastive learning, preference optimization, or reinforcement learning is proposed
- **THEN** a recipe names the measured failure, training signal, data, ablation, eval slice, and stop rule before execution

### Requirement: Correct edit-aware objective
If implemented, the edit-aware objective SHALL compute a deterministic minimum byte-edit alignment between noisy source and clean target, map target-side edit spans to decoder loss positions, and weight configured edit positions independently from copied positions. It MUST define insertion, deletion, substitution, transposition, Unicode normalization, tokenizer-offset, padding, and end-of-sequence behavior and MUST match an unweighted sequence-loss oracle when all weights equal one.

#### Scenario: Toy alignments are checked
- **WHEN** the objective is evaluated on committed ASCII, emoji, composed/decomposed Unicode, whitespace, insertion, deletion, substitution, and transposition fixtures
- **THEN** the alignment, token mapping, per-position weights, scalar loss, and gradients match the frozen expected values

#### Scenario: Edit weighting does not help
- **WHEN** the edit-aware candidate fails to improve the targeted frozen slice over the ordinary-loss candidate or increases unnecessary edits beyond the regression bar
- **THEN** the run rejects the objective for that recipe and retains the simpler candidate

### Requirement: Gated beam decoding and stable-prefix streaming
The evaluator SHALL measure greedy decoding first. A beam-search candidate MUST freeze beam width, length penalty, output limit, stopping rules, and score calculation and MUST beat greedy decoding on the frozen quality gate without breaching latency, RSS, or energy limits. Stable-prefix streaming SHALL emit only the longest common prefix of all surviving post-pruning beams, at valid UTF-8 and grapheme boundaries, and emitted text MUST never be retracted.

#### Scenario: Beam search has no useful tradeoff
- **WHEN** beam search fails its quality delta or performance gates
- **THEN** greedy decoding remains the accepted mode

#### Scenario: Stable text is emitted
- **WHEN** all surviving beams share a longer prefix after a search step
- **THEN** the newly shared complete-grapheme suffix is emitted once and remains a prefix of the final selected output

#### Scenario: Beams disagree
- **WHEN** surviving beams do not share text beyond the already emitted prefix
- **THEN** the streamer emits nothing and does not guess or retract text

### Requirement: Frozen and calibrated evaluation
The complete evaluation SHALL be frozen before training and SHALL keep natural held-out errors as the primary slice. It MUST include synthetic error families, clean text, rare or lexically held-out words, names, numbers, URLs, punctuation, casing, and length slices. Before small-model scores are reported, the pinned frontier comparator MUST reach the frozen near-ceiling threshold on reviewed unambiguous rows; ambiguous or broken rows MUST be fixed or dropped without consulting candidate outputs.

#### Scenario: Frontier misses an example
- **WHEN** the frontier comparator fails a purportedly unambiguous row
- **THEN** reviewers determine whether the row or ruler is broken and fix or remove it before candidate results are unblinded

#### Scenario: Candidate score is computed
- **WHEN** a frozen candidate is evaluated
- **THEN** the report includes error reduction rate, exact match, residual character error, clean-text preservation, unnecessary-edit rate, protected-span preservation, meaning-change review, confidence intervals, and every required slice

#### Scenario: Benchmark overlap is detected
- **WHEN** an evaluation source or normalized target overlaps training data
- **THEN** the affected rows are excluded or the run is invalidated and the overlap is reported

### Requirement: Frozen ship and Mac performance gates
Before training, the run SHALL freeze numeric quality, regression, and resource thresholds. A `ship` decision MUST require at least 90% natural-error reduction; a 95% confidence-interval lower bound of at least negative two percentage points for the candidate-minus-frontier error-reduction difference; a frozen minimum improvement over the measured local incumbent; at least 99.5% byte-exact preservation on clean text; at least 99.5% preservation of uncorrupted names, numbers, and URLs; and no unresolved meaning-change failures in the reviewed high-risk slice. The first target envelope SHALL be no more than 2B parameters, 4 GB peak inference RSS, 50 ms median time to first stable text, and 250 ms median end-to-end latency on the frozen short-prose suite.

#### Scenario: Point estimate narrowly beats frontier
- **WHEN** the candidate's point estimate exceeds the frontier but its confidence interval does not establish the frozen comparison criterion
- **THEN** the report states the measured estimate and uncertainty without claiming general frontier superiority

#### Scenario: Quality clears but regressions fail
- **WHEN** error reduction clears its bar but clean-text, protected-span, meaning, or performance gates fail
- **THEN** the decision is not `ship`

#### Scenario: All gates clear
- **WHEN** the candidate clears every frozen quality, regression, local-only, reproducibility, and Mac resource gate
- **THEN** the run may record `ship` and proceed to specialist packaging

### Requirement: Canonical evidence, conditional packaging, and heavy-work safety
Every attempted candidate SHALL emit or assemble the canonical factory run with configuration, dataset manifest, training log, baseline and candidate evals, slice metrics, trace review, provenance, performance, artifact metadata, report, and exactly one allowed decision. A committed specialist package SHALL be created only after `ship`. Downloads, dependency installation, compilation, training, and sustained model or energy benchmarks MUST require explicit operator approval immediately before execution and MUST follow the repository GPU-lock and process-cleanup rules.

#### Scenario: Candidate does not ship
- **WHEN** the decision is `reject`, `retry-data`, `retry-training`, `retry-eval`, or `park`
- **THEN** the run evidence is retained but no specialist package is created

#### Scenario: Heavy operation lacks approval
- **WHEN** an implementation task reaches a model download, installation, compilation, training, or sustained benchmark without immediate operator approval
- **THEN** it stops after presenting the exact command, expected time, disk/RAM impact, and cleanup plan

#### Scenario: Candidate ships
- **WHEN** every gate passes and the factory publish check succeeds without report-only allowances
- **THEN** the package records the base and adapter revisions, correction contract, tokenizer assumptions, decoding mode, evals, performance, routing limits, and resolvable artifact path
