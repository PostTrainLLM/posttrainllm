# Factory Docs

Start here for active TinyGPT work.

TinyGPT's current product loop is:

```text
target -> data -> post-training -> eval -> package -> report
```

## Files

- [`overview.md`](overview.md) — what the factory is and what counts as proof.
- [`post-training-factory.md`](post-training-factory.md) — how data,
  post-training, evals, performance, packaging, and public artifacts fit
  together.
- [`run-schema.md`](run-schema.md) — local run directory contract.
- [`eval-protocol.md`](eval-protocol.md) — baseline, regression, and ship/reject rules.
- [`packaging.md`](packaging.md) — specialist package layout and lock metadata.
- [`reports.md`](reports.md) — before/after report template.
- [`public-artifacts.md`](public-artifacts.md) — public artifact registry,
  release states, and blockers.

## Rule

Use existing primitives first. Add new tooling only when it directly improves
data preparation, post-training, eval, packaging, or reporting for the current
factory target.
