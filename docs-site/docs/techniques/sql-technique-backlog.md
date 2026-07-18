---
title: "SQL Technique Backlog"
description: "This is the SQL-specific ledger of methods, recipes, status, and next smallest"
---

# SQL Technique Backlog

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

## Not Yet Tried

| Technique | Method | Concrete SQL recipe | Why It Might Help | Smallest Next Test |
|---|---|---|---|---|
| Candidate-selection curriculum | supervised selection / RLVR bridge | Build rows with 4-6 candidate SQL strings, train/eval the model to pick the executable/gold-equivalent answer before open generation | SQL generation is sparse-reward; selecting among candidates is easier and creates denser learning signal | Use `scripts/build_sql_candidate_choice.py` on existing candidate predictions, create a tiny SFT/eval slice, compare selection accuracy by join/filter/group slices |
| Reference-anchored hygiene DPO | DPO | Retry the failed hygiene goal with a reference anchor, lower LR, fewer steps, and composed eval against the SFT adapter | Ref-free SimPO over-optimized and collapsed; reference anchoring should preserve generation quality | Same 108 pairs, frozen 50-row eval, require no execution regression and clean-SQL lift |
| One-step offline rollout update | OAPL/ReST-style batch loop | Generate N rollouts per prompt, score offline by execution/gold/format, train one adapter update, evaluate heldout | Keeps the loop batch-first and avoids moving-target on-policy instability | Render a batch plan with `scripts/render_batch_posttrain_plan.py`, then run only after candidate-selection evidence |
| Policy lag / stale reference | RL regularization | Keep rollout policy fixed for a batch or compare against a stale reference during preference/RL update | Prevents the optimizer from chasing its own malformed outputs | Add as a variant only after a first offline rollout update exists |
| Controlled LoRA rank sweep | LoRA/DoRA | Sweep rank `{1,2,4,8}` on the same frozen SQL data with fixed seed/steps/LR | Existing ranks were confounded with different data/recipes; successful adapters have low effective stable rank | Run no more than one small sweep after the next target is frozen; report slice metrics and geometry |
| LoRA geometry decision check | diagnostics | Compare successful, failed, and retry adapters by effective-update norm/stable rank/module concentration | Explains whether a failure learned too little, too diffusely, or in the wrong layers | Run `scripts/lora_geometry.py` on every meaningful adapter and attach `lora-geometry.json` |
| Slice-gated reporting | eval discipline | Require overall, join, single-table, filter, aggregate, format, and clean-output slices | Overall hides the known join weakness and hygiene failure | Generate `slice-metrics.json` for every SQL report |
| Trace review as data source | failure analysis | Classify failures into hallucinated schema, missing join, wrong filter, prose/fence wrapping, no-select collapse | Converts failed attempts into targeted data or preferences | Generate `trace_review.md` for every SQL report |

## Priority Order

1. **Candidate-selection curriculum.**
   This is the cheapest new recipe and directly addresses sparse SQL reward.
2. **Reference-anchored hygiene DPO.**
   This retries the known hygiene failure with a safer recipe.
3. **Public execution gate.**
   This changes the eval from exact string match to a more serious SQL claim.
4. **Controlled rank sweep + geometry.**
   Run after the next target is frozen so the sweep is not confounded.
5. **Offline rollout update / OAPL-style loop.**
   Run only after candidate-selection creates a clean reward surface.

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

