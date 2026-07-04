# Learning Progress Tracker

This tracker makes the owner learning pipeline measurable. The goal is not to
finish a generic course. The goal is to learn exactly what improves the TinyGPT
factory.

Status values:

- `not-started`
- `reading`
- `applied`
- `verified`

## Modules

| Module | Status | Evidence | Next Concrete Action |
|---|---|---|---|
| Eval design | `applied` | Frozen SQL gates, public-vs-synthetic distinction, slice metrics tooling | Add public Spider/BIRD execution gate when DBs are local |
| Data for post-training | `applied` | SQL SFT rows, preference pairs, failure-derived rows, candidate-choice builder | Build candidate-selection train/eval rows from existing predictions |
| SFT + LoRA mechanics | `applied` | Expanded synthetic SFT worked; public v4 worked on public exact; LoRA geometry tooling exists | Run controlled rank sweep only after next target is frozen |
| Preference tuning | `applied` | Hygiene SimPO collapsed and is documented | Write/run reference-anchored DPO retry recipe |
| Verifiable rewards | `reading` | SQL execution and BFCL AST matching are understood as target reward surfaces | Turn SQL candidate selection into a scored reward/data loop |
| RLVR / ReST / OAPL | `not-started` | Batch plan renderer exists; no model run | Start only after candidate-selection evidence exists |
| Failure analysis | `applied` | Failure taxonomy, trace review tooling, attempt ledger | Attach `trace_review.md` to every new SQL run |
| Public reporting | `applied` | Public artifacts registry, case-study template, publish-check | Re-render public SQL artifact with perf and public execution when available |

## Current Focus

The next learning focus is **candidate selection for SQL**:

1. Why selection is easier than generation.
2. How to build candidate sets without leakage.
3. How to score candidate choices by execution/gold equivalence.
4. How to decide whether selection skill transfers back to generation.

## Completion Criteria

A module reaches `verified` only when:

- the concept is explained in owner-readable docs,
- the concept changes a recipe or validator,
- a run or smoke test exercises the change,
- and the result is recorded in `docs/attempt-ledger.md`.

Reading alone is not enough.

