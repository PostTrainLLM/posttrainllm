# Document Status Registry

This registry labels the major documentation surfaces so old roadmap material
does not compete with the closed learning lab.

## Status Labels

| Status | Meaning |
|---|---|
| `active` | Current source for what to do next |
| `closed` | Current completion truth and fresh-experiment gate; no backlog is active |
| `evidence` | Results, attempts, artifacts, and validation history |
| `reference` | Useful background, not the active queue |
| `learning` | Owner curriculum and concept explanations |
| `parked` | Intentionally paused until it unblocks active factory work |
| `superseded` | Preserved for links/history, but replaced by a newer doc |
| `archive` | Historical material only |

## Registry

| Doc / Folder | Status | Use It For | Do Not Use It For |
|---|---|---|---|
| `PROJECT_STATUS.md` | `closed` | completion candidate, release boundary, and fresh-experiment rule | old feature-by-feature backlog |
| `docs/README.md` | `closed` | golden path through the learning artifact and lab | detailed run evidence |
| `docs/NEXT.md` | `closed` | release receipt and fresh-experiment admission rule | an active task queue |
| `docs/factory/` | `reference` | factory contracts, reports, evals, packaging, enforcement | generic ML theory |
| `docs/techniques/` | `reference` | method-vs-recipe cards and closed technique lineages | active task selection |
| `docs/techniques/audit-inventory.md` | `evidence` | row-level treatment of `docs/audits/audit_2026.md` technique rows | run-level success/failure claims |
| `docs/attempt-ledger.md` | `evidence` | 76 final experiment dispositions and lessons | full per-run logs or an active queue |
| `docs/audits/history-coverage-audit.md` | `evidence` | what historical work is normalized, classified, partial, or narrative-only | active task selection |
| `docs/audits/exactness-completion-audit.md` | `evidence` | proof that the docs exactness pass is complete and guarded | new roadmap scope |
| `docs/external-products-reviewed.md` | `evidence` | reviewed products, papers, and stolen techniques | exhaustive literature survey |
| `docs/factory/public-artifacts.md` | `evidence` | public artifact release state and blockers | internal-only scratch notes |
| `docs/learning-pipeline.md` | `learning` | ready owner learning sequence tied to repository labs | generic course catalog |
| `docs/learn/` | `learning` | curriculum and concept references | active project queue |
| `docs/prds/` | `reference` | acceptance criteria for a named/deferred lane | selecting the next active task |
| `docs/PLAN.md` | `reference` | historical feature inventory and shipped/skipped/TODO context | current source of truth |
| `docs/roadmap/` | `superseded` | old roadmap links and historical split | active roadmap |
| `docs/parked/` | `parked` | paused lanes and why they are paused | active tasks |
| `docs/archive/` | `archive` | historical snapshots | current claims |
| `docs/performance/` | `evidence` | kernel, memory, and throughput results and their method notes | active task selection |
| `docs/audits/` | `evidence` | coverage, feature, docs-quality and validation audits | current claims |
| `docs/techniques/` folder pages | `reference` | per-method concept cards (LoRA, MoE, quantization, ...) | run-level results |
| `docs/integrations/` | `reference` | wiring posttrainllm to external tools and data sources | internal contracts |
| `docs/guides/` | `learning` | long-form model / training / study walkthroughs | current queue |
| `docs/sessions/` | `archive` | dated session records and handoffs | current claims |

## Conflict Rule

When docs disagree, trust the newest active/evidence source in this order:

```text
PROJECT_STATUS.md
-> docs/NEXT.md
-> docs/README.md
-> docs/techniques/
-> docs/factory/
-> docs/attempt-ledger.md / run report / public artifact entry
-> docs/prds/PRIORITY.md
-> docs/PLAN.md
-> archived/session notes
```
