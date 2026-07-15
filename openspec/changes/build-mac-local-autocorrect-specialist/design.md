## Context

The motivating account describes a small encoder-decoder autocorrect model trained on clean text plus simulated keyboard errors, improved by edit-aware loss, and served with beam search and stable-prefix streaming. None of those reported model choices, scores, or implementation details are treated as verified. The future work is a reproduction through the repository's existing factory loop:

```text
target -> data -> post-training -> eval -> package -> report
```

The target user is the owner typing ordinary prose on a Mac. The desired behavior is post-composition repair: accept a complete text span, correct genuine typing errors, preserve intent and style, and run without a network. The current active SQL proof remains ahead of this work.

## Goals / Non-Goals

**Goals:**

- Find the smallest Mac-local model that reaches frontier-parity on a frozen, unambiguous autocorrect eval.
- Improve typo repair without creating an aggressive rewriting or grammar-polishing model.
- Reproduce the four essential bets independently: keyboard-noise data, encoder-decoder/model choice, edit-aware training, and beam decoding with stable streaming.
- Report quality, clean-text regressions, latency, RAM, throughput, energy, training time, and cost in the canonical factory format.

**Non-Goals:**

- Building a keyboard extension, editor UI, OS input method, or cloud service.
- Rewriting tone, grammar, facts, or meaning beyond the minimum edits needed to repair typing errors.
- Assuming any named base model, public dataset, benchmark number, or custom algorithm from the motivating account is correct.
- Training from scratch, full-parameter tuning, distributed training, or unbounded model and hyperparameter sweeps.

## Decisions

### 1. Freeze a narrow text-to-text contract

Version 1 accepts one UTF-8 prose span and returns one corrected UTF-8 span. The output must preserve wording, whitespace, casing, punctuation, named entities, URLs, numbers, and code-like fragments unless a frozen example marks that span as corrupted. No explanations or markup are allowed.

This isolates correction from product integration and makes every candidate comparable. Inline cursor prediction, style rewriting, and app-specific context are separate future changes.

### 2. Treat natural errors as the primary test and simulation as training support

The primary held-out set uses consented or permissively licensed natural typo/correction pairs that are independently reviewed as unambiguous. Synthetic evaluation is a diagnostic slice, not the headline score.

The simulator operates on clean text and emits a corruption trace. Its first version covers adjacent-key substitutions, omissions, insertions, transpositions, repeated keys, space errors, and shift/case errors on a versioned Mac keyboard layout. Error types and rates are configuration, not hard-coded folklore. Clean sources are assigned to splits before corruptions are generated, and all derivatives of a source stay in one split.

Alternatives rejected:

- Synthetic-only evaluation: too easy to overfit to the simulator.
- Random character noise: cheap but physically unlike typing errors.
- Training on private typing logs by default: unnecessary and unsafe for a first proof.

### 3. Select the base by a bounded bake-off

The bake-off compares a small set of pinned, Mac-runnable encoder-decoder or byte/character-aware bases. It measures zero-shot repair quality, tokenizer fragmentation on noisy text, load/RAM, greedy latency, license, MLX feasibility, and adapter-training feasibility. The smallest base that remains plausibly capable advances.

T5Gemma, ByT5, Qwen, Gemma, and Liquid models are candidates only if suitable immutable releases and licenses exist at implementation time. Architecture names in the motivating account do not freeze the choice.

### 4. Stage training so each claimed improvement has an ablation

The first candidate is ordinary supervised LoRA/SFT on noisy-to-clean pairs. It must pass the repository's 1–10 KB repeated-data overfit gate. Only then may the run add an edit-aware objective.

The edit-aware objective uses a deterministic byte-level alignment between noisy source and clean target, then maps target-side edit spans to decoder loss positions. Its exact handling of insertions, deletions, Unicode, and tokenizer offsets must be specified and unit-tested before training. The claim is accepted only if the same frozen candidate recipe improves the targeted missed-edit slices over ordinary sequence loss without increasing overcorrection.

Contrastive learning, DPO, GRPO, dynamic masking, and additional preference stages are excluded until a prior frozen report names a failure they can address.

### 5. Establish greedy decoding before beam search

Greedy decoding is the quality and performance baseline. A bounded beam-search candidate is added only if trace review shows recoverable decoding errors. Beam width, length penalty, maximum output length, and stopping rules are frozen and evaluated as part of the candidate identity.

Stable-prefix streaming may expose only the longest common prefix of all surviving beams after pruning. Emitted text is never retracted, is released only at valid UTF-8/grapheme boundaries, and must equal a prefix of the final selected output. If beam search does not clear both the quality delta and latency/RAM gates, greedy decoding remains the shipped mode.

### 6. Use an honest, calibrated eval

The primary metric is error reduction rate:

```text
1 - edit_distance(candidate, clean) / edit_distance(noisy, clean)
```

The report also includes exact match, residual character error rate, clean-text preservation, unnecessary-edit rate, named-entity/number/URL preservation, meaning-change review, and metrics by natural/synthetic and error-type slice. Confidence intervals are computed over source examples.

Before candidate scoring, the exact frontier comparator must clear a near-ceiling gate on the unambiguous rows; failures are reviewed and ambiguous rows are fixed or dropped without using candidate outputs. Apple autocorrect and the frontier comparator are measured on the same frozen inputs where their interfaces allow it, with any protocol mismatch disclosed. Training data and evaluation sources are searched for exact and normalized overlap, and a lexical holdout slice tests rare or unseen words.

### 7. Ship frontier-parity per unit cost, not a hype claim

The intended result is the smallest artifact that is statistically non-inferior to the calibrated frontier while materially beating the local incumbent. The ship decision requires all frozen quality, regression, local-only, and Mac resource gates. A point estimate above the frontier is reported as such, not as a general claim that a small model outperforms the frontier.

The initial target envelope is at most 2B parameters, at most 4 GB peak inference RSS, at most 50 ms median time to first stable text, and at most 250 ms median end-to-end latency on the frozen short-prose suite. Implementation freezes the exact Mac model, power mode, thermals procedure, text lengths, warmup, and measurement method before results.

### 8. Reuse the canonical factory artifacts

Every attempted candidate produces the existing run folder with frozen config, dataset manifest, baseline and candidate evals, slice metrics, trace review, provenance, performance, report, artifact metadata, and one decision. A specialist package is created only for `ship`. No keyboard/UI integration is bundled with the model proof.

## Risks / Trade-offs

- **Synthetic noise becomes the task** -> Keep natural errors primary, report natural and synthetic slices separately, and randomize only within a frozen simulator family.
- **The model overcorrects valid text** -> Give clean examples their own regression gate and reject gains that increase unnecessary edits or meaning changes.
- **Byte alignment does not map cleanly to token loss** -> Specify the mapping on toy Unicode cases, gradient-check the implementation, and retain ordinary sequence loss as the oracle ablation.
- **Beam search wins accuracy but loses the local experience** -> Gate it on measured end-to-end latency, RSS, and energy; ship greedy if the trade is negative.
- **Comparator protocols are not equivalent** -> Record exact invocation and accessible context, disclose mismatches, and avoid a cross-system superiority claim when parity cannot be established.
- **A 2B model misses the bar** -> Record `park` or propose a separately scoped larger-model run; do not silently enlarge the target or start an open sweep.
- **Private text leaks into artifacts** -> Use public/consented data, store only approved fixtures and aggregates, and keep raw personal text out of committed files.

## Migration Plan

There is no deployed system to migrate. Implementation proceeds as a parked factory run: freeze eval, build tiny fixtures and simulator, run the base bake-off, prove tiny overfit, train one pilot, evaluate, and either stop or package. Rollback is deletion of local ignored run/model artifacts; committed fixtures and planning records remain as evidence.

## Open Questions

- Which current encoder-decoder or byte-aware base is the smallest Mac-runnable candidate with an acceptable license and MLX path?
- Which natural typo dataset can be redistributed or reproducibly fetched while preserving a strict held-out test?
- Can Apple autocorrect be invoked reproducibly on the same full-span protocol, or must it remain a separately labelled observational baseline?
- What energy measurement is stable enough on the target Mac to support a battery claim?
