# Document Status Registry

This registry labels the major documentation surfaces so old roadmap material
does not compete with the active factory path.

## Status Labels

| Status | Meaning |
|---|---|
| `active` | Current source for what to do next |
| `evidence` | Results, attempts, artifacts, and validation history |
| `reference` | Useful background, not the active queue |
| `learning` | Owner curriculum and concept explanations |
| `parked` | Intentionally paused until it unblocks active factory work |
| `superseded` | Preserved for links/history, but replaced by a newer doc |
| `archive` | Historical material only |

## Registry

| Doc / Folder | Status | Use It For | Do Not Use It For |
|---|---|---|---|
| `PROJECT_STATUS.md` | `active` | current project state and active gaps | old feature-by-feature backlog |
| `docs/README.md` | `active` | golden path through the docs | detailed run evidence |
| `docs/NEXT.md` | `active` | current queue and sequencing | broad ideation |
| `docs/factory/` | `active` | factory contracts, reports, evals, packaging, enforcement | generic ML theory |
| `docs/techniques/` | `active` | method-vs-recipe cards and target-specific technique backlog | historical PRD status |
| `docs/techniques/audit-inventory.md` | `evidence` | row-level treatment of `docs/audit_2026.md` technique rows | run-level success/failure claims |
| `docs/attempt-ledger.md` | `evidence` | worked/failed/regressed/not-tried attempts | full per-run logs |
| `docs/history-coverage-audit.md` | `evidence` | what historical work is normalized, classified, partial, or narrative-only | active task selection |
| `docs/exactness-completion-audit.md` | `evidence` | proof that the docs exactness pass is complete and guarded | new roadmap scope |
| `docs/external-products-reviewed.md` | `evidence` | reviewed products, papers, and stolen techniques | exhaustive literature survey |
| `docs/factory/public-artifacts.md` | `evidence` | public artifact release state and blockers | internal-only scratch notes |
| `docs/learning-pipeline.md` | `learning` | current owner learning sequence tied to factory work | generic course catalog |
| `docs/learn/` | `learning` | curriculum and concept references | active project queue |
| `docs/prds/` | `reference` | acceptance criteria for a named/deferred lane | selecting the next active task |
| `docs/PLAN.md` | `reference` | historical feature inventory and shipped/skipped/TODO context | current source of truth |
| `docs/roadmap/` | `superseded` | old roadmap links and historical split | active roadmap |
| `docs/parked/` | `parked` | paused lanes and why they are paused | active tasks |
| `docs/archive/` | `archive` | historical snapshots | current claims |

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
