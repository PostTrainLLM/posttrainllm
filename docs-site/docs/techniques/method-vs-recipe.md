---
title: "Method vs Recipe"
description: "posttrainllm should not confuse having a method on the roadmap with having a recipe"
---

# Method vs Recipe

posttrainllm should not confuse having a method on the roadmap with having a recipe
that is likely to work.

## Method

A method is a general capability or algorithm.

Examples:

- SFT
- DPO / SimPO / ORPO / KTO
- GRPO / RLVR / ReST
- LoRA / DoRA / QLoRA
- constrained decoding
- routing
- eval harness
- failure taxonomy

Methods are necessary, but they are not enough. A method does not say when to
use it, what data shape it needs, which failure it is meant to fix, or how to
tell if it worked.

## Recipe

A recipe is a task-specific application of a method.

A good recipe says:

- target
- method
- data source and split
- reward or label signal
- model/base/adapter configuration
- hyperparameter range
- eval gate
- slice metrics
- known failure mode it is meant to address
- stop rule

Examples:

| Weak method-level plan | Strong recipe-level plan |
|---|---|
| Try DPO. | On `qwen06-sql-expanded`, run reference-anchored DPO on the 108 SQL hygiene pairs at lower LR than the failed SimPO run, then evaluate composed with the SFT adapter on the frozen 50-row synthetic execution gate and clean-SQL raw-output gate. |
| Try RLVR. | Build 4-6 SQL candidates per prompt, score each by execution or gold equivalence, train/evaluate the model on selecting the best candidate before returning to open generation. |
| Try LoRA rank changes. | On the same frozen SQL data, sweep rank `{1,2,4,8}` with fixed steps/LR/seed, report slice metrics, then inspect effective-update geometry before deciding whether more rank helped. |
| Add evals. | Block reporting unless the run has baseline, candidate, slice metrics, trace review, performance, and a `ship/retry/reject` decision. |

## Why It Matters

The SQL hygiene run proves the difference. The method "preference tuning" was
available and on-roadmap. The recipe used ref-free SimPO on 108 short pairs for
200 steps. That recipe collapsed generation:

```text
synthetic execution: 0.860 -> 0.080
clean-SQL raw rate: 0.000 -> 0.000
```

The method was not disproved. The recipe failed.

## Required Recipe Card

Before a new post-training run, write or update a card with this shape:

```markdown
## <recipe name>

- Target:
- Method:
- Failure mode addressed:
- Data:
- Baseline:
- Candidate:
- Eval gate:
- Slice gates:
- Performance fields:
- Stop rule:
- Prior evidence:
- Result:
```

If the card cannot name the failure mode and eval gate, the run is not ready.

