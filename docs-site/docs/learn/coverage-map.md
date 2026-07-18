---
title: "Learning coverage map — every subsystem has a home"
description: "This map is the guarantee that the learning corpus **covers everything in the"
---

# Learning coverage map — every subsystem has a home

This map is the guarantee that the learning corpus **covers everything in the
project**. The ground-up [`curriculum.md`](curriculum.md) is the *spine* (10
modules, first principles to self-improving factory). This page is the *net*:
every shipped capability in `PROJECT_STATUS.md` maps to a learning anchor here,
so no subsystem is a black box with no explainer.

How to read it: the **Anchor** column is where to go to learn that thing. Where a
concept has a definitive external source, the anchor stays thin and links out
(per the repo's "lean on external sources" rule) rather than re-explaining.

The spine teaches you to *read* the whole system; this map is the index that
proves nothing was left unread.

---

## 1. Foundations — the ground-up spine

The 10-module arc. This is the "learn it in order" path; everything below builds
on it.

| Module | Topic | Anchor |
|---:|---|---|
| 1 | Functions, data, parameters | [`session-01-neural-net-basics.md`](session-01-neural-net-basics.md) |
| 2 | Loss and gradient descent | [`session-02-gradient-descent.md`](session-02-gradient-descent.md) |
| 3 | Vectors, matrices, tensors | [`session-09-tensors.md`](session-09-tensors.md) |
| 4 | Non-linear nets + backprop | [`session-03-non-linearities.md`](session-03-non-linearities.md) |
| 5 | ML paradigms and scaling | [`session-04-ml-paradigms.md`](session-04-ml-paradigms.md), [`session-05-scaling.md`](session-05-scaling.md) |
| 6 | Tokenization, embeddings, LM | [`session-06-tokenization-embeddings.md`](session-06-tokenization-embeddings.md) |
| 7 | Attention and transformer blocks | [`session-10-attention.md`](session-10-attention.md) |
| 8 | Training mechanics | [`session-08-training-mechanics.md`](session-08-training-mechanics.md) |
| 9 | Post-training: SFT, LoRA, preference tuning | [`session-07-behavior-learning.md`](session-07-behavior-learning.md) |
| 10 | Evals, rewards, self-improvement | [`session-11-evals-rewards.md`](session-11-evals-rewards.md) |

Reference layer under the spine:
[`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md) (RoPE, GQA, MoE,
attention variants) and
[`essential-vs-optimization.md`](essential-vs-optimization.md) (which math
defines the model vs which only makes it fast).

---

## 2. Post-training methods and internals

Everything under `PROJECT_STATUS.md` → "Training and post-training."

| Capability | Anchor |
|---|---|
| SFT | [`../training/sft.md`](../training/sft.md), Module 9 |
| Pretraining | [`../training/pretrain.md`](../training/pretrain.md), Session 8 |
| LoRA / DoRA / QLoRA | [`../lora_guide.md`](../lora_guide.md), [`../peft_variants.md`](../peft_variants.md), [`../factory/lora-geometry.md`](../factory/lora-geometry.md), Session 9 |
| DPO / SimPO / preference tuning | [`../training/dpo.md`](../training/dpo.md), Module 9 + 10 |
| Distillation | [`../distillation.md`](../distillation.md), [`diversity-driven-small-model-reasoning.md`](diversity-driven-small-model-reasoning.md) |
| Evolution strategies (ES) | [`../evolution_strategies.md`](../evolution_strategies.md), [`castform-rl-finetune.md`](castform-rl-finetune.md) |
| RLVR / ReST / GRPO | [`advanced-llm-training.md`](advanced-llm-training.md), [`../GRPO_CLARIFY.md`](../GRPO_CLARIFY.md) |
| Optimizers, schedules, stability | [`../optimizers.md`](../optimizers.md), [`../galore_and_stability.md`](../galore_and_stability.md), Session 8 |
| NEFTune, z-loss, WSD, LLRD, seq packing, grad checkpointing | [`../training_guide.md`](../training_guide.md), [`../gradient_checkpointing_results.md`](../gradient_checkpointing_results.md), Session 8 |
| Precision (bf16 / fp8 / mixed) | [`../precision.md`](../precision.md), [`advanced-llm-training.md`](advanced-llm-training.md) |
| Method-vs-recipe discipline | [`../techniques/method-vs-recipe.md`](../techniques/method-vs-recipe.md) |

---

## 3. Data pipeline

`PROJECT_STATUS.md` → "Data."

| Capability | Anchor |
|---|---|
| Dataset registry / inventory | [`../dataset-inventory.md`](../dataset-inventory.md), [`../data_inventory.md`](../data_inventory.md) |
| HF integration | [`../hf_datasets_integration.md`](../hf_datasets_integration.md) |
| GitHub fetcher | [`../github_data_integration.md`](../github_data_integration.md) |
| Magpie / synthesis | [`advanced-llm-training.md`](advanced-llm-training.md) (data curation), [`small-model-tool-calling-playbook.md`](small-model-tool-calling-playbook.md) |
| Tokenizer training, extractor data | [`session-06-tokenization-embeddings.md`](session-06-tokenization-embeddings.md), [`../tool_call_extractor.md`](../tool_call_extractor.md) |
| Traces → data, corrections → data | [`../recipes/from-traces.md`](../recipes/from-traces.md) |
| Quality filter, dedupe, reasoning-classify | [`../factory/post-training-factory.md`](../factory/post-training-factory.md), [`castform-rl-finetune.md`](castform-rl-finetune.md) |

---

## 4. Evaluation

`PROJECT_STATUS.md` → "Evals." Module 10 is the concept spine; these are the
surfaces.

| Capability | Anchor |
|---|---|
| Eval protocol, frozen baselines, gates | [`../factory/eval-protocol.md`](../factory/eval-protocol.md), Module 10 |
| Eval methodology / broken-eval lessons | [`eval-methodology-2026-06-08.md`](eval-methodology-2026-06-08.md), [`eval-matrix-2026-06-08.md`](eval-matrix-2026-06-08.md) |
| BFCL / tool-calling eval | [`tool-calling-frontier-parity.md`](tool-calling-frontier-parity.md), [`small-model-tool-calling-playbook.md`](small-model-tool-calling-playbook.md) |
| SQL execution / exact / slices / candidate-choice | [`../techniques/sql-technique-backlog.md`](../techniques/sql-technique-backlog.md), Module 10 |
| lm-eval / HumanEval / MTEB / MILU / tau-bench | [`../lm_eval_integration.md`](../lm_eval_integration.md), [`advanced-ml-systems-eval.md`](advanced-ml-systems-eval.md) |
| Router / routed-specialist eval, eval-gate, planner eval | [`../recipes/eval-gate.md`](../recipes/eval-gate.md), [`../recipes/eval_planner.md`](../recipes/eval_planner.md), [`../planner-lock-2026-06-19.md`](../planner-lock-2026-06-19.md) |
| LLM-as-judge, perplexity, contamination | [`advanced-ml-systems-eval.md`](advanced-ml-systems-eval.md), Module 10 |
| Leaderboard / reporting | [`../leaderboard.md`](../leaderboard.md), [`../factory/reports.md`](../factory/reports.md) |

---

## 5. Runtime, serving, and agents

`PROJECT_STATUS.md` → "Runtime/serving."

| Capability | Anchor |
|---|---|
| Inference/serving architecture, batching, roofline | [`advanced-llm-inference.md`](advanced-llm-inference.md) |
| KV cache + paging | [`../kv_cache_optimization.md`](../kv_cache_optimization.md), [`advanced-llm-inference.md`](advanced-llm-inference.md) |
| OpenAI/Ollama-compatible serve, Continue provider | [`../agent_runtime.md`](../agent_runtime.md), [`../continue_provider.md`](../continue_provider.md) |
| Agent loop, tool dispatch | [`model-vs-agent.md`](model-vs-agent.md), [`../async_tool_dispatch.md`](../async_tool_dispatch.md), [`agent-context-hierarchy.md`](agent-context-hierarchy.md) |
| Constrained JSON / FSM generation | [`../constrained_generation.md`](../constrained_generation.md) |
| Speculative decoding / MTP | [`../speculative_heads.md`](../speculative_heads.md), [`../mtp.md`](../mtp.md), [`advanced-llm-inference.md`](advanced-llm-inference.md) |
| Cost routing / escalation / cascade (AutoMix, ScaleDown) | [`../recipes/automix.md`](../recipes/automix.md), [`../recipes/b25-scaledown.md`](../recipes/b25-scaledown.md), [`agent-context-hierarchy.md`](agent-context-hierarchy.md) |
| Streaming / long context (StreamingLLM, KIVI) | [`../streaming_llm_kivi.md`](../streaming_llm_kivi.md) |

---

## 6. Quantization, packaging, and inference optimization

`PROJECT_STATUS.md` → "Packaging/runtime."

| Capability | Anchor |
|---|---|
| Quantization (GGUF / AWQ / GPTQ / HQQ), quant theory | [`../quantization_expansion.md`](../quantization_expansion.md), [`advanced-llm-inference.md`](advanced-llm-inference.md) |
| Export to MLX / safetensors / CoreML | [`../recipes/mlx-export.md`](../recipes/mlx-export.md), [`../factory/packaging.md`](../factory/packaging.md) |
| merge / bake-lora | [`../factory/lora-geometry.md`](../factory/lora-geometry.md), [`../lora_guide.md`](../lora_guide.md) |
| Pruning | [`../pruning.md`](../pruning.md) |
| Specialist packaging / model cards | [`../factory/packaging.md`](../factory/packaging.md), [`../factory/public-artifacts.md`](../factory/public-artifacts.md) |

---

## 7. Attention and kernel internals

The math oracle is [`python_ref/model.py`](../../python_ref/model.py); Session 10
is the concept.

| Capability | Anchor |
|---|---|
| Attention math, transformer block | [`session-10-attention.md`](session-10-attention.md) |
| FlashAttention-2 forward/backward | [`../fa2_forward_notes.md`](../fa2_forward_notes.md), [`../fa2_backward_notes.md`](../fa2_backward_notes.md) |
| Online softmax | [`../online_softmax_in_attention.md`](../online_softmax_in_attention.md) |
| MoE / expert routing | [`../moe.md`](../moe.md), [`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md) |

---

## 8. Browser / WASM / WebGPU track (completed, parked)

`PROJECT_STATUS.md` → "Completed/parked learning tracks."

| Capability | Anchor |
|---|---|
| WebGPU execution model (read before the `.wgsl` files) | [`webgpu-execution-model.md`](webgpu-execution-model.md) |
| Browser GPT training, WASM SIMD, OPFS | [`../browser_notes.md`](../browser_notes.md) |
| BPE-in-browser scoring | [`../bpe_browser_scoring.md`](../bpe_browser_scoring.md) |
| Numerics gates / precision drift | [`../precision.md`](../precision.md), [`../determinism.md`](../determinism.md) |

---

## 9. Native Mac / MLX / ANE / Apple Foundation Models

| Capability | Anchor |
|---|---|
| Mac-local mastery map (living agenda) | [`mac-mastery-map.md`](mac-mastery-map.md) |
| Apple on-device Foundation Models — where they fit | [`apple-on-device-foundation-models.md`](apple-on-device-foundation-models.md), [`app-intents-comparison.md`](app-intents-comparison.md) |
| ANE / CoreML research (negative results) | [`ane-research/`](ane-research/) |
| Native runtime architecture | [`../../native-mac/ARCHITECTURE.md`](../../native-mac/ARCHITECTURE.md) |

---

## 10. Interpretability (completed, parked)

| Capability | Anchor |
|---|---|
| Attention heatmap + logit lens (browser) | [`../interpretability.md`](../interpretability.md), Session 10 |
| SAE, ROME, MEMIT, tuned/logit lens, activation patching | [`../interpretability.md`](../interpretability.md), [`advanced-ml-systems-eval.md`](advanced-ml-systems-eval.md) |

---

## 11. Multimodal (VLM) — research/parked

| Capability | Anchor |
|---|---|
| Qwen3-VL mRoPE + DeepStack, vision-language attention | [`qwen3-vl-mrope-deepstack.md`](qwen3-vl-mrope-deepstack.md) |

---

## 12. The factory loop and methodology

The thing all of the above serves.

| Capability | Anchor |
|---|---|
| Factory overview + run schema | [`../factory/overview.md`](../factory/overview.md), [`../factory/run-schema.md`](../factory/run-schema.md) |
| Batch post-training / rollout plan | [`../factory/batch-posttraining.md`](../factory/batch-posttraining.md) |
| Case-study reports, public artifacts | [`../factory/case-study-template.md`](../factory/case-study-template.md), [`../factory/public-artifacts.md`](../factory/public-artifacts.md) |
| Attempt history (worked/failed/regressed) | [`../attempt-ledger.md`](../attempt-ledger.md) |
| Owner learning sequence tied to factory work | [`../learning-pipeline.md`](../learning-pipeline.md), [`../learning-progress.md`](../learning-progress.md) |

---

## 13. Strategy and external knowledge

| Capability | Anchor |
|---|---|
| Competitive landscape, Mac-first whitespace | [`competitive-landscape.md`](competitive-landscape.md) |
| Reviewed external products / stolen techniques | [`../external-products-reviewed.md`](../external-products-reviewed.md), [`castform-rl-finetune.md`](castform-rl-finetune.md) |
| Speech & systems interview-grade topics | [`speech-and-systems-topics.md`](speech-and-systems-topics.md) |
| Papers / reading list | [`external-references.md`](external-references.md), [`../CITATIONS.md`](../CITATIONS.md) |
| Running questions and tangents | [`journal.md`](journal.md) |

---

## Coverage Guarantee

**Every shipped capability in `PROJECT_STATUS.md` → "Features (shipped)" and
"Completed/parked learning tracks" appears in exactly one section above with a
learning anchor.** The factory-loop framing is the checklist:

```text
target -> data -> post-training -> eval -> package -> report
```

- **target / methodology** → §12
- **data** → §3
- **post-training** → §2, §7 (internals), §9 (Mac runtime), §11 (VLM)
- **eval** → §4, Module 10
- **package** → §6
- **report** → §4, §12
- **serve/run the result** → §5
- **understand the result** → §10 (interpretability), §1 (foundations)

### Maintenance rule

This map is guarded by
[`../../scripts/check_learning_roadmap.py`](../../scripts/check_learning_roadmap.py)
(run via `bash evals/learning-roadmap-smoke.sh`). When a **new subsystem** ships
in `PROJECT_STATUS.md`, add a row here pointing to its best explainer before
calling the feature done — a capability with no learning anchor is an
undocumented black box. When an existing doc is the definitive explainer, point
to it (DRY); only write a new learn doc when nothing adequate exists.
