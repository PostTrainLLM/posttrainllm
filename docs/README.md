# posttrainllm Docs

This is the canonical entrypoint for posttrainllm documentation.

posttrainllm is a completed Mac-local specialist-factory learning artifact and
lab. The docs should let a new reader answer six questions without asking the
project owner:

1. What is this project?
2. What have we tried?
3. What worked, failed, regressed, or received a final disposition?
4. What external products/papers/blogs changed the roadmap?
5. Which hands-on path and mastery gate teaches each retained capability?
6. Which model, adapter, benchmark, agent, package, or systems artifact does the
   learner produce?
7. What evidence and authorization are required to open a fresh experiment?

## Golden Path

Read in this order:

| Step | Doc                                                                                                  | Purpose                                                                                                                                                               |
| ---: | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 | [`../PROJECT_STATUS.md`](https://github.com/PostTrainLLM/posttrainllm/blob/main/PROJECT_STATUS.md)   | Completion state, release boundary, and closed-lab posture                                                                                                            |
|    2 | [`NEXT.md`](NEXT.md)                                                                                 | Closure receipt and fresh-experiment admission rule                                                                                                                   |
|    3 | [`cli-reference.md`](cli-reference.md)                                                               | Complete CLI discovery contract, command families, exit behavior, and verification                                                                                    |
|    4 | [`factory/README.md`](factory/README.md)                                                             | Factory contract: run schema, reports, evals, packaging, public artifacts                                                                                             |
|    5 | [`recipes/registry.json`](recipes/registry.json) and [`techniques/README.md`](techniques/README.md)  | All 18 retained technique recipes and their final dispositions                                                                                                        |
|    6 | [`techniques/audit-inventory.md`](techniques/audit-inventory.md)                                     | Row-level treatment of the broad 2026 technique audit                                                                                                                 |
|    7 | [`attempt-ledger.md`](attempt-ledger.md) and [`attempts.json`](attempts.json)                        | All 75 worked, failed, regressed, inconclusive, superseded, and rejected attempts                                                                                     |
|    8 | [`external-products-reviewed.md`](external-products-reviewed.md)                                     | Competitors/startups/papers/blogs reviewed and what we stole or rejected                                                                                              |
|    9 | [`learn/artifact-journey.md`](learn/artifact-journey.md), [`learn/path-registry.json`](learn/path-registry.json), [`learn/curriculum.md`](learn/curriculum.md) | Nine ready learning stages, thirteen buildable artifacts, evidence, recipes, CLI entry points, labs, and mastery gates; [`learn/coverage-map.md`](learn/coverage-map.md) indexes every subsystem |
|   10 | [`learning-progress.md`](learning-progress.md)                                                       | Measured progress through the owner learning pipeline                                                                                                                 |
|   11 | [`learning-pipeline.md`](learning-pipeline.md)                                                       | How ground-up learning attaches to the factory lab                                                                                                                    |
|   12 | [`factory/public-artifacts.md`](factory/public-artifacts.md)                                         | Public artifact inventory, blockers, and release posture                                                                                                              |
|   13 | [`history-coverage-audit.md`](audits/history-coverage-audit.md)                                      | Exactness boundary for normalized vs unnormalized historical attempts                                                                                                 |
|   14 | [`exactness-completion-audit.md`](audits/exactness-completion-audit.md)                              | Completion proof for the docs exactness pass                                                                                                                          |
|   15 | [`docs-quality-audit.md`](audits/docs-quality-audit.md)                                              | Honest audit of what is world-class now and what still is not                                                                                                         |
|   16 | [`doc-status.md`](doc-status.md)                                                                     | Active/reference/parked/superseded labels for major docs                                                                                                              |

## Retained Project Loop

```text
target -> data -> post-training -> eval -> package -> report
```

Every hands-on lab follows those stages. New project work starts only from a
fresh owner-selected question and scoped issue; retained parked/PRD/TODO text
is historical context, not unfinished work.

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

| Category  | Meaning                                                      | Where                                                                                                                                |
| --------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| Closure   | Completion state, release receipt, and fresh-experiment gate | `PROJECT_STATUS.md`, `docs/NEXT.md`                                                                                                  |
| Evidence  | Attempt results, reports, artifact status                    | `docs/attempt-ledger.md`, `docs/specialists/`, `docs/factory/public-artifacts.md`, `docs/factory/report-card.md`, `runs/*/report.md` |
| Learning  | Owner curriculum and concept explanations                    | `docs/learn/`, `docs/learning-pipeline.md`, `docs/training/`                                                                         |
| Reference | Broad mechanics, recipes, historical plans                   | `docs/recipes/`, `docs/roadmap/`, `docs/prds/`, `docs/PLAN.md`                                                                       |
| Archive   | Superseded or moved material                                 | `docs/archive/`, `docs/parked/`                                                                                                      |

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
