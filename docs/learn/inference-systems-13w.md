---
title: Inference systems — 13-week owner sprint
description: 28 September–27 December 2026 route through transformer mechanics, measurement, kernels, serving, and the single-device-to-cluster boundary.
---

# Inference systems — 13 weeks

This is the owner's **active inference-systems sprint**, starting
**28 September 2026** and running through **27 December 2026**: 13 seven-day
weeks at **up to 20 focused hours each** (260 hours total). The remaining
December days are buffer or review time, not a fourteenth week. Reading, recall,
implementation, debugging, and explanation all count toward each 20-hour cap.

Open the single [Next Session](../learning-progress.md#next-session) for the
current exercise. This page is the route and evidence contract, not another
progress tracker. The [ten-module curriculum](curriculum.md) remains the
foundation and remediation path. The broader factory, artifacts, and learning
paths remain available. Session filenames are creation order: Session 9 teaches
tensors before Session 6's embedding work and Session 10's attention work.

The outcome is an independent explanation of a transformer forward pass, a
prediction of time and memory behavior, measured bottleneck diagnosis, a
source-level inference-engine trace, a tested bounded change, and a defense
on an unfamiliar workload. A read article, generated implementation, or passed
automated check alone is not evidence of owner mastery.

## Entry and prerequisite gate

Before reading the answer-bearing sections, write your own answers in the
[checkpoint](../learning-progress.md#checkpoints-and-recall-queue):

1. For `y = w·x + b`, with `x = [2, 3]`, `w = [4, -1]`, `b = 2`, identify the
   input, parameters, intermediate dot product, and output. Calculate it.
2. A batch has shape `(2, 4, 3)` and a linear map has three input features and
   five output features. Predict the output shape, naming each axis.
3. In a one-layer causal decoder, which positions may influence the output at
   position 2? Distinguish training from inference and explain where loss and
   gradients enter (or do not enter) the forward pass.

Check the arithmetic and shapes only after recording the attempt, using
[Session 9's dot-product and shape sections](session-09-tensors.md#the-one-operation-that-matters-the-dot-product)
and [Session 10's causal mask](session-10-attention.md#causal-masking--no-peeking-at-the-future).
If a part fails, study only the smallest missing foundation: [parameters](session-01-neural-net-basics.md),
[loss and gradients](session-02-gradient-descent.md),
[nonlinearity](session-03-non-linearities.md),
[tensors](session-09-tensors.md), or [attention](session-10-attention.md).
Retry with changed numbers before moving on. A previous `reading` status does
not imply either a pass or a failure.

## Weekly route

Each row names the prerequisite, source, exercise, prediction, check,
independent explanation, repo connection, and hardware. Expand a later row
into exact commands only when its week begins; pin external code and budgets
then. `Source review` is never reported as execution.

| Week / dates | Contract and required evidence |
|---|---|
| **1 · Sep 28–Oct 4** | **Forward path and initial baseline.** After the entry gate, read the selected [tensor](session-09-tensors.md), [embedding](session-06-tokenization-embeddings.md), [attention](session-10-attention.md), and [mechanics](llm-mechanics-fundamentals.md) sections below. Predict shapes and causal influence before the CPU lab; save the exact source revision, config, output, annotated tensor trace, and your explanation. See the full contract below. |
| **2 · Oct 5–11** | **Autoregressive generation, prefill/decode, KV cache.** Requires Week 1's forward trace. Read [KV/cache sections](advanced-llm-inference.md#memory--scheduling) and inspect `python_ref/model.py`'s `generate`. Predict cache bytes for declared layers, KV heads, head dimension, context, batch, precision; compare cached and uncached output and context lengths only after choosing a verified implementation. Explain why prefill and decode have different work. Mac CPU/source review first; no unverified cached path is claimed here. |
| **3 · Oct 12–18** | **Measurement.** Requires Week 2's phase model. Read [serving metrics](advanced-llm-inference.md#fundamentals) and [benchmark design](../performance/benchmark_harness_design.md). Declare timing boundary, warmup, device, batch, precision, prompts, repetitions, and memory method before measuring TTFT, inter-token latency, throughput, and memory in an existing harness. Predict bottleneck, compare observed values, and explain variance. Mac-local; inspect/extend the harness only if its current commands pass an audit. |
| **4 · Oct 19–25** | **GPU execution and introductory CUDA/Triton.** Requires Week 3's measurement discipline. Read the [kernel path](advanced-llm-inference.md#curated-deep-reading-path); draw grid/block/warp and memory-access diagrams, then predict correctness and timing for vector add and fused softmax. Check against a reference and document launch shape and memory traffic. Explain coalescing and fusion. Source analysis is Mac-compatible; CUDA execution needs a separately approved NVIDIA environment, pinned dependencies, and cost cap. The CUDA execution gate remains pending until run there. |
| **5 · Oct 26–Nov 1** | **Attention performance.** Requires Weeks 1 and 4 concepts. Read [attention](session-10-attention.md) and [FlashAttention's IO argument](https://arxiv.org/abs/2205.14135). Predict traffic for declared sequence/head shapes; compare reference and optimized paths with declared tolerance and timing boundary. Explain tiling and why a mathematically equal path can have different memory cost. Use an available Mac reference/optimized pair for execution; NVIDIA-specific claims require NVIDIA execution. |
| **6 · Nov 2–8** | **Trace vLLM end to end.** Requires cache and scheduling vocabulary. Pin a vLLM source revision before reading; trace one request through input, scheduler, model execution, KV ownership, and output using code links. Predict state transitions, then check the source trace. Explain where latency accumulates. [Inside vLLM](../industry_learning_roadmap.md#case-study---inside-vllm-inference-systems-and-scaling-boundaries) is orientation; Mac source review is sufficient this week. |
| **7 · Nov 9–15** | **Scheduling and KV ownership.** Requires Week 6's trace. Hand-simulate three request arrivals and cache allocations, predict queue/cache effects of one scheduling choice, then inspect or measure that choice at the pinned revision. Explain eviction, fragmentation, and fairness. Label a simulation separately from a runtime measurement; no cloud resource is implicit. |
| **8 · Nov 16–22** | **One bounded runtime change.** Requires a reproducible Week 7 baseline. State the failure case and acceptance threshold; make one reviewable patch with correctness tests and controlled before/after on the same declared workload. Predict benefit and regressions first; explain observed mechanism. This is a learning patch, subject to its target repository's own contribution rules; no publication is implied. |
| **9 · Nov 23–29** | **Serving behavior.** Requires a tested runtime and measurement boundaries. Define request mix and service target, predict queueing versus model-time behavior, then measure latency/throughput and diagnose misses. Explain which scheduling change would help and what it would harm. Use a local simulator or available runtime; distinguish either from production service evidence. |
| **10 · Nov 30–Dec 6** | **Single-device-to-multi-GPU boundary.** Requires the earlier memory model. Use [parallelism and inference economics](advanced-llm-inference.md#serving-architecture) to predict parameter/KV memory, communication volume, and topology effects for a declared model and workload. Check algebra and source design; explain which limit one Mac cannot remove. A topology design is not a multi-GPU benchmark. |
| **11 · Dec 7–13** | **Capstone investigation.** Requires reproducible Weeks 8–10 evidence. State one falsifiable performance hypothesis, frozen workload and regression metrics, bounded intervention, and stop rule. Predict the result, implement and retain raw logs plus environment/revision. Explain causal alternatives. Hardware and time budget must be declared before any run. |
| **12 · Dec 14–20** | **Capstone review.** Reproduce Week 11 on the same conditions, then try changed workloads. Predict where the gain should fail; report regressions, variance, costs, and limits, and defend ship/reject/redo. Raw evidence and your own explanation are required; one good trace is insufficient. |
| **13 · Dec 21–27** | **Unfamiliar-problem assessment.** Given a new bottleneck or correctness failure, write assumptions, a predicted cause, diagnostic plan, and next test before inspecting results. Check on a changed workload and defend the conclusion without copying the capstone solution. A reviewer may prepare the prompt, but the owner supplies the reasoning and evidence. |

## Week 1: full session contract

**Objective:** trace the reference decoder from token IDs to logits, predict
shapes and causal influence, and capture one reproducible CPU baseline.

**Required sections:** [Session 9: dot product, matrix–vector, batch/sequence](session-09-tensors.md#the-one-operation-that-matters-the-dot-product),
[Session 6: embedding layer and tied output](session-06-tokenization-embeddings.md#from-tokens-to-vectors-the-embedding-layer),
[Session 10: Q/K/V, causal mask, transformer block](session-10-attention.md#query-key-value--the-three-roles),
and [mechanics: full trace](llm-mechanics-fundamentals.md#the-full-trace).
Read `configs/model.byte-tinygpt-v0.json` and `python_ref/model.py` at the
current revision. The config and code, not this page, own the model dimensions.

**Prediction before execution:** write the `(batch, sequence, width)` shape
after the token embedding; the Q/K/V and attention-score shapes per head;
the logits shape; whether changing the final input token can alter earlier
positions' logits; and whether changing an earlier input token can alter the
last position's logits. Label inputs, parameters, intermediate activations,
and outputs. Keep weights fixed.

**CPU lab, from repo root:** use the existing Python-reference dependencies in
an isolated environment (`python_ref/requirements.txt`); no GPU is needed.
Do not install PyTorch or start a long run just to read the lesson. When the
dependency is available, run:

```bash
git rev-parse HEAD
python3 -c 'import torch; print(torch.__version__)'
python3 scripts/learning/inference_week1.py
```

If using the repo's `.venv`, substitute `.venv/bin/python` for `python3` on
the last two lines. Save the raw JSON with the revision and environment in a
dated checkpoint. The script performs one timed forward and two changed-input
forwards on CPU. Its single timing is **an initial baseline smoke**, not a
stable throughput estimate; Week 3 owns controlled performance measurement.
It checks shapes and future-token isolation but cannot judge your reasoning.

**Independent explanation:** trace IDs → token lookup and learned position
lookup → Q/K/V → mask → attention output → MLP → final normalization → tied
output head. Explain why a changed earlier token may change a later output,
why a changed future token must leave earlier outputs unchanged, and why
embedding lookup is mathematically expressible as one-hot multiplication but
implemented as indexing here. Point to the corresponding lines in
`python_ref/model.py`.

**Expected checks:** the lab prints `checks: passed`, expected tensor shapes,
parameter count, and both changed-input deltas. A failed assertion is a
correctness or environment issue to investigate; it is never papered over.
The annotated trace, the saved raw output, and the owner's explanation are
separate evidence. Use [the Learning Loop](../learning-progress.md#learning-loop)
for the immediate gate and actual +2/+7-day recall dates. Week 2 is eligible
after Week 1's immediate gate, even while delayed checks are pending.

**First two-hour session:** 10 minutes entry gate; 25 minutes selected tensor
and embedding sections; 55 minutes prediction plus embedding/output-head and
reference trace; 20 minutes causal-attention example; 10 minutes save the
owner's explanation and actual evidence. If the entry gate fails, replace
the lab time with the smallest remediation lesson and changed-number retry.
The full Week 1 trace and baseline are week deliverables, not prerequisites
to ending the first lesson.

## Hardware and evidence boundary

This Mac can run the CPU/PyTorch Week 1 lab and Mac-local source/serving work
when dependencies are present. Mac/MLX/WebGPU work teaches transferable
concepts; it does not satisfy a **NVIDIA CUDA execution** gate. For Week 4,
select a CUDA-capable NVIDIA host, pin CUDA/PyTorch/Triton versions and exact
commands against that host, and get an approved compute/cost budget before
running. If unavailable, complete and label the theory/source analysis while
leaving execution pending. No paid compute, model download, or heavy training
is authorized by this route. Reading source and executing it are separate
claims. See [NVIDIA CUDA requirements](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/index.html).
