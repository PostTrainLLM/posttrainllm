# Planner lock - 2026-06-19

This is the stop point for planner-model churn. Starting tomorrow, planner
work should be integration, routing, latency, and daily-use fixes, not another
base-model search.

## Decision

**Default general Pace planner: Qwen3-4B-Instruct-2507 bf16, stock weights,
with the plan-then-execute system prompt.**

Use the local HF snapshot:

```text
~/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554
```

Why:

- It is the best current multi-domain agent in the latest breadth check:
  stock 4B scored 59.6% on held-out non-filesystem BFCL multi-turn tasks,
  while the file-ops distilled 4B regressed to 42.3%.
- It is near-frontier on the validated single-turn tool-calling slice:
  Qwen3-4B-Instruct-2507 bf16 scored 88.7 vs frontier 98.0.
- The plan-then-execute prompt is a free and measured lift on the hard
  multi-turn gate: 58% -> 75%.
- Training interventions on this strong base have either been neutral or
  regressive for general use. More planner-model tuning is not the next lever.

## What not to ship as the general planner

- **Qwen3-0.6B**: ruled out. It remains useful for cheap harness smoke tests,
  not production planning. Today's bounded BFCL pace12 run scored 5/12 in full
  schema mode and 0/4 in deferred mode on the same prefix.
- **File-ops distilled Qwen3-4B**: strong routed specialist only. It hits
  100% on the file-ops hard gate, but negative-transfers on other backends.
  Use it only behind a router for that domain, not as the general planner.
- **Gemma-3/4 12B**: keep as a challenger and unhappy-path reference. It won
  the older n=130 unhappy-path drill, but the newer agentic head-to-head and
  breadth checks make the stock 4B the better general planner choice today.
- **Deferred tools as default**: not yet. B26 remains behind an eval gate.

## B26/deferred-tools note

Today's cheap real-model probe used Qwen3-0.6B against BFCL `pace12` with a
12-tool catalog:

| mode | sample | pass rate | parse errors | p50 latency |
|---|---:|---:|---:|---:|
| full schemas | 12 | 5/12 (41.7%) | 1 | 7354 ms |
| deferred schemas | first 4 | 0/4 (0.0%) | 0 | 10137 ms |

The matching full-schema prefix was 2/4, so deferred was -50pp on that small
prefix. This is not the full B26 acceptance gate, but it is enough to keep
deferred tools off for the planner lock.

## Reopen rule

Do not reopen planner-model selection unless daily use produces a concrete
failure cluster with saved prompts, tool catalog, expected actions, model
outputs, and a small eval that reproduces the issue. If that happens, compare
against this locked stock-4B baseline before training or switching bases.
