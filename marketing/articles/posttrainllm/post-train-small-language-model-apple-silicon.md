# How to Post-Train a Small Language Model on Apple Silicon

**Slug:** `post-train-small-language-model-apple-silicon`
**Target Query:** post train small language model apple silicon
**Search Intent:** Informational / Practical Developer Guide. Developers and ML practitioners seeking to adapt and fine-tune small open models (0.6B to 4B parameters) locally on Apple Silicon Macs using native frameworks like MLX and PyTorch (MPS) without cloud GPUs.
**Meta Title:** Post-Train Small Language Models on Apple Silicon: Local Workflow Guide
**Meta Description:** Learn how to post-train 0.6B–4B language models locally on Apple Silicon using LoRA, MPS, and MLX. Includes real run data, factory loops, and hardware constraints.

---

## Outline

1. **Introduction: Local Post-Training on Apple Silicon**
   - The shifting landscape: why local post-training on Mac hardware matters.
   - The unified memory advantage and single-host compute boundaries.
2. **The Local Post-Training Factory Loop**
   - Defining the six-stage loop: Target -> Data -> Post-Training -> Eval -> Package -> Report.
   - Distinguishing general adaptation guidance from reproducible recipe contracts.
3. **Execution Runtimes: Swift/MLX vs. Python/PyTorch (MPS)**
   - Native Mac runtime execution (`posttrainllm` Swift CLI over MLX).
   - Python reference paths and hand-rolled PyTorch MPS LoRA injection.
   - Managing host stability and cooperative GPU locks (`gpu.lock`).
4. **Post-Training Techniques on Mac Hardware**
   - Supervised Fine-Tuning (SFT) with rank-4 and rank-8 Low-Rank Adaptation (LoRA/DoRA).
   - Direct Preference Optimization (DPO) and reference-anchoring vs. SimPO policy collapse.
   - Distillation strategies: distilling multi-turn tool calling into small base models.
5. **Real Local Runs, Artifacts, and Lessons Learned**
   - Case study 1: `qwen3-4b-file-ops-distilled` (file operations depth vs. out-of-domain breadth).
   - Case study 2: `qwen06-sql-hygiene-dpo-v1` (format hygiene vs. base model prose priors).
   - Case study 3: FLAN-T5-small encoder-decoder adapter pilot (overcorrection failure mode).
6. **Hardware Constraints and Performance Realities**
   - Memory allocation, Peak RSS, and unified bandwidth limits.
   - Why low training loss does not guarantee task-completion capability.
7. **Conclusion & Practical Action Plan**

---

## Article Content

### Introduction: Local Post-Training on Apple Silicon

Adapting small language models (0.6B to 4B parameters) on local hardware has transitioned from a novelty to a practical engineering discipline. Apple Silicon's Unified Memory Architecture (UMA) gives a single workstation high-bandwidth shared memory across CPU and GPU cores, enabling local execution of training, preference alignment, and evaluation loops that previously required cloud GPU instances.

However, training on a Mac requires a shift in mindset. You are not competing with multi-node clusters or frontier-scale pre-training. Instead, the goal is domain specialization: taking a general small base model—such as Qwen3-0.6B, Qwen3-4B, or FLAN-T5-small—and post-training it to reliably execute structured tasks, tool calls, or domain-specific queries within strict RAM and latency budgets.

Understanding local post-training requires distinguishing four distinct categories of information:
- **General Guidance:** Architectural principles and workflow patterns.
- **Recipe Contracts:** Fixed, versioned parameters (learning rate, rank, batch size, stop rules).
- **Public Artifacts:** Packaged, inspectable weights and metadata output from a run.
- **Actual Runs:** Empirical benchmark results and failure analysis from real local executions.

---

### The Local Post-Training Factory Loop

A structured post-training workflow relies on a closed evidence loop rather than ad-hoc parameter tweaks. Every local experiment follows a deterministic sequence:

```text
target -> data -> post-training -> eval -> package -> report
```

1. **Target:** Define a single task or domain (e.g., SQL generation or file-system action grounding) alongside explicit pass/fail criteria before touching weights.
2. **Data:** Prepare cleaned train and held-out evaluation splits. Data cleanliness and format alignment take precedence over raw token volume.
3. **Post-Training:** Apply Supervised Fine-Tuning (SFT), Direct Preference Optimization (DPO), or Distillation using a parameter-efficient adapter recipe.
4. **Eval:** Measure candidate performance against a frozen baseline across both targeted depth and out-of-domain regression suites.
5. **Package:** Export weights into standardized formats (MLX adapters, safetensors, or GGUF) with embedded provenance metadata.
6. **Report:** Generate an immutable before-and-after report card documenting score delta, latency, peak memory (Peak RSS), and the terminal decision (`ship`, `routed-ship`, `retry-data`, or `reject`).

---

### Execution Runtimes: Swift/MLX vs. Python/PyTorch (MPS)

On macOS, developers typically choose between two execution environments for post-training:

#### 1. Native Swift/MLX Runtime
The MLX framework, integrated into native Swift command-line tools (`posttrainllm`), offers direct interaction with Metal performance primitives. Swift/MLX runtimes deliver low cold-start latency and efficient memory reuse during low-rank adaptation. Commands like `posttrainllm sft` or `posttrainllm dpo` operate natively against Apple Silicon GPU pipelines without Python process overhead.

#### 2. Python / PyTorch (MPS) Reference Paths
For custom architectures or research experiments (such as encoder-decoder models), PyTorch with the Metal Performance Shaders (`mps`) backend provides flexibility. When hand-rolling Low-Rank Adaptation (LoRA) modules—such as injecting adapter matrices $A$ and $B$ into attention projection layers ($Q, K, V$)—using PyTorch MPS enables step-by-step gradient inspection and loss tracing.

#### Host Protection & Resource Management
Heavy GPU compute loops on macOS can cause WindowServer responsiveness issues if unconstrained. Local post-training workflows must use process lockfiles (e.g., `~/.cache/posttrainllm/gpu.lock`) to prevent concurrent GPU workloads from colliding, while setting cooperative batch sizes to maintain system stability.

---

### Post-Training Techniques on Mac Hardware

#### Parameter-Efficient Adaptation (LoRA & DoRA)
Full parameter fine-tuning of even a 4B model on local hardware consumes significant memory due to optimizer state overhead (AdamW requires 8 bytes per parameter for momentum and variance buffers alone). Parameter-Efficient Fine-Tuning (PEFT) techniques like Low-Rank Adaptation (LoRA) and Weight-Decomposed Low-Rank Adaptation (DoRA) restrict trainable parameters to low-rank decomposition matrices ($r=4$ or $r=8$) injected into key projections (`q_proj`, `v_proj`). On a 0.6B parameter base model, a rank-4 LoRA adapter adds fewer than 500,000 trainable parameters (<0.1% of base size), keeping peak memory usage well under 2 GB during training.

#### Preference Alignment: DPO vs. SimPO
When refining model formatting or output tone, Direct Preference Optimization (DPO) aligns model generation against preferred and dispreferred pairs without training a separate reward model.

Local experiments highlight a critical stability distinction between preference loss formulations:
- **Reference-Free Loss (SimPO):** Removing the reference model anchor during preference updates can cause severe policy collapse on small models. In local SQL hygiene experiments on Qwen3-0.6B, reference-free SimPO caused execution accuracy to plummet from 86.0% to 8.0%, resulting in repetitive fence and prose outputs.
- **Reference-Anchored DPO:** Maintaining a frozen reference model anchor ($\beta=0.1$ to $0.3$) stabilizes updates. On the same Qwen3-0.6B target, reference-anchored DPO preserved and enhanced execution accuracy (rising from 86.0% to 92.0%).

#### Knowledge Distillation
For complex reasoning or multi-turn tool execution, direct SFT on small models often hits capacity limits. Distillation—training a small student model on high-quality action trajectories generated by larger teacher models (or frontier APIs)—enables small models to learn structured output conventions that would otherwise require multi-billion parameter capacity.

---

### Real Local Runs, Artifacts, and Lessons Learned

Local post-training produces concrete empirical evidence. Reviewing actual runs recorded in posttrainllm reveals key lessons:

#### Case Study 1: `qwen3-4b-file-ops-distilled` (Routed Specialist Win)
- **Objective:** Improve file-operation tool-calling accuracy on a 4B parameter model.
- **Result:** Distillation improved file-operations hard gate task completion from 58.0% to 100.0%.
- **Regression Check:** Out-of-domain general planning breadth regressed from 59.6% down to 42.3%.
- **Decision:** Released as a `routed-ship` specialist artifact. The model is deployed exclusively behind a file-ops route; it is explicitly rejected as a general planner replacement.

#### Case Study 2: `qwen06-sql-hygiene-dpo-v1` (Format Prior Limitations)
- **Objective:** Suppress unwanted prose wrappers (e.g., `Answer: ...`) around SQL SELECT statements on Qwen3-0.6B.
- **Result:** Higher-pressure reference-anchored DPO ($\beta=0.3$, 200 steps) successfully minimized preference loss ($0.6931 \to 0.0073$) and boosted inner SQL execution from 86.0% to 92.0%. However, greedy generation still retained the prose wrapper (`clean-SQL` raw rate remained at 0.000).
- **Decision:** `retry-data`. Diagnosis revealed that the base model's strong prose prior could not be erased by rank-4 preference adapters alone when SFT targets were already clean. Format hygiene required generation-time constrained sampling or stronger initial SFT rather than preference updates.

#### Case Study 3: FLAN-T5-Small Autocorrect Pilot (Overcorrection Failure)
- **Objective:** Train an encoder-decoder model (FLAN-T5-small, 60M parameters) for text error correction using hand-rolled PyTorch MPS LoRA.
- **Result:** Ordinary sequence loss over 50 steps caused negative error reduction (+0.0625 to -0.8125). The adapter transformed from a subtle error corrector into an aggressive paraphraser (e.g., changing `remeber` to `remind you` rather than `remember`).
- **Lesson:** Sequence loss alone on thin datasets fails to enforce minimum-edit distance constraints.

---

### Hardware Constraints and Performance Realities

When post-training on Apple Silicon, hardware metrics directly govern viability:

| Parameter Count | Quantization / Format | Peak Training RSS | Decode Speed (M5 Pro / M3) | Typical Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **0.6B** | BF16 / Float32 | ~1.1 GB – 1.8 GB | ~120 – 180 tok/s | Fast local router, bare SQL, single-intent classifiers |
| **1.7B** | BF16 / Q4_K_M | ~2.5 GB – 4.0 GB | ~60 – 90 tok/s | Single-turn tool calling, structured JSON extraction |
| **4.0B** | BF16 / Q4_0 | ~5.5 GB – 9.0 GB | ~30 – 50 tok/s | Multi-turn agentic planning, routed specialists |

Key hardware lessons:
1. **Low Loss $\neq$ High Capability:** Training loss reaching near-zero (e.g., 0.001) often indicates memorization rather than generalization.
2. **Unified Memory Headroom:** Always reserve at least 20–30% of system RAM for macOS WindowServer and buffer caches to prevent thermal throttling or page swapping.

---

### Internal-Link Suggestions

- Read the complete experiment history in [`docs/attempt-ledger.md`](../../../docs/attempt-ledger.md) and [`docs/attempts.json`](../../../docs/attempts.json).
- Review the specialist factory methodology in [`docs/factory/run-schema.md`](../../../docs/factory/run-schema.md).
- Examine encoder-decoder adapter implementation details in [`docs/learn/encoder-decoder-adapters.md`](../../../docs/learn/encoder-decoder-adapters.md).
- Explore local evaluation criteria in [`docs/factory/report-card.md`](../../../docs/factory/report-card.md).

---

### Clear Next Action

To run your own local post-training experiment on Apple Silicon:
1. Clone the repository and build the native CLI using `swift build -c release`.
2. Prepare a paired dataset following the run schema contract in `docs/factory/run-schema.md`.
3. Freeze your evaluation baseline before initiating training.
4. Execute `posttrainllm sft` with a low-rank adapter config ($r=4$ or $r=8$).
5. Run `posttrainllm eval-gate` to generate an immutable report card before deciding whether to ship or retry.

---

### Source Notes (Non-Publishable)

*Supporting repository files:*
- `AGENTS.md` (Operating rules, Apple Silicon north-star goals, eval philosophy).
- `PROJECT_STATUS.md` (Current state, verified wins, specialist package records).
- `docs/attempt-ledger.md` (Full history of 76 experiment dispositions).
- `native-mac/Sources/TinyGPT/` (Native Swift/MLX CLI implementations).
- `scripts/research/autocorrect_adapter.py` (Hand-rolled PyTorch MPS encoder-decoder LoRA path).
- `evals/autocorrect/adapter-recipe-v1.json` (FLAN-T5-small recipe contract).
- `specialists/qwen3-4b-file-ops-distilled` & `specialists/qwen3-4b-rest-fused` (Registered specialist packages).

*Limitations & Scope Boundary:*
- Review-only draft. No production code, configuration, or website routing files were modified.
- All hardware speed metrics and model results reflect retained repository empirical evidence without fabrication or external extrapolation.
