---
title: The buildable AI journey
description: A nine-stage journey from transformer foundations to local specialist models, agents, packages, runtime decisions, and causal probes.
---

# The buildable AI journey

PostTrainLLM is designed to teach ML, AI, and language-model systems by making
the learner produce things. Every stage ends in an artifact that can be built,
modified, tuned, evaluated, and packaged on hardware the learner controls.

The machine-readable source of truth is
[`artifact-journey.json`](artifact-journey.json). The public [`/learn`](/learn)
surface renders the same contract alongside the nine learning paths.

## How to read readiness

- **Runnable lab** — an existing bounded local or browser implementation.
- **Guided replay** — a reconstruction of retained evidence, not a claim that a
  fresh run happened.
- **Recipe contract** — a complete procedure whose expensive execution begins
  only as a fresh, explicitly budgeted experiment.

That distinction matters. Reading a result, reproducing a result, and running a
new experiment are different activities and should never be presented as the
same proof.

## The journey

| Stage | Learning path | Artifacts produced |
|---:|---|---|
| 1 | Foundations | `byte-tinygpt`, `browser-tinygpt` |
| 2 | Training mechanics | `tiny-overfit-receipt` |
| 3 | Post-training | `lora-specialist`, `distilled-tool-caller` |
| 4 | Evaluation and factory | `needle-selection-ruler`, `factory-report-card` |
| 5 | Runtime and agents | `local-tool-agent` |
| 6 | Architecture and kernels | `kernel-parity-receipt` |
| 7 | Quantization and packaging | `mlx-specialist-package` |
| 8 | Browser and Mac runtime | `browser-asr-case`, `mac-runtime-boundary-map` |
| 9 | Interpretability | `causal-probe-dossier` |

The order is conceptual, not a demand to run every expensive workload. A
learner can complete a guided replay, understand its limits, and defer a fresh
training or kernel run until they choose a target and budget.

## The five-action artifact contract

Every registered artifact answers five questions:

1. **Build** — what is assembled or run?
2. **Modify** — which source, data, policy, or configuration can change?
3. **Tune** — which parameters are legitimate experimental variables?
4. **Prove** — which correctness, capability, regression, and resource checks
   decide whether the change helped?
5. **Package** — what must travel with the result so another person can inspect,
   reproduce, or safely use it?

An artifact is incomplete if it is only a model file, screenshot, metric, or
code sample. Its inputs, configuration, evidence, limitations, and decision are
part of the thing being learned.

## Completion rule

The repository completion check validates that stage IDs and orders are unique,
prerequisites resolve without cycles, all nine learning paths are represented,
every action and anchor resolves, CLI commands exist in the discovery catalog,
and the public learning surface imports this registry. This makes the journey a
maintained product contract rather than an aspirational roadmap.
