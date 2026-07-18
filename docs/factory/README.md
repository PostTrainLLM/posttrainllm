# Factory Docs

Start here for active posttrainllm work.

posttrainllm's current product loop is:

```text
target -> data -> post-training -> eval -> package -> report
```

## Files

- [`../README.md`](../README.md) — golden path through state, attempts,
  reviewed products, roadmap, and learning.
- [`overview.md`](overview.md) — what the factory is and what counts as proof.
- [`post-training-factory.md`](post-training-factory.md) — how data,
  post-training, evals, performance, packaging, and public artifacts fit
  together.
- [`../attempt-ledger.md`](../attempt-ledger.md) — worked, failed, regressed,
  inconclusive, and not-yet-tried attempts.
- [`../external-products-reviewed.md`](../external-products-reviewed.md) —
  external products and techniques reviewed or adopted.
- [`case-study-template.md`](case-study-template.md) — public artifact report
  shape: baseline, failed attempts, slices, trace review, performance, and
  blockers.
- [`batch-posttraining.md`](batch-posttraining.md) — batch rollout, offline
  scoring, compact adapter update, eval, and decision loop.
- [`lora-geometry.md`](lora-geometry.md) — adapter effective-update diagnostics
  for rank and module targeting.
- [`run-schema.md`](run-schema.md) — local run directory contract.
- [`enforcement.md`](enforcement.md) — native validation plus stricter
  publish-check requirements.
- [`eval-protocol.md`](eval-protocol.md) — baseline, regression, and ship/reject rules.
- [`packaging.md`](packaging.md) — specialist package layout and lock metadata.
- [`reports.md`](reports.md) — before/after report template.
- [`public-artifacts.md`](public-artifacts.md) — public artifact registry,
  release states, and blockers.
- [`../techniques/README`](../techniques/README) — method-vs-recipe registry. Use this
  before selecting a post-training run so "try DPO/RLVR/LoRA" becomes a concrete
  recipe with data, eval, slices, and stop rule.

## Rule

Use existing primitives first. Add new tooling only when it directly improves
data preparation, post-training, eval, packaging, or reporting for the current
factory target.

Do not treat a method name as a plan. A run is ready only when it has a recipe:
target, failure mode, data, reward or labels, eval gates, slice gates, and a
ship/retry/reject threshold.
