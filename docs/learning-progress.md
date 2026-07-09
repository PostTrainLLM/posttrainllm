# Learning Progress Tracker

This tracker makes the owner learning pipeline measurable. The goal is to learn
from the ground up while using posttrainllm as the lab.

Status values:

- `not-started`
- `reading`
- `applied`
- `verified`

## Ground-Up Roadmap Progress

Canonical roadmap: [`learn/curriculum.md`](learn/curriculum.md).

| # | Module | Status | Evidence | Next Concrete Action |
|---:|---|---|---|---|
| 1 | Functions, data, parameters | `reading` | Session 1 exists and has self-checks | Pass mastery gate out loud; write checkpoint |
| 2 | Loss and gradient descent | `reading` | Session 2 exists and has worked examples | Compute one MSE + gradient step by hand |
| 3 | Vectors, matrices, tensors | `not-started` | References exist; polished session missing | Write compact tensor-shapes session or checkpoint from references |
| 4 | Non-linear neural nets + backprop | `not-started` | Session 3 exists | Run/inspect tiny non-linear example |
| 5 | ML paradigms and scaling | `not-started` | Sessions 4 and 5 exist | Classify posttrainllm attempts by paradigm |
| 6 | Tokenization, embeddings, language modeling | `not-started` | Session 6 exists | Tokenize SQL prompts and inspect splits |
| 7 | Attention and transformer blocks | `not-started` | References exist; polished session missing | Work one tiny Q/K/V attention example |
| 8 | Training mechanics | `not-started` | Session 8 exists | Inspect tiny overfit gate and failure symptoms |
| 9 | Post-training: SFT, LoRA, preference tuning | `reading` | SFT/LoRA/DPO docs and SQL run evidence exist | Explain SQL SFT win vs SimPO collapse |
| 10 | Evals, rewards, self-improvement | `reading` | Factory eval protocol, attempt ledger, SQL candidate-choice tools exist | Build/inspect candidate-selection rows and report slice metrics |

## Factory Lab Progress

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

The next project-lab focus is **candidate selection for SQL**:

1. Why selection is easier than generation.
2. How to build candidate sets without leakage.
3. How to score candidate choices by execution/gold equivalence.
4. How to decide whether selection skill transfers back to generation.

The next ground-up focus is **Module 1 -> Module 2**:

1. Explain data vs parameters.
2. Compute loss for bad and better guesses.
3. Take one gradient-descent update.
4. Connect that to why LoRA changes parameters rather than prompts.

## Completion Criteria

A module reaches `verified` only when:

- the concept is explained in owner-readable docs,
- the concept changes a recipe or validator,
- a run or smoke test exercises the change,
- and the result is recorded in `docs/attempt-ledger.md`.

Reading alone is not enough.
