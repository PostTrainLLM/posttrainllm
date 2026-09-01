# SQL Technique Lineage — Closed

This is the SQL-specific ledger of methods, recipes, status, and next smallest
tests. It exists to prevent the roadmap from looking complete just because broad
method names are present.

## Current Evidence

| Recipe / Attempt | Status | Evidence | Decision |
|---|---|---|---|
| Toy SQL SFT, rank 4 | Worked as a factory proof | execution `0.167 -> 0.833` on 6 rows | `retry-data` because train/eval overlap |
| Expanded synthetic SQL SFT, rank 4 | Worked | execution `0.160 -> 0.860`, exact `0.140 -> 0.840` on 50 rows | current synthetic specialist |
| Public b-mc2 SFT v1 | Failed | exact `0.344` vs T5-small `0.484` | reject |
| Public b-mc2 SFT v2 | Failed badly | exact `0.031` | reject |
| Public b-mc2 SFT v3 | Improved but failed gate | exact `0.422` | reject |
| Public b-mc2 SFT v4, join/group weighted | Worked on public exact | exact `0.531` vs T5-small `0.484` | not shippable; synthetic regression |
| Public v4 synthetic regression | Failed | synthetic execution `0.240` vs incumbent `0.860` | route or compose |
| Public+synthetic blended SFT | Failed/interfered | public `0.297`, synthetic execution `0.560` | reject |
| Static multi-LoRA composition | Failed to pass both gates | best public pass still had synthetic failure | reject |
| Routed public + synthetic adapters | Best current candidate | public exact `0.531`, synthetic execution `0.860` | report-ready, not package-ready |
| Hygiene SimPO/DPO adapter | Failed hard | execution `0.860 -> 0.080`, degenerate output | retry-training |

## Closed Historical Proposals

| Technique | Method | Historical proposal | Final disposition | Fresh-work rule |
|---|---|---|---|---|
| Candidate-selection curriculum | supervised selection / RLVR bridge | Build rows with 4-6 candidate SQL strings and learn to pick the executable answer | `rejected`: no frozen candidate dataset or eval existed before project closure | Reopen only as a new experiment after learning with leakage checks and a frozen selection gate |
| Reference-anchored hygiene DPO | DPO | Retry the failed hygiene goal with a reference anchor, lower LR, fewer steps, and composed eval against the SFT adapter | Ref-free SimPO over-optimized and collapsed; reference anchoring should preserve generation quality | Same 108 pairs, frozen 50-row eval, require no execution regression and clean-SQL lift |
| One-step offline rollout update | OAPL/ReST-style batch loop | Generate N rollouts per prompt, score offline, and train one adapter update | `rejected`: its candidate-selection reward prerequisite was never validated | A new experiment must validate the reward before any update |
| Policy lag / stale reference | RL regularization | Keep the rollout policy fixed or compare against a stale reference | `rejected`: no valid offline rollout experiment existed to vary | Treat only as a variable inside a future fresh RL experiment |
| Controlled LoRA rank sweep | LoRA/DoRA | Sweep rank `{1,2,4,8}` with every other variable fixed | `rejected`: no active frozen SQL target existed, so the sweep would not resolve the historical confound | Start as a new experiment with fixed data, seed, steps, LR, and eval |
| LoRA geometry decision check | diagnostics | Compare successful, failed, and retry adapters by effective-update norm/stable rank/module concentration | Explains whether a failure learned too little, too diffusely, or in the wrong layers | Run `scripts/lora_geometry.py` on every meaningful adapter and attach `lora-geometry.json` |
| Slice-gated reporting | eval discipline | Require overall, join, single-table, filter, aggregate, format, and clean-output slices | Overall hides the known join weakness and hygiene failure | Generate `slice-metrics.json` for every SQL report |
| Trace review as data source | failure analysis | Classify failures into hallucinated schema, missing join, wrong filter, prose/fence wrapping, no-select collapse | Converts failed attempts into targeted data or preferences | Generate `trace_review.md` for every SQL report |

## Closure

There is no SQL priority queue after this pass. The measured lineage, failed
recipes, routed result, and rejected proposals are retained as a learning lab.
Future SQL work begins from a newly frozen question rather than continuing this
historical sequence by inertia.

## Enforcement

No SQL candidate should be reported as improved unless the run folder contains:

- `eval-baseline.json`
- `eval-candidate.json`
- `slice-metrics.json`
- `trace_review.md`
- `report.md`
- `decision.json`

No SQL candidate should be packaged unless the decision is `ship` and the public
execution gate is present or explicitly waived in the report.
