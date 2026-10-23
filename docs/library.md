---
title: Document library — where to look
description: A labeled map of the retained learning, reference, factory, evidence, and historical documentation.
---

# Document library — where to look

Use this map when you need a document outside the [current learning
session](learning-progress.md#next-session). The sidebar shows the primary
entrances; site search reaches the full retained corpus. Existing document
URLs and Markdown mirrors remain available.

## Learn and build

| Shelf                      | Use it for                                                      | Start here                                                                                                               |
| -------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Current course             | The owner's 13-week inference route and its evidence contract   | [Course workspace](learn.md), [weekly route](learn/inference-systems-13w.md)                                             |
| One active task            | Exercise, checkpoint, and actual delayed recall dates           | [Next Session](learning-progress.md#next-session)                                                                        |
| Foundations                | Prerequisites from functions and tensors to attention and evals | [Ten-module curriculum](learn/curriculum.md), [ordered lessons](learn/README.md#i-want-to-learn-ml-from-scratch)         |
| Practical labs             | Runnable paths, artifacts, exercises, and mastery gates         | [Artifact journey](learn/artifact-journey.md), [learning pipeline](learning-pipeline.md)                                 |
| Model and systems concepts | Architecture, inference, training, and Mac-to-cluster boundary  | [Learning index](learn/README.md#i-want-the-modern-llm-mechanics-reference), [Mac mastery map](learn/mac-mastery-map.md) |

## Apply and evaluate

| Shelf                | Use it for                                              | Start here                                                                                 |
| -------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Factory contract     | Target → data → post-training → eval → package → report | [Factory docs](factory/README.md)                                                          |
| Methods and recipes  | Distinguish a technique from a runnable, gated recipe   | [Technique registry](techniques/README.md), [recipe index](recipes/README.md)              |
| CLI and integrations | Commands, local workflow, and external interfaces       | [CLI reference](cli-reference.md), [integration example](integrations/model-run.md)        |
| Data and models      | Dataset provenance and retained model artifacts         | [Data inventory](data_inventory.md), [model card](hf-cards/qwen3-4b-file-ops-distilled.md) |

## Inspect the evidence

| Shelf       | Use it for                                      | Start here                                                                                                                           |
| ----------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Outcomes    | Final dispositions and failure explanations     | [Attempt ledger](attempt-ledger.md), [public artifacts](factory/public-artifacts.md)                                                 |
| Performance | Measurements, harness design, and method limits | [Benchmark harness design](performance/benchmark_harness_design.md), [Mac decode baseline](research/mac_decode_baseline_m5pro.md)    |
| Research    | Benchmark and landscape findings, with sources  | [Inference benchmark survey](research/inference_benchmarks_may_2026.md), [external products reviewed](external-products-reviewed.md) |
| Audits      | Coverage and validation boundaries              | [History coverage](audits/history-coverage-audit.md), [docs quality](audits/docs-quality-audit.md)                                   |

## Read with historical context

| Shelf                       | Use it for                                               | Start here                                                                                                                   |
| --------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Status and admission        | Closed-lab state and the rule for a fresh experiment     | [Project status](https://github.com/PostTrainLLM/posttrainllm/blob/main/PROJECT_STATUS.md), [closure and next rule](NEXT.md) |
| Deferred specifications     | Acceptance criteria for named historical or parked ideas | [PRD index](prds/README.md), [priority map](prds/PRIORITY.md)                                                                |
| Parked lanes                | Work intentionally paused                                | [Parked lanes](parked/README.md)                                                                                             |
| Archive and session records | Historical plans, transcripts, and dated handoffs        | [Archive status](archive/status.md), [document status registry](doc-status.md)                                               |
| Original walkthrough        | Python → WASM → WebGPU guided tour                       | [Legacy walkthrough](learn/legacy-walkthrough.md)                                                                            |

Historical TODOs and PRDs are reference material. New model work still needs
an owner-selected question and the [fresh-experiment gate](NEXT.md).

## Retained evidence directory

These direct links keep older evidence discoverable without turning the sidebar
into a full archive. They are historical records, not an active backlog or new
claims about model quality.

### Performance receipts

- [First Worked Run — `posttrainllm bench`](performance/benchmark_first_run.md)
- [Cold-start bundle — results](performance/cold_start_results.md)
- [CPU speedup bundle — measured results](performance/cpu_speedup_results.md)
- [CPU utilization research — what we're leaving on the table](performance/cpu_utilization_research.md)
- [Data-side performance levers](performance/data_perf.md)
- [YOCO — "You Only Cache Once" worked example](performance/yoco_results.md)

### Research and audit receipts

- [Learnable cross-stream attention — adopt or skip?](research/cross-stream-attention-evaluation.md)
- [Indic-language evals — MILU + IndicGenBench](research/indic_evals.md)
- [Wave 2.5 kernel audit — BUILD / DEFER / DROP](research/wave_2_5_kernel_audit.md)
- [Mac SLM agentic leaderboard v0](research/mac_slm_leaderboard_v0.md)
- [Feature audit — 2026-05-31](audits/feature_audit_2026_05_31.md)
- [Test Coverage Goals — posttrainllm](audits/test-coverage.md)
- [GitHub Corpus Parity Decision](artifacts/github-corpus-parity.md)

### Factory and specialist references

- [Foundry Evidence Contract — posttrainllm](factory/foundry-evidence.md)
- [Hugging Face Artifact Storage](factory/huggingface-artifact-storage.md)
- [Qwen3-4B ReST Fused](hf-cards/qwen3-4b-rest-fused.md)
- [Recipe — Pace planner specialist](recipes/pace-planner.md)
- [Recipe: distill a big model into a small local specialist](recipes/distill-specialist.md)
- [A1 — first tool-calling specialist](specialists/a1-tool-caller.md)
- [B1 — second specialist: text-to-SQL](specialists/b1-sql.md)
- [parakeet.wgsl browser smoke](techniques/parakeet-wgsl-browser-smoke.md)
- [Needle 2 baseline review](techniques/needle2-baseline-review.md)

### Dated sessions and retrospectives

- [Session — eval-first prep before the 2-day training window](sessions/2026-06-05-eval-first.md)
- [Strategy session — what posttrainllm actually is, what's possible on a Mac](sessions/2026-06-06-mac-specialist-platform.md)
- [Specialist Embedder PRD Blocker](sessions/2026-06-06-specialist-embedder-blocker.md)
- [vllm-mlx Investigation](sessions/2026-06-06-vllm-mlx-investigation.md)
- [Session — 2026-06-08, the factory-validation night](sessions/2026-06-08-factory-validation-night.md)
- [Strategy session — the market landscape and the Mac-first wedge](sessions/2026-06-13-market-landscape-mac-first.md)
- [Session — from frontier-parity distillation to the self-improving loop](sessions/2026-06-16-distill-to-self-improvement.md)
- [Step-back: what we have, the wall, and the ROI menu](sessions/2026-06-17-stepback-inventory-roi.md)
- [Vercel Eve and the local-agent wedge](sessions/2026-06-17-vercel-eve-and-local-agents.md)
- [Drilldown — the experiments left untried, run to bedrock](sessions/DRILLDOWN.md)
- [PostTrainLLM — retrospective and forward plan](sessions/RETROSPECTIVE.md)
- [Pace handoff — posttrainllm deliverables status (2026-06-10)](sessions/pace-handoff-2026-06-10.md)
- [Planner lock - 2026-06-19](sessions/planner-lock-2026-06-19.md)
- [PostTrainLLM — Working Session Q&A Log](sessions/qa_log.md)
- [Session retrospective — 2026-05-31](sessions/session_2026_05_31.md)
- [Session Retrospective: posttrainllm, the Long Working Session](sessions/session_retrospective.md)
- [First specialist run — `toolcall-v1` findings](sessions/specialist_v1_findings.md)
- [v11 baselines — committed 2026-06-09](sessions/v11-baselines-2026-06-09.md)
- [WWDC 2026 (June 8–9) — impact on posttrainllm + Pace](sessions/wwdc-2026-impact.md)
