---
title: Learn — course workspace
description: Continue the interactive 13-week inference-systems sprint, with foundations and retained learning references nearby.
---

# Learn — course workspace

The active owner route is the [13-week inference-systems sprint](learn/inference-systems-13w.md),
28 September–27 December 2026. It starts with a transformer forward trace on
one Mac and builds toward measurement, runtime changes, serving, and the
single-device-to-cluster boundary. Each week asks for a prediction, a bounded
check, and an independent explanation. Reading or a passing script alone does
not establish mastery.

## Start with one session

1. Open the [interactive inference workspace](https://posttrainllm.com/learn/session?route=inference-systems-13w).
   Empty browser state starts at Week 1, Day 1; existing progress resumes.
2. Learn the Day 1 concepts, record a prediction, do the small CPU exercise,
   check the result, and explain it in your own words. The full reference-model
   smoke arrives on Day 6 after attention has been taught.
3. Save a browser-local checkpoint and use Continue for the next day. See the
   [manual progress record](learning-progress.md) for historical context;
   opening a page never records mastery.

## Course route

| Stage | Read and do |
|---|---|
| **Now — Week 1** | [Seven ready sessions](learn/inference-systems-13w.md#week-1-seven-ready-lessons): token IDs to logits, causal attention, the reference CPU trace, and a closed-book debug. |
| **Next — Weeks 2–3** | Generation, prefill/decode, KV cache, and measured latency and memory. Start only after the preceding immediate gate. |
| **Later — Weeks 4–13** | GPU execution, attention performance, vLLM source trace, scheduling, a bounded change, serving, and the Mac-to-cluster boundary. [See every week's contract](learn/inference-systems-13w.md#weekly-route). |

## Repair a prerequisite

The [ten-module ground-up curriculum](learn/curriculum.md) and its
[ordered lessons](learn/README.md#i-want-to-learn-ml-from-scratch) teach the
smallest missing concept. The session file numbers reflect creation order,
not reading order. Use the [coverage map](learn/coverage-map.md) to locate a
  specific subsystem. A prerequisite repair can be selected in the same
  browser workspace while preserving the sprint draft.

## Explore after the current task

- [Practical paths and buildable artifacts](learn/artifact-journey.md) connect
  concepts to repository labs and mastery gates.
- [Learning library](learn/README.md) groups modern LLM mechanics, interview
  maps, Mac-local findings, and session-specific decisions.
- [Document library map](library.md) separates reference, factory contracts,
  evidence, and historical material across the full corpus.
- [Legacy Python/WASM/WebGPU walkthrough](learn/legacy-walkthrough.md) remains
  available as a historical guided tour; it is not the current learning queue.
