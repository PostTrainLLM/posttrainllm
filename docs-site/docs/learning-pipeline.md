---
title: "Learning Pipeline"
description: "The owner's learning track is now explicitly ground-up. It still reinforces the"
---

# Learning Pipeline

The owner's learning track is now explicitly ground-up. It still reinforces the
posttrainllm factory, but it does not start with post-training jargon.

Primary path:

```text
math intuition -> tiny neural net -> training loop -> transformer
-> LLM behavior -> post-training -> evals -> self-improving factory
```

Learning is not separate from building; every module should eventually make the
next run better.

Progress is tracked in [`learning-progress.md`](learning-progress.md).

## Principle

```text
concept -> toy implementation -> posttrainllm anchor -> recipe improvement
```

If a learning topic does not improve target selection, data, post-training,
eval, packaging, or reporting, park it until it does.

## Ground-Up Master Roadmap

The canonical roadmap is [`docs/learn/curriculum.md`](learn/curriculum.md).

It defines the 10-module path:

1. functions, data, parameters
2. loss and gradient descent
3. vectors, matrices, tensors
4. non-linear neural nets and backprop
5. ML paradigms and scaling
6. tokenization, embeddings, language modeling
7. attention and transformer blocks
8. training mechanics
9. post-training: SFT, LoRA, preference tuning
10. evals, rewards, and self-improvement

The SQL factory is the lab, not the starting point. Do not skip the foundation
unless the module mastery gate can be passed out loud.

All ten modules now have a polished session. For the guarantee that every
shipped subsystem (post-training internals, quantization, serving,
interpretability, WASM/WebGPU, VLM, the factory loop) also has a learning
anchor, see [`docs/learn/coverage-map.md`](learn/coverage-map.md).

## Factory-Attached Learning Sequence

| Order | Topic | Why Now | Project Work It Unlocks | Primary Docs |
|---:|---|---|---|---|
| 1 | Eval design | Bad evals create fake progress | frozen gates, slice metrics, leakage checks, regression gates | [`docs/factory/eval-protocol.md`](factory/eval-protocol.md), [`docs/learn/eval-methodology-2026-06-08.md`](learn/eval-methodology-2026-06-08.md) |
| 2 | Data for post-training | Most improvement is data/reward shape, not optimizer novelty | SFT rows, preference pairs, candidate sets, synthetic data, trace-to-data | [`docs/factory/post-training-factory.md`](factory/post-training-factory.md), [`docs/recipes/from-traces.md`](recipes/from-traces.md) |
| 3 | SFT + LoRA mechanics | Current SQL wins came from SFT/LoRA; failures need adapter diagnosis | rank/layer sweeps, LoRA geometry, overfit checks | [`docs/training/sft.md`](training/sft.md), [`docs/lora_guide.md`](lora_guide.md), [`docs/factory/lora-geometry.md`](factory/lora-geometry.md) |
| 4 | Preference tuning | Hygiene SimPO collapsed; need to understand why | reference-anchored DPO retry, length-balanced negatives, KL/reference anchoring | [`docs/training/dpo.md`](training/dpo.md), [`docs/techniques/method-vs-recipe.md`](techniques/method-vs-recipe.md) |
| 5 | Verifiable rewards | SQL/tool-calling improvement needs executable rewards | SQL execution reward, BFCL AST reward, unit-test rewards | [`docs/techniques/sql-technique-backlog.md`](techniques/sql-technique-backlog.md), [`docs/learn/tool-calling-frontier-parity.md`](learn/tool-calling-frontier-parity.md) |
| 6 | RLVR / ReST / OAPL | Only useful after reward surfaces are clean | batch rollouts, offline scoring, policy lag, candidate selection | [`docs/factory/batch-posttraining.md`](factory/batch-posttraining.md), [`docs/learn/advanced-llm-training.md`](learn/advanced-llm-training.md) |
| 7 | Failure analysis | Failed runs must become data | trace review, failure taxonomy, targeted retry data | [`docs/factory/reports.md`](factory/reports.md), [`docs/attempt-ledger.md`](attempt-ledger.md) |
| 8 | Public reporting | Public artifacts are a product surface | case-study reports, blockers, competition comparison, reproduction notes | [`docs/factory/case-study-template.md`](factory/case-study-template.md), [`docs/factory/public-artifacts.md`](factory/public-artifacts.md) |

## Current Practical Curriculum

This is the project lab sequence. It should run alongside the ground-up path,
not replace it.

### Module 1 — SQL Eval Quality

Goal: know when a SQL improvement claim is real.

Do:

- Read the SQL attempt ledger.
- Compare exact match vs execution accuracy.
- Study why public b-mc2 exact is not enough.
- Build or run the Spider/BIRD-style execution gate when DBs are local.

Deliverable:

- A short note in the next SQL report explaining which metric is trusted and
  which metric is only directional.

### Module 2 — Candidate Selection

Goal: understand why "choose the best answer" can be easier than open
generation.

Do:

- Read `docs/techniques/trainloop-teardown.md`.
- Inspect `scripts/build_sql_candidate_choice.py`.
- Generate candidate-choice rows from existing SQL predictions.
- Train/eval a small candidate-selection adapter only after the recipe card is
  written.

Deliverable:

- Candidate-selection accuracy overall and by slice.

### Module 3 — Preference Tuning Failure

Goal: explain the failed hygiene SimPO run without hand-waving.

Do:

- Read the hygiene run report.
- Compare ref-free SimPO vs reference-anchored DPO.
- Inspect degenerate predictions and trace review.
- Define a safer retry recipe.

Deliverable:

- A recipe card that predicts how the retry avoids collapse.

### Module 4 — Adapter Geometry

Goal: see whether adapter failures are capacity, targeting, or optimization
problems.

Do:

- Run `scripts/lora_geometry.py` on successful and failed SQL adapters.
- Compare rank, stable rank, Frobenius norm, and top modules.
- Attach `lora-geometry.json` to the next run.

Deliverable:

- One paragraph in the report explaining whether the adapter update looked
  concentrated, diffuse, too small, or too large.

## Learning Is Complete For A Topic When

- the concept is explained in owner-readable language,
- the explanation points to repo evidence,
- it changes a recipe, eval, or report,
- and the next run can verify whether that change mattered.
