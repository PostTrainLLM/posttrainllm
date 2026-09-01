# Technique Registry

This directory is the canonical place for post-training tactics that may improve
posttrainllm factory runs.

The rest of the roadmap tracks products, PRDs, and run artifacts. This registry
tracks the smaller unit that actually changes model quality:

```text
method -> recipe -> experiment -> result -> next recipe
```

The historical project is closed. The machine-readable completion contract is
[`../recipes/registry.json`](../recipes/registry.json): every retained technique
has a final status, concrete target, failure mode, data contract, method,
primary and regression evals, resource budget, stop rule, decision rule,
evidence, exercise, and mastery gate. It is a learning-lab catalog, not an
active AI backlog.

## Definitions

- **Method:** a general technique, such as SFT, DPO, GRPO/RLVR, LoRA,
  constrained decoding, routing, or evaluation.
- **Recipe:** a concrete way to apply a method to one target, with data shape,
  reward, hyperparameters, eval slices, failure mode, and stop rule.
- **Experiment:** one frozen run of one recipe.
- **Result:** worked, failed, regressed, or inconclusive, with numbers.

See [`method-vs-recipe.md`](method-vs-recipe.md) for the distinction.

## Retained Files

- [`method-vs-recipe.md`](method-vs-recipe.md) — vocabulary and examples.
- [`audit-inventory.md`](audit-inventory.md) — row-level treatment of the
  broad `audit_2026.md` technique audit.
- [`sql-technique-backlog.md`](sql-technique-backlog.md) — SQL-specific method,
  recipe, final status, and closed lineage.
- [`trainloop-teardown.md`](trainloop-teardown.md) — techniques extracted from
  TrainLoop case studies and how they map to posttrainllm.
- [`../external-products-reviewed.md`](../external-products-reviewed.md) —
  cross-project ledger of products, papers, and techniques reviewed.
- [`../attempt-ledger.md`](../attempt-ledger.md) — global worked/failed attempt
  history.
- [`../recipes/registry.json`](../recipes/registry.json) — complete
  technique-to-recipe and learning-path contract.
- [`../learn/path-registry.json`](../learn/path-registry.json) — prerequisites,
  lab exercise, and mastery gate for every recipe path.

## Rules

When the owner starts a fresh post-training experiment after learning:

1. Pick a target and frozen eval.
2. Select one recipe from the closed technique catalog.
3. Record why that recipe should address the current failure mode.
4. Define the smallest test and ship/reject threshold.
5. Make sure the run can produce the factory evidence:
   `eval-baseline.json`, `eval-candidate.json`, `slice-metrics.json`,
   `trace_review.md`, `report.md`, and `decision.json`.

Do not treat a method name as a plan. "Try DPO" is not a recipe.

No row in this directory authorizes follow-up work by itself. A fresh run needs
a new owner-selected question and tracking issue.
