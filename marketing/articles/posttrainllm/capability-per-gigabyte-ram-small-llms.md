# Measuring Model Capability Per Gigabyte of RAM: Beyond Parameter Chasing

**Slug:** `capability-per-gigabyte-ram-small-llms`
**Target Query:** capability per gigabyte ram small llms
**Search Intent:** Informational / Thought Leadership & Engineering Practice. System engineers, local AI developers, and hardware-constrained practitioners seeking cost-efficient LLM deployment strategies based on capability density (% frontier capability per GB RAM) rather than raw parameter count.
**Meta Title:** Capability Density: Measuring LLM Performance Per Gigabyte of RAM
**Meta Description:** Stop chasing model size. Learn how to evaluate local LLMs using capability per GB of RAM, active parameter efficiency, and hardware-aware density metrics.

---

## Outline

1. **Introduction: The Parameter Count Paradigm Trap**
   - The fallacy of judging AI models strictly by parameter volume.
   - The economic and physical realities of local execution on unified memory.
2. **The Core Metric: % Frontier Capability Retained Per Unit of RAM / Compute**
   - Defining Capability Density: Why frontier models are calibration anchors, not competitors.
   - The physics of Apple Silicon Unified Memory Architecture (UMA) and Peak RSS.
3. **Active Parameter Efficiency: MoE and Distillation Case Studies**
   - Sparse Active Parameters: How Qwen3-30B-A3B matches frontier multi-call tool performance with only ~3B active parameters.
   - Distilled Small Models: Compressing 4B capabilities into 1.7B and 0.6B routed specialists.
4. **On-Device Foundation Model Assessment: Apple's Foundation Models vs. Owned Weights**
   - Empirical findings from the Apple Foundation Model action-grounding probe.
   - Context window constraints (4096-token limits) and tool catalog limits.
   - Core ML as a compile target vs. platform capability dependency.
5. **Browser & WebGPU Execution Limits**
   - Evaluating WebGPU vs. WASM performance density on Apple Silicon.
   - Empirical receipts: Apple M5 Pro / Metal 3 WebGPU speedup over WASM on Large preset models.
6. **Accounting for Density in Fine-Tune Report Cards**
   - Integrating Peak RSS, TTFT, decode tok/s, and active memory overhead into decision governance.
7. **Conclusion & Engineering Recommendations**

---

## Article Content

### Introduction: The Parameter Count Paradigm Trap

For years, the open-source language model ecosystem has been driven by parameter count inflation. Benchmark leaderboards routinely highlight 70B, 120B, or 405B parameter models. However, for practitioners building applications designed to run locally on workstations, edge devices, or user laptops, raw parameter count is a misleading and expensive metric.

On hardware with fixed memory budgets—such as Apple Silicon MacBooks or embedded edge devices—every gigabyte of RAM consumed by model weights is a gigabyte unavailable for KV caching, system UI compositing, user application state, or parallel worker threads. The true engineering goal for local AI is not to train the largest possible model, but to achieve maximum **Capability Density**: maximizing task completion per gigabyte of RAM used.

When documenting capability density, it is crucial to categorize information accurately:
- **General Guidance:** System design principles for memory-constrained local execution.
- **Recipe Contracts:** Resource-bounded execution specs (RAM allocation limits, context window sizes, quantization precision).
- **Public Artifacts:** Specialist model packages carrying explicit memory and throughput metadata.
- **Actual Runs:** Hardware-measured empirical benchmarks (Peak RSS, tok/s, TTFT) from local test harnesses.

---

### The Core Metric: % Frontier Capability Retained Per Unit of RAM

Instead of treating frontier models (such as Claude 3.5 Sonnet or GPT-4o / Codex) as rivals to beat locally, local LLM architecture treats them as **calibration anchors**. The headline metric for local model efficiency is defined as:

$$\text{Capability Density} = \frac{\% \text{ Frontier Capability Retained}}{\text{Peak RAM / Memory Footprint (GB)}}$$

```text
               ┌─────────────────────────────────────────────────────────┐
               │              Frontier Calibration Anchor                │
               │                   (~100% Benchmark Ceiling)             │
               └────────────────────────────┬────────────────────────────┘
                                            │
                                            ▼
               ┌─────────────────────────────────────────────────────────┐
               │           Mac-Local Candidate Measurement              │
               │   Score: % Frontier Retained  │  Footprint: Peak RSS GB │
               └────────────────────────────┬────────────────────────────┘
                                            │
                                            ▼
               ┌─────────────────────────────────────────────────────────┐
               │    Capability Density = % Retained / Peak RSS (GB)      │
               └─────────────────────────────────────────────────────────┘
```

#### The Physics of Unified Memory Architecture (UMA)
Apple Silicon integrates CPU, GPU, and Neural Engine access into a single, high-bandwidth Unified Memory pool. While UMA eliminates PCIe transfer bottlenecks, memory pressure remains the hard ceiling for local execution.

When a model runs, its operational memory footprint consists of:
1. **Static Weight Footprint:** Model parameters loaded in memory (e.g., 4B parameters in 4-bit quantization consume ~2.5 GB).
2. **Dynamic Activation & KV Cache Footprint:** Context window memory scaling linearly or quadratically with sequence length and batch size.
3. **Peak Resident Set Size (Peak RSS):** The maximum physical RAM allocated by macOS during active inference or post-training.

If Peak RSS exceeds available system memory, macOS initiates paging to SSD swap, causing token generation rates to drop from 50+ tok/s to sub-1 tok/s.

---

### Active Parameter Efficiency: MoE and Distillation Case Studies

Achieving high capability density relies on two primary techniques: sparse active parameter execution and domain-specific knowledge distillation.

#### 1. Mixture-of-Experts (MoE) Active Efficiency
Mixture-of-Experts (MoE) architectures separate total parameter footprint from per-token compute cost. A prominent example evaluated on Mac hardware is **Qwen3-30B-A3B**:
- **Total Footprint:** ~30B parameters (~18 GB RAM in 4-bit quantization).
- **Active Parameters:** ~3B active parameters per token.
- **Empirical Performance:** On multi-turn agentic function calling (`parallel` and `parallel_multiple` tool selection), this model reaches **~96% accuracy**, matching frontier performance. By activating only ~3B parameters per forward pass, it achieves frontier-level tool selection at a fraction of the compute cost of a dense 30B model.

#### 2. Distilled Small Model Specialists
When total RAM is constrained to under 8 GB (typical for consumer MacBooks running background developer utilities), dense 1.7B and 4B models distilled from larger teachers offer extreme capability density:

| Model / Package | Active Params | Peak RSS Footprint | Target Task Depth | General Breadth | Capability Density Assessment |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen3-4B File-Ops Distilled** | 4.0B | ~4.2 GB | **100.0%** (File-Ops) | 42.3% | **High Specialist Density:** Perfect file action grounding within 4.2 GB RAM. |
| **Qwen3-4B ReST Fused** | 4.0B | ~4.2 GB | **100.0%** (File-Ops) | 55.5% | **Balanced Specialist Density:** 2.42× faster execution wall time with reduced side effects. |
| **Qwen3-0.6B SQL Specialist** | 0.6B | ~1.1 GB | **92.0%** (SQL Exec) | 38.0% | **Extreme Footprint Efficiency:** High single-domain execution accuracy in ~1.1 GB RAM. |

---

### On-Device Foundation Model Assessment: Apple FM vs. Owned Weights

A key question for macOS developers is whether to rely on Apple's built-in on-device Foundation Models (exposed via system APIs) or deploy owned model weights (e.g., Qwen or Gemma variants running over local MLX/Metal engines).

Empirical probing of Apple's on-device Foundation Model (`scripts/fm_agent_bridge.swift`) revealed severe capability density limitations:

```text
[ Task: Action Grounding / Tool Calling ]
 ├── Apple On-Device Foundation Model ──> BFCL Agentic: 25% (Full) / ~0% (Compact) ──> Context Ceiling: 4,096 tokens
 └── Owned Qwen3-4B Specialist (MLX)  ──> BFCL Agentic: 85%+              ──> Context Ceiling: 32,768+ tokens
```

#### Key Empirical Findings:
1. **Action-Grounding Failure:** Apple's on-device model achieved only **25%** on full-catalog BFCL agentic tool selection and **~0%** on compact tool selections. On planner action-grounding tasks, it scored **13%**.
2. **Context Window Bottleneck:** The built-in model's strict 4,096-token context window cannot hold a realistic developer tool catalog alongside multi-turn conversation history.
3. **Execution Speed:** The system model did not generate tokens significantly faster than a dedicated, 4-bit quantized 4B model running on MLX.

**Strategic Principle:** Own the model; do not depend on system runtime models for core application capabilities. Treat system models strictly as free routing floors. Core ML compilation of owned weights remains an optional future battery optimization target, not a capability dependency.

---

### Browser & WebGPU Execution Limits

Capability density also governs in-browser AI execution. When running client-side models via WASM or WebGPU, memory allocation limits and browser sandboxing create strict operational boundaries.

Empirical ABBA benchmark measurements on an Apple M5 Pro / Metal 3 setup using the posttrainllm browser runtime provided concrete proof of WebGPU capability density:
- **Model Preset:** Large preset model.
- **Execution Speedup:** WebGPU achieved a **10.67× median speedup** over WASM SIMD execution.
- **Numerical Fidelity:** Final loss drift between WebGPU and WASM stayed under **4.72%** with zero runtime allocation errors.

However, browser WASM runtimes encounter severe Memory64 Out-Of-Bounds (OOB) allocation failures when attempting to load models above 2B parameters without custom shared-memory growth handlers.

---

### Accounting for Density in Fine-Tune Report Cards

To enforce capability density in local deployment, every model fine-tuning run must emit a standardized Fine-Tune Report Card (`report-card.json`). The report card mandates tracking resource utilization alongside accuracy metrics:

```json
{
  "artifact_name": "qwen3-4b-rest-fused",
  "decision": "routed-ship",
  "metrics": {
    "target_depth_score": 1.00,
    "general_breadth_score": 0.555,
    "peak_rss_bytes": 4509715456,
    "decode_tok_per_sec": 42.5,
    "time_to_first_token_ms": 112.4
  },
  "measurement_states": {
    "peak_rss_bytes": "measured",
    "decode_tok_per_sec": "measured"
  }
}
```

If a candidate model increases RAM consumption by 300% (e.g., jumping from 4B to 14B parameters) while improving target task accuracy by only 2%, the capability density decreases—justifying a `reject` or `routed-ship` decision in favor of the smaller, higher-density model.

---

### Internal-Link Suggestions

- Review complete hardware and model experiment records in [`docs/attempt-ledger.md`](../../../docs/attempt-ledger.md).
- Read the Apple Foundation Model empirical evaluation report in [`docs/learn/apple-on-device-foundation-models.md`](../../../docs/learn/apple-on-device-foundation-models.md).
- Examine local model serving and RAM accounting in [`docs/factory/report-card.md`](../../../docs/factory/report-card.md).
- Explore local tool-calling density strategies in [`docs/learn/small-model-tool-calling-playbook.md`](../../../docs/learn/small-model-tool-calling-playbook.md).

---

### Clear Next Action

To measure capability density for your local models:
1. Measure your base model's baseline Peak RSS and decode throughput using `posttrainllm serve --metrics`.
2. Evaluate target task depth and out-of-domain breadth on your 1.7B or 4B candidate.
3. Compute the capability density ratio (% frontier capability retained per GB of Peak RSS).
4. Build a fine-tune report card using `python3 scripts/factory/build_fine_tune_report_card.py`.
5. Select the smallest, highest-density candidate that satisfies your application's task-completion threshold.

---

### Source Notes (Non-Publishable)

*Supporting repository files:*
- `AGENTS.md` (Eval philosophy, capability density definition, Qwen3-30B-A3B active parameter analysis, Apple FM probe findings).
- `PRODUCT.md` (Product principles, local bounded workflow defaults).
- `PROJECT_STATUS.md` (Specialist package records, WebGPU M5 Pro Large preset ABBA benchmark receipt).
- `docs/learn/apple-on-device-foundation-models.md` (Complete empirical probe report on Apple's Foundation Models).
- `docs/attempt-ledger.md` (Recorded RAM, Peak RSS, and speed metrics across 76 attempts).

*Limitations & Scope Boundary:*
- Review-only draft. No code, configuration, or website routes were modified.
- All hardware measurements, RAM footprints, and model accuracy benchmarks reflect retained empirical evidence without external extrapolation or fabrication.
