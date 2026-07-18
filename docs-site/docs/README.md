---
title: "posttrainllm Docs"
description: "This is the canonical entrypoint for posttrainllm documentation."
---

# posttrainllm Docs

This is the canonical entrypoint for posttrainllm documentation.

posttrainllm is a Mac-local specialist factory. The docs should let a new reader
answer five questions without asking the project owner:

1. What is this project?
2. What have we tried?
3. What worked, failed, or is still blocked?
4. What external products/papers/blogs changed the roadmap?
5. What should we build and learn next?

## Golden Path

Read in this order:

| Step | Doc | Purpose |
|---:|---|---|
| 1 | [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) | Current state, active product thesis, shipped/parked surfaces, active gaps |
| 2 | [`NEXT.md`](NEXT.md) | Active queue only; what to do next and what not to touch |
| 3 | [`factory/README.md`](factory/README.md) | Factory contract: run schema, reports, evals, packaging, public artifacts |
| 4 | [`techniques/README.md`](techniques/README.md) | Method-vs-recipe registry; how we choose model-improvement tactics |
| 5 | [`techniques/audit-inventory.md`](techniques/audit-inventory.md) | Row-level treatment of the broad 2026 technique audit |
| 6 | [`attempt-ledger.md`](attempt-ledger.md) | What worked, failed, regressed, or remains untried |
| 7 | [`external-products-reviewed.md`](external-products-reviewed.md) | Competitors/startups/papers/blogs reviewed and what we stole or rejected |
| 8 | [`learn/curriculum.md`](learn/curriculum.md) | Ground-up learning roadmap from first principles to self-improving specialists; [`learn/coverage-map.md`](learn/coverage-map.md) indexes every subsystem to a learning anchor |
| 9 | [`learning-progress.md`](learning-progress.md) | Measured progress through the owner learning pipeline |
| 10 | [`learning-pipeline.md`](learning-pipeline.md) | How ground-up learning attaches to the factory lab |
| 11 | [`factory/public-artifacts.md`](factory/public-artifacts.md) | Public artifact inventory, blockers, and release posture |
| 12 | [`history-coverage-audit.md`](history-coverage-audit.md) | Exactness boundary for normalized vs unnormalized historical attempts |
| 13 | [`exactness-completion-audit.md`](exactness-completion-audit.md) | Completion proof for the docs exactness pass |
| 14 | [`docs-quality-audit.md`](docs-quality-audit.md) | Honest audit of what is world-class now and what still is not |
| 15 | [`doc-status.md`](doc-status.md) | Active/reference/parked/superseded labels for major docs |

## Current Project Loop

```text
target -> data -> post-training -> eval -> package -> report
```

Every active task should improve one of those stages. If it does not, it belongs
in `docs/parked/`, `docs/prds/`, or the learning corpus.

## Documentation Standard

For every meaningful model/factory attempt, the docs must record:

- target and frozen eval
- recipe, not just method
- data source and provenance
- baseline result
- candidate result
- slice metrics
- trace review or failure taxonomy
- failure reason confidence and evidence sources
- performance where feasible
- decision: `ship`, `retry`, or `reject`
- next action

For every external product or paper that changes the plan, the docs must record:

- source
- useful technique
- local translation
- status: adopted, scaffolded, tried, rejected, or parked
- next smallest experiment

## Active vs Reference vs Archive

| Category | Meaning | Where |
|---|---|---|
| Active | Current work queue and gates | `PROJECT_STATUS.md`, `docs/NEXT.md`, `docs/factory/`, `docs/techniques/` |
| Evidence | Attempt results, reports, artifact status | `docs/attempt-ledger.md`, `docs/specialists/`, `docs/factory/public-artifacts.md`, `runs/*/report.md` |
| Learning | Owner curriculum and concept explanations | `docs/learn/`, `docs/learning-pipeline.md`, `docs/training/` |
| Reference | Broad mechanics, recipes, historical plans | `docs/recipes/`, `docs/roadmap/`, `docs/prds/`, `docs/PLAN.md` |
| Archive | Superseded or moved material | `docs/archive/`, `docs/parked/` |

If two docs conflict, prefer current source in this order:

```text
PROJECT_STATUS.md
-> docs/NEXT.md
-> docs/techniques/
-> docs/factory/
-> run report / artifact entry
-> older PRD/PLAN/session notes
```

See [`doc-status.md`](doc-status.md) for the status label of each major docs
surface.
