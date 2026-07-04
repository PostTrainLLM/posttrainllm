# Attempt Ledger

This ledger records meaningful TinyGPT attempts as worked, failed, regressed,
inconclusive, or not yet tried. It is the human-readable companion to run
folders and factory reports.

The point is not to look successful. The point is to preserve the experimental
state so the next recipe is better than the last one.

Structured index: [`docs/attempts.json`](attempts.json). Check sync with:

```bash
bash evals/attempt-ledger-smoke.sh
```

## Status Vocabulary

| Status | Meaning |
|---|---|
| `worked` | Passed the intended gate for that attempt |
| `worked-with-caveat` | Improved the target but exposed a blocker/regression |
| `failed` | Did not pass the intended gate |
| `regressed` | Improved one slice but damaged a required gate |
| `inconclusive` | Evidence too weak or eval not credible enough |
| `not-tried` | Planned/scaffolded but not executed as a model run |

## SQL Specialist Attempts

SQL is the current factory POC and the best-documented attempt family.

| Attempt | Recipe | Evidence | Status | Decision / Lesson |
|---|---|---|---|---|
| Toy SQL SFT | Qwen3-0.6B + rank-4 DoRA/LoRA on 12 rows | execution `0.167 -> 0.833` on 6-row fixture | `worked-with-caveat` | Proved loop mechanics, but train/eval overlap made it non-shippable |
| Expanded synthetic SQL SFT | 108 train rows, 50 heldout rows, five SQLite domains | execution `0.160 -> 0.860`, exact `0.140 -> 0.840` | `worked` | Current synthetic SQL adapter; joins remain weaker than single-table rows |
| Public b-mc2 v1 | 512 public-style SFT rows, rank 8, 300 steps | exact `0.344` vs T5-small `0.484` | `failed` | More public-style data needed |
| Public b-mc2 v2 | 2048 rows, rank 16, 1200 steps | exact `0.031` | `failed` | Bigger data/rank/steps made the recipe worse |
| Public b-mc2 v3 | 2048 rows, rank 8, lower LR, 600 steps | exact `0.422` | `failed` | Better than v2, still below T5-small |
| Public b-mc2 v4 | Join/group weighted public rows, rank 8, 700 steps | exact `0.531` vs T5-small `0.484` | `worked-with-caveat` | Beat small public baseline but regressed synthetic execution |
| Public v4 synthetic regression check | v4 scored on synthetic execution fixture | synthetic execution `0.240` vs incumbent `0.860` | `regressed` | Public style overfit/hallucinated schema links; cannot ship as one adapter |
| Blended public+synthetic SFT | Public rows + synthetic rows mixed into one adapter | public `0.297`, synthetic execution `0.560` | `failed` | Naive mixture caused interference and output-format collapse |
| Static multi-LoRA composition | Public + synthetic adapters composed with fixed weights | best public-pass setting still synthetic-failed | `failed` | Smooth tradeoff, no weight passed both gates |
| Routed public + synthetic adapters | Route public schemas to public adapter; synthetic DB rows to synthetic adapter | public exact `0.531`, synthetic execution `0.860` | `worked-with-caveat` | Best current report artifact; not package-ready until public execution and perf gates |
| Hygiene SimPO/DPO | Ref-free SimPO on 108 SQL-only preference pairs | execution `0.860 -> 0.080`, clean-SQL `0.000 -> 0.000` | `failed` | Policy collapse; retry only with reference anchoring or much smaller update |
| SQL candidate selection | Choose best SQL among candidates before open generation | tooling and smoke exist; no model run | `not-tried` | Highest-priority next recipe |
| Offline rollout / OAPL-style SQL update | Batch rollouts, score offline, one adapter update | plan renderer exists; no model run | `not-tried` | Run only after candidate-selection reward surface is clean |
| Controlled SQL LoRA rank sweep | Same data, ranks `{1,2,4,8}`, fixed seed/steps/LR | not run | `not-tried` | Needed to separate capacity from data/recipe confounds |

Primary source docs:

- [`docs/specialists/b1-sql-poc.md`](specialists/b1-sql-poc.md)
- [`docs/techniques/sql-technique-backlog.md`](techniques/sql-technique-backlog.md)
- [`docs/factory/public-artifacts.md`](factory/public-artifacts.md)
- Local run reports under `runs/2026-07-02-*` and
  `runs/2026-07-03-sql-hygiene-dpo-qwen06/`

## Factory / Documentation Attempts

| Attempt | Result | Status | Lesson |
|---|---|---|---|
| Factory run schema | `docs/factory/run-schema.md` defines expected run folder | `worked-with-caveat` | Schema exists; validation still needs stronger enforcement |
| SQL factory run renderer | `scripts/render_sql_factory_run.py` renders canonical SQL report artifacts | `worked-with-caveat` | Useful bridge; not yet one universal factory command |
| Public artifact registry | `docs/factory/public-artifacts.md` tracks artifacts, blockers, release state | `worked` | Public artifacts and blockers are first-class |
| Technique registry | `docs/techniques/` distinguishes methods from recipes | `worked-with-caveat` | Registry exists; next step is validator/release enforcement |
| TrainLoop-style tooling | candidate choice, slice metrics, trace review, batch plan, LoRA geometry | `worked-with-caveat` | Tooling passes smokes; most recipes not trained yet |

## Next Ledger Improvements

This ledger should eventually be generated or checked from structured run
metadata. Required future fields:

- run id
- git commit / binary provenance
- dataset hash
- exact commands
- train/eval cost
- latency/RAM/tok-s
- report URL
- artifact URL
