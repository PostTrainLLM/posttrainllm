# Factory Docs

Start here for the retained factory contracts. They are runnable lab material,
not an active project queue; use them only after the fresh-experiment gate in
`../NEXT.md` is met.

posttrainllm's retained product loop is:

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
- [`../attempt-ledger.md`](../attempt-ledger.md) — all 75 final worked, failed,
  regressed, inconclusive, superseded, and rejected attempts.
- [`../external-products-reviewed.md`](../external-products-reviewed.md) —
  external products and techniques reviewed or adopted.
- [`case-study-template.md`](case-study-template.md) — public artifact report
  shape: baseline, failed attempts, slices, trace review, performance, and
  blockers.
- [`batch-posttraining.md`](batch-posttraining.md) — batch rollout, offline
  scoring, compact adapter update, eval, and decision loop.
- [`lora-geometry.md`](lora-geometry.md) — adapter effective-update diagnostics
  for rank and module targeting.
- Closed autocorrect foundation (training was rejected after the bounded bake-off):
  [`autocorrect-foundation.md`](autocorrect-foundation.md) — contract,
  evaluator, simulator, and manifests;
  [`autocorrect-model-shortlist.md`](autocorrect-model-shortlist.md) — the
  measured base bake-off and selection;
  [`autocorrect-adapter-recipe.md`](autocorrect-adapter-recipe.md) — the frozen
  LoRA recipe, the encoder-decoder training path, and its load-parity evidence.
- [`run-schema.md`](run-schema.md) — local run directory contract.
- [`run-lifecycle.md`](run-lifecycle.md) — durable phase/revision state,
  metadata-only operator commands, advisory discovery, and recovery.
- [`report-card.md`](report-card.md) — portable before/after proof contract:
  measurement states, decision semantics, JSON + static report, publication gate.
- [`report-card-cohort.md`](report-card-cohort.md) — the published report-card
  cohort, documented absences, and the mapping gaps the review found.
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
