# Industry learning roadmap

This is the external learning track for posttrainllm. Use it alongside the canonical
[`ground-up curriculum`](learn/curriculum.md) and
[`practical paths`](learn/path-registry.json). CS336 supplies external course
depth; company docs and papers supply applied case studies. External module
numbers below are independent of the ten ground-up curriculum modules.

The goal is not to copy frontier-scale infrastructure. The goal is to extract
small, testable ideas that fit posttrainllm: better data, cleaner evals, stronger
specialist training, and Mac-first runtime discipline.

## How to read

1. Read the source.
2. Write the one sentence lesson.
3. Map it to a posttrainllm artifact: code, doc, eval, or explicit skip.
4. Record a learning checkpoint in [`learning-progress.md`](learning-progress.md).
5. Start implementation only after the owner opens a fresh, scoped question under
   [`NEXT.md`](NEXT.md). Historical actions below are retained study context,
   not an active queue or authorization for downloads, training, or benchmarks.

## Module 0 - Course spine: Stanford CS336

Source: [Stanford CS336 - Language Modeling from Scratch](https://cs336.stanford.edu/)

Why it matters: CS336 is almost exactly posttrainllm's educational contract. It
walks through tokenizer/model/optimizer basics, systems profiling,
FlashAttention, distributed memory efficiency, scaling laws, data filtering and
deduplication, and SFT/RL-style post-training.

posttrainllm mapping:

| CS336 piece | posttrainllm anchor |
|---|---|
| Assignment 1: basics | `python_ref/`, `tests/test_phase1.py` |
| Assignment 2: systems | `wasm/`, `webgpu/`, FA2 notes |
| Assignment 3: scaling | `configs/`, `evals/`, `docs/performance/benchmark_harness_design.md` |
| Assignment 4: data | `posttrainllm download-dataset`, `dedupe`, dataset registry |
| Assignment 5: alignment/reasoning RL | `sft`, `dpo`, future RLVR/Tier 5 reasoning |

Action: add CS336 as the default external course for anyone learning the repo.
Do not import assignments wholesale; use it as a reading and audit checklist.

## Module 1 - Small model data recipes

Sources:

- [Hugging Face SmolLM blog](https://huggingface.co/blog/smollm)
- [FineWeb / FineWeb-Edu paper](https://arxiv.org/abs/2406.17557)

Lesson: small models do not win by architecture alone. They need unusually good
data: educational-quality text, code subsets, deduplication, and scale-aware
evaluation.

posttrainllm actions:

- Keep B10: quality classifier on pretrain data.
- Keep dedupe and MinHash dedupe in the default data path.
- Add every future training run to a manifest with corpus hash, filter settings,
  and eval set.

## Module 2 - Open post-training recipes

Sources:

- [Ai2 Tulu 3](https://allenai.org/tulu)
- [Tulu 3 technical blog](https://allenai.org/blog/tulu-3-technical)
- [Tulu 3 report](https://arxiv.org/abs/2411.15124)

Lesson: post-training is a recipe, not a single dataset. The useful shape is
SFT -> preference tuning -> verifiable-reward RL, with explicit data mixtures
and evaluation.

posttrainllm actions:

- Keep `docs/training/` as the canonical pretrain/SFT/DPO pipeline.
- Add held-out task evals before claiming any specialist win.
- Treat RLVR as a Tier 5 learning experiment until SFT/DPO specialists are real.

## Module 3 - Reasoning and RLVR

Source: [DeepSeek-R1 official repo/report](https://github.com/deepseek-ai/DeepSeek-R1)

Lesson: reasoning gains come from verifiable rewards and long rollouts, but
this is only meaningful after the base model and SFT path are stable.

posttrainllm actions:

- Use math/code tasks with exact checkers before any LLM judge.
- Start with GRPO/DAPO as mental models, not immediate production features.
- Log full trajectories, rewards, and token ids if any RL-style run happens.

## Module 4 - Agent design

Sources:

- [Anthropic - Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Mistral Agents docs](https://docs.mistral.ai/studio/agents/introduction)
- [Mistral handoffs docs](https://docs.mistral.ai/studio/agents/handoffs)

Lesson: most useful agent systems are simple workflows with good tools. Multi-
agent handoffs help only when the boundary is crisp.

posttrainllm actions:

- Prefer tool quality and eval harnesses over more agent layers.
- Keep the router/specialist boundary explicit: one specialist per task family.
- Add handoff only after one specialist can prove it should delegate.

## Module 5 - Agentic coding and eval discipline

Source: [Poolside Laguna deep dive](https://poolside.ai/blog/laguna-a-deeper-dive)

Lesson: the stealable pieces are not 30T tokens or 6,144 GPUs. They are data
mixing discipline, repeated agent evals, token-preserving trajectories, and
careful sandbox budgets.

posttrainllm actions:

- Keep B21: micro-AutoMixer for specialist data mixes.
- Keep B22: token-preserving agent trajectory recorder.
- Keep B23: repeated pass@1 agent eval protocol.
- Keep B24: Muon only after a large/proxy-scale re-benchmark.

## Module 6 - Evals as product infrastructure

Sources:

- [OpenAI Evals cookbook](https://cookbook.openai.com/examples/evaluation/getting_started_with_openai_evals)
- [OpenAI structured-output eval example](https://cookbook.openai.com/examples/evaluation/use-cases/structured-outputs-evaluation)
- [OpenAI Model Spec evals note](https://openai.com/index/our-approach-to-the-model-spec/)

Lesson: evals should be scenario-shaped and rubric-shaped, not just aggregate
leaderboard numbers. Structured-output tasks need schema validity plus semantic
grading.

posttrainllm actions:

- Add custom evals for each specialist before training the specialist.
- For JSON/tool/storyboard outputs, score both schema validity and task success.
- Keep public benchmark scores separate from repo-local product evals.

## Module 7 - General foundation model reports

Sources:

- [Meta Llama 3 Herd of Models](https://ai.meta.com/research/publications/the-llama-3-herd-of-models/)
- [Qwen docs: key concepts](https://qwen.readthedocs.io/en/latest/getting_started/concepts.html)

Lesson: foundation-model reports are useful for phase structure, eval breadth,
tokenizer and multilingual choices, and safety/post-training taxonomy. They are
not directly actionable at posttrainllm scale.

posttrainllm actions:

- Read these for vocabulary and comparison tables.
- Do not chase 100B-scale architecture changes unless a tiny proxy can falsify
  the idea first.

## Module 8 - Mac/local runtime

Sources:

- [Apple MLX open-source project](https://opensource.apple.com/projects/mlx/)
- [Apple MLX M5 LLM research note](https://machinelearning.apple.com/research/exploring-llms-mlx-m5)

Lesson: posttrainllm's differentiator is not beating CUDA. It is making local,
inspectable model training and inference work well on Apple Silicon.

posttrainllm actions:

- Keep Mac-native MLX paths first-class.
- Measure TTFT, throughput, memory, and energy before adding runtime tricks.
- Treat CoreML/ANE/GPU changes as measured runtime work, not roadmap glamour.

## Module 9 - Specialized visual/video systems

Sources:

- [Lamina Labs](https://laminalabs.ai/)
- [Qwen Image technical direction](https://arxiv.org/abs/2605.10730) for a
  larger-scale multimodal comparison point.

Lesson: for posttrainllm, the feasible first step is a structured explainer compiler,
not pixel-native video generation.

posttrainllm actions:

- Keep Tier 5.7 scoped to prompt/doc -> script -> storyboard DSL -> deterministic
  render.
- Train a visual-planner specialist only after storyboard data and evals exist.

## Case study - Savante / Aryabhata: specialist data and evaluation

Added 2026-09-19. **Study only; local reproduction not attempted.**

Sources: [Savante](https://savante.ai/),
[Aryabhata paper](https://arxiv.org/abs/2508.08665),
[model card](https://huggingface.co/PhysicsWallahAI/Aryabhata-1.0).

Read after ground-up Modules 9–10, in the `post-training` and
`evaluation-and-factory` paths. The published recipe combines model merging,
curated reasoning traces, SFT, and verifiable-reward RL for JEE mathematics.
Use it to study how domain data and a measurable task shape specialization;
do not attribute the whole improvement to RL or treat selected historical
comparisons as current frontier parity. The reported H100 training is not
proof of Mac-local reproducibility.

Exercise: write a one-page recipe teardown separating initialization, data,
trace filtering, SFT, reward, and evaluation. Identify missing ablations,
possible leakage boundaries, and what data access a comparable specialist
would require. Map each component to the existing factory loop.

Mastery gate: explain what the evidence supports, what cannot be attributed to
one training stage, and how to freeze an independent test before adapting the
recipe to a Mac-sized target. Record the checkpoint; running it would require
a new scoped experiment with a resource budget.

## Case study - Bonsai 2 27B: capability retained per deployment cost

Added 2026-09-19. **Study only; candidate for a future bounded comparison.**

Sources: [release announcement](https://prismml.com/news/bonsai-2-27b),
[MLX model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit),
[runtime and technical report](https://github.com/PrismML-Eng/Bonsai-demo).

Read in `quantization-and-packaging`, then connect to `runtime-and-agents`.
Study ternary representation, packing overhead, activation transforms, and
kernel support. The current card distinguishes a 5.95 GB GGUF language model
from 7.67 GB MLX language weights and an 8.60 GB MLX pack including vision.
These are artifact sizes, not peak runtime memory. Its custom-loader warning,
earlier-build Apple speed measurements, and differences from the announcement's
benchmark table make provenance part of the exercise. Retention relative to
the source model does not establish parity with a frontier model.

Exercise: draft a comparison sheet for Bonsai and an existing small-model
baseline: exact weight/runtime revisions, packing, context and reasoning
budget, frozen task completion and regression gates, peak RAM, prefill/TTFT,
decode throughput, and total task latency. Mark unmeasured fields unknown;
separate inference feasibility from post-training feasibility.

Mastery gate: explain why parameter count, file size, RAM, and latency can rank
models differently, and specify a fair same-Mac test. A future experiment
requires owner selection, a scoped issue, and bounded resources; this reading
entry does not authorize model downloads or runs.

## Case study - QORL: parameter-aware query optimization

Added 2026-09-19. **Learning queued; experiment proposed, not started.**

Reference: [QORL](https://rohanbansal.com/qorl).

Read after ground-up Module 10 in the `evaluation-and-factory` path, with
`runtime-and-agents` for dispatcher overhead and fallback behavior. QORL studies
post-training a model to propose faster PostgreSQL plans. The owner-proposed
experiment below instead isolates offline search and parameter-based routing;
LLM training is explicitly outside its scope.

Exercise: turn the PRD into a frozen comparison protocol. Specify parameter
splits, workload weights, repeated-measurement/cache policy, timeout accounting,
search budgets, SQL-equivalence checks, and how unfamiliar parameters trigger
native fallback. Keep search/selection measurements separate from the fresh
held-out evaluation. Compare both search methods against native parameter-aware
planning and against each other.

Mastery gate: explain how selection bias, cache state, parameter skew, and
routing overhead can erase an apparent speedup. Derive break-even executions
as tuning cost divided by positive per-execution savings using consistent
units; report no finite break-even when savings are non-positive. Distinguish
wall-time amortization from monetary amortization.

### Owner PRD: Experimental Parameter-Aware Query Optimization

**Goal:** Test whether offline plan exploration and parameter-based routing
outperform PostgreSQL's native planner.

**Experiment:**

1. Use an isolated, representative PostgreSQL snapshot, **1–3 parameterized
   SELECT queries**, and real parameter samples.
2. Compare native parameter-aware planning, structured hint sweeping, and
   QORL-inspired LLM hint proposals. Give both searches equal execution budgets
   and hard timeouts; preserve SQL semantics.
3. Benchmark candidates repeatedly. Retain a small plan portfolio and learn a
   simple **parameters → plan** dispatcher, falling back to native planning for
   unfamiliar cases.
4. Evaluate on held-out parameters with fresh measurements after selection.
   Include dispatcher overhead.

**Deliverables:** Runnable harness, reusable plan portfolio, dispatcher, and
comparison report covering latency, regressions, resource usage, tuning cost,
and break-even execution count.

**Provisional success criteria:** At least **20% lower held-out workload
execution time**, with no greater than **10% p95 latency regression**. Retain
the LLM only if it provides worthwhile gains over structured search after
accounting for tuning cost.

**Non-goals:** Production integration, LLM training, SQL rewrites, index/schema
changes, or a general-purpose optimizer.

**Activation boundary:** This entry preserves the owner's proposed experiment
as learning material. Before implementation, choose the isolated snapshot,
queries, parameter source, explicit budgets, and acceptance metric definitions
in a scoped GitHub Issue. Database-optimizer implementation belongs in a
separately scoped project under the repo's factory boundary; the experimental
design and evaluation lessons remain part of this learning roadmap.

## Case study - Inside vLLM: inference systems and scaling boundaries

Added 2026-09-19. **Study only; no installation or benchmark started.**

Source: Aleksa Gordić, [Inside vLLM: Anatomy of a High-Throughput LLM Inference
System](https://www.aleksagordic.com/blog/vllm), published August 29, 2025.
The article analyzes V1 at commit `42172ad` (August 9, 2025); treat implementation
names and setup details as a historical snapshot.

Read after attention and transformer foundations, in `runtime-and-agents`,
with `architecture-and-kernels` for execution and memory tradeoffs. Study the
request lifecycle, paged KV storage, continuous batching, chunked prefill,
prefix reuse, constrained/speculative decoding, and the progression to
multi-GPU and multi-node serving.

Exercise, in three passes:

1. Draw a request from admission through scheduling, prefill, decode, and
   completion. Hand-simulate three requests of different lengths under a
   fixed token budget and KV-block capacity; show allocation and release.
2. Write a prediction table for which changes help TTFT, inter-token latency,
   throughput, or memory, and where improving one may hurt another. Connect
   the predictions to the existing [KV-cache notes](performance/kv_cache_optimization.md)
   and [inference guide](learn/advanced-llm-inference.md).
3. Separate ideas transferable to Mac-local serving from CUDA-specific
   execution mechanisms and cluster coordination. Explain what a second
   machine buys and what communication costs it introduces; do not assume
   an MLX implementation has vLLM's exact behavior or features.

Mastery gate: explain why high throughput need not mean low interactive
latency, trace block ownership without confusing storage layout with attention
math, and justify a single-Mac versus distributed serving choice for a stated
workload. Record the trace and predictions in the learning tracker. Refresh
upstream documentation before any future implementation; this is boundary
study, not a request to recreate or deploy a serving stack.

## Running source queue

Read in this order when updating the roadmap:

1. CS336
2. SmolLM / FineWeb-Edu
3. Tulu 3, then Savante / Aryabhata after ground-up Modules 9–10
4. Anthropic agents
5. OpenAI evals, then QORL for search, routing, and held-out runtime evaluation
6. Poolside Laguna
7. Apple MLX, then Inside vLLM for inference systems and scaling boundaries,
   and Bonsai 2 in the quantization/runtime paths
8. Llama/Qwen reports
9. DeepSeek-R1
10. Lamina/video references

Each time a new source is added, update this file with one of:

- **Adopt now**: exact owner-authorized issue and frozen experiment contract.
- **Adopt later**: exact trigger.
- **Study only**: why it is context, not roadmap.
- **Skip**: why it does not fit posttrainllm.
