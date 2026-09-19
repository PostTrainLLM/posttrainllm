# Learning Progress Tracker

This tracker makes the owner learning pipeline measurable. The goal is to learn
from the ground up while using posttrainllm as the lab.

## Next Session

This is the single current-session page. The curriculum, practical paths,
articles, and artifacts are the reference library, not competing task queues.

| Field | Current selection |
|---|---|
| Current module | **Module 1 — Functions, data, parameters** |
| Read | [Session 1](learn/session-01-neural-net-basics.md), only as needed for the exercise |
| One exercise | For `(x,y) = (0,1), (1,3), (2,5), (3,7), (4,9)`, choose `m,b` for `y = mx + b`; show all five predictions and label inputs, targets, parameters, and predictions |
| One explanation | In your own words, explain which quantities stay fixed during fitting, which change, and how parameters differ from inputs; name one corresponding quantity in the repo |
| Evidence to save | Your calculation and explanation in a dated checkpoint below; unanswered questions stay explicit |
| Immediate gate | Explain a parameter without LLM jargon and predict the effect of changing `m` versus `b` on a new input |
| Delayed recall | Not scheduled yet: set actual dates at exercise completion, for +2 and +7 days |
| Next eligible module | Module 2, after the exercise and immediate gate pass |

Suggested session: 5 minutes of due recall, 10 minutes of focused reading,
10 minutes on the exercise, and 5 minutes recording your explanation. Split
larger labs across sessions while keeping one exercise in focus.

## Learning Loop

1. Start with any due recall check, closed-book, before rereading.
2. Work on the **one current module** and its **one selected exercise**.
3. Record **one explanation in the owner's words**, the actual work, errors,
   and a link to a relevant repo artifact. An agent may critique or transcribe
   it, but must not substitute its own answer as evidence of owner mastery.
4. On an immediate pass, mark `applied`, set recall dates for **+2 days** and
   **+7 days** from completion, and select the next prerequisite-ready module.
   Earlier modules can await recall while one new module is current.
5. At each recall, explain without notes and solve a changed example or
   diagnose a new failure. Record the answer before checking it. A failed
   recall returns the topic to `reading`; repair the gap as the current focus
   and restart its recall dates after the repaired exercise passes.
6. Mark `verified` only after both delayed checks pass. If a check is overdue,
   do it at the next session; elapsed time alone never counts as a pass.

Status meanings for new checkpoints:

- `not-started`: queued material, with no owner work recorded.
- `reading`: active study or a gap being repaired; mastery is not established.
- `applied`: exercise and immediate gate passed, with owner evidence recorded.
- `verified`: immediate gate plus both delayed recall checks passed.

The intervals are our starting schedule, adjustable from observed recall.
These are tracked due dates, not automated reminders. No dates or passes are
inferred from the existence of an article, lesson, artifact, or agent review.

## Checkpoints and Recall Queue

No checkpoints have been recorded under this loop yet. Keep completed and
failed entries; when changing the current session, do not overwrite evidence.
Append one block per exercise and update only its recall results:

```text
Date / module:
Exercise and actual work (inline or artifact link):
Owner explanation:
Repo connection and practical consequence:
Immediate gate: pending / pass / needs repair; evidence:
Errors or open questions:
Recall +2 days: due YYYY-MM-DD; actual date; changed prompt; answer; result:
Recall +7 days: due YYYY-MM-DD; actual date; changed prompt; answer; result:
Status:
Next session:
```

## Preserved Learning Library

- [Ten-module curriculum](learn/curriculum.md): prerequisites and mastery gates.
- [Nine practical paths](learn/path-registry.json): deeper labs and repo anchors.
- [Thirteen buildable artifacts](learn/artifact-journey.json): build/modify/tune/prove/package work.
- [Coverage map](learn/coverage-map.md): find the lesson for each subsystem.
- [Industry roadmap](industry_learning_roadmap.md): all external readings,
  including Savante, Bonsai, QORL and its owner PRD, Inside vLLM, and Splash.
- [Recipe registry](recipes/registry.json) and [attempt ledger](attempt-ledger.md):
  retained methods, experiments, results, and failures.

Add new articles to the library and the case-study table without changing the
current session. Select one as an exercise when its prerequisites are met or
when the owner deliberately chooses it. Breadth remains available, including
Mac-to-cluster boundary study; it does not create parallel active assignments.

## Ground-Up Roadmap Progress

Canonical roadmap: [`learn/curriculum.md`](learn/curriculum.md).
Coverage index (every subsystem → anchor): [`learn/coverage-map.md`](learn/coverage-map.md).

All ten modules now have a polished session; remaining work is mastery, not
authoring. The rows below preserve the pre-loop status and resource notes;
lesson existence is not evidence of owner mastery. None is promoted by this
reorganization. Replace a resource note with checkpoint evidence when the
owner completes the work; use Next Session above for the current selection.

| # | Module | Status | Evidence | Next Concrete Action |
|---:|---|---|---|---|
| 1 | Functions, data, parameters | `reading` | Session 1 exists and has self-checks | Pass mastery gate out loud; write checkpoint |
| 2 | Loss and gradient descent | `reading` | Session 2 exists and has worked examples | Compute one MSE + gradient step by hand |
| 3 | Vectors, matrices, tensors | `reading` | Session 9 (tensors) written; anchors LoRA shape logic | Trace one layer's shapes; read a shape error and name the wrong axis |
| 4 | Non-linear neural nets + backprop | `not-started` | Session 3 exists | Run/inspect tiny non-linear example |
| 5 | ML paradigms and scaling | `not-started` | Sessions 4 and 5 exist | Classify posttrainllm attempts by paradigm |
| 6 | Tokenization, embeddings, language modeling | `not-started` | Session 6 exists | Tokenize SQL prompts and inspect splits |
| 7 | Attention and transformer blocks | `reading` | Session 10 (attention) written; ties to interpretability heatmap | Work one tiny Q/K/V attention example |
| 8 | Training mechanics | `not-started` | Session 8 exists | Inspect tiny overfit gate and failure symptoms |
| 9 | Post-training: SFT, LoRA, preference tuning | `reading` | SFT/LoRA/DPO docs and SQL run evidence exist | Explain SQL SFT win vs SimPO collapse |
| 10 | Evals, rewards, self-improvement | `reading` | Session 11 (evals/rewards) written; eval protocol, attempt ledger, SQL candidate-choice tools exist | Build/inspect candidate-selection rows and report slice metrics |

## Industry Case-Study Progress

Added at the owner's request on 2026-09-19. Source review by an agent does not
establish owner mastery; the queued exercises remain `not-started`.

| Case Study | Learning Paths | Status | Next Concrete Action |
|---|---|---|---|
| [Savante / Aryabhata](industry_learning_roadmap.md#case-study---savante--aryabhata-specialist-data-and-evaluation) | Post-training; evaluation and factory | `not-started` | Write the recipe teardown and identify missing causal/leakage evidence |
| [Bonsai 2 27B](industry_learning_roadmap.md#case-study---bonsai-2-27b-capability-retained-per-deployment-cost) | Quantization and packaging; runtime and agents | `not-started` | Draft the artifact/runtime comparison sheet with unmeasured fields marked unknown |
| [QORL / parameter-aware query optimization](industry_learning_roadmap.md#case-study---qorl-parameter-aware-query-optimization) | Evaluation and factory; runtime and agents | `not-started` | Draft the frozen three-arm comparison protocol from the retained owner PRD; no database runs yet |
| [Inside vLLM](industry_learning_roadmap.md#case-study---inside-vllm-inference-systems-and-scaling-boundaries) | Runtime and agents; architecture and kernels | `not-started` | Hand-simulate three requests and KV-block allocation; write the latency/throughput prediction table |
| [Splash](industry_learning_roadmap.md#case-study---splash-model-specific-mac-inference) | Runtime and agents; architecture and kernels; quantization and packaging | `not-started` | Design the same-Mac specialized-versus-general engine comparison; no install or benchmark yet |

Record the explanation, inspected source, open questions, and mastery-gate
result here after study. These entries authorize learning, not model runs.

## Factory Lab Progress

This table preserves historical lab evidence and conditional next actions.
Fresh experiments follow [the admission rule](NEXT.md); these rows are not an
active task queue.

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

The next ground-up focus is **Module 1 -> Module 2**. Only Module 1 is current;
Module 2 becomes eligible after its immediate gate. The Next Session card is
the authoritative selection, and earlier modules remain in the recall queue.
SQL candidate selection remains a retained lab example for later study.

## Completion Criteria

A module reaches `verified` through the evidence-backed Learning Loop above.
A hand calculation, code inspection, or small simulation can demonstrate
learning; a production change or new training run is not required. Record
learning evidence here. Record actual experiments in the attempt ledger only
when they occur under the [fresh-experiment rule](NEXT.md).
