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

## Before Freezing: Check History By Shape

`Prior evidence:` above is the anti-repeat field, and filling it from memory is
how repeats happen. Query the ledger by the *shape* of what you are about to
try, not by reading it chronologically:

```bash
python3 scripts/query_attempts.py --method dpo --objective output-format
python3 scripts/query_attempts.py --base qwen3-0.6b --failures-only
python3 scripts/query_attempts.py --lineage <attempt-id>   # what this extends
python3 scripts/query_attempts.py --streaks                # axes that stopped paying
```

`docs/attempts.json` carries `methods`, `bases`, `objective`, `data_rows`, and
`varied_from` for every model attempt, so the question "has anything shaped like
this been tried?" is a query rather than a re-read. `--lineage` walks the
`varied_from` chain and is the fastest way to see that three prior attempts
already varied the axis you were about to vary a fourth time.

Two consecutive trailing failures on an objective print `CAUTION`; three print
`STOP AND RETHINK`. That is not a veto -- it is the point at which the next
attempt needs to change *axis*, not pressure. The SQL output-format lane hit
three and the honest conclusion was that preference tuning was the wrong tool.

A recipe with a `shape` block gets this lookup automatically at validate time —
see `scripts/autocorrect_adapter.py::print_prior_attempts` for the pattern.

## Closing An Attempt: Triage The Lesson

Writing the lesson down is not what prevents the repeat. When you close an
attempt, put its lesson in one of two places:

1. **Mechanizable → write a check.** Anything comparing two recorded numbers,
   validating a fixture, or asserting a threshold is satisfiable belongs in a
   guard script. Both defects that ended the autocorrect lane were visible in
   committed files at freeze time; nobody ran the comparison. They are now
   `scripts/autocorrect_adapter.py::check_recipe_defects`, and they fail the
   recipe before any training starts.
2. **Judgment → a ledger entry with full shape.** Set `methods`, `bases`,
   `objective`, and `varied_from` so the lesson is *reachable by query* from a
   future recipe that shares the shape. A lesson only in prose is a lesson only
   findable by someone who already remembers it.

Two rules recovered this way, now enforced:

| Rule | Enforced by |
|---|---|
| A training stop rule must be satisfiable by the baseline's measured value, not the target | `check_recipe_defects` |
| A memorization gate needs more than one unique target, or it cannot tell memorization from a constant | `check_recipe_defects` |

