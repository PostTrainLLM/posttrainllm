---
title: "posttrainllm — study queue"
description: "Short stubs for every genuinely-novel topic in the codebase."
---

# posttrainllm — study queue

Short stubs for every genuinely-novel topic in the codebase.
Fill in `Why here:` yourself after internalising each topic.

---

## Backpropagation & gradient descent
- What: compute the loss gradient w.r.t. every parameter via the chain rule (reverse-mode autodiff), then step each parameter against its gradient.
- Why here: TBD
- Source: https://www.youtube.com/watch?v=VMj-3S1tku0 (Karpathy — spelled-out intro, builds a tiny autograd by hand)

## Next-token language modeling & sampling
- What: a language model predicts a probability distribution over the next token; generation repeatedly samples from it, shaped by temperature and top-k truncation.
- Why here: TBD
- Source: https://github.com/karpathy/makemore

## Memorization testing (style-adaptation eval)
- What: feed a training-set prefix and check whether the model copies the exact continuation; distinguishes learned style from memorised text, alongside base/prompt-only/LoRA baselines.
- Why here: TBD
- Source: https://arxiv.org/abs/2012.07805 (Carlini et al. — extracting training data from LMs)

## Transformer / scaled-dot-product attention
- What: sequence model where each token attends to all previous tokens via learned Q/K/V projections; output is a weighted sum of values.
- Why here: TBD
- Gotcha (from code): per-thread private `array<f32, 1024>` for the score row at ctx=1024 is 4 KB — Apple WebGPU spills it to global memory.
- Source: https://nlp.seas.harvard.edu/annotated-transformer/

## Flash Attention 2 (FA2)
- What: tiled attention algorithm that walks K/V in blocks and accumulates softmax online, never materialising the full T×T score matrix.
- Why here: TBD
- Gotcha (from code): tile sizes `Br = Bc = 16` are hard-coded in `webgpu/attention_fa2.wgsl`; going wider hits register pressure on Apple GPU.
- Source: https://arxiv.org/abs/2307.08691

## Online softmax
- What: single-pass numerically-stable softmax that carries a running max and denominator, updating them as each new element arrives.
- Why here: TBD
- Source: https://arxiv.org/abs/1805.02867

## Byte-Pair Encoding (BPE) tokenization
- What: greedy compression algorithm that iteratively merges the most-frequent byte pair until a target vocab size is reached; tokens are subword units.
- Why here: TBD
- Source: https://huggingface.co/learn/nlp-course/chapter6/5

## WebAssembly (WASM) + Emscripten
- What: portable binary instruction format; Emscripten compiles C++ to `.wasm` + a JS glue file that wires browser APIs (memory, threads) to the C runtime.
- Why here: TBD
- Gotcha (from code): WASM Memory64 (`tinygpt64.wasm`) hits a pthread × `WebAssembly.Memory.grow` race in the browser — the fix is over-allocating `INITIAL_MEMORY=256 MB` so growth never fires during training.
- Source: https://emscripten.org/docs/porting/pthreads.html

## WASM SIMD + multi-threading
- What: WASM SIMD extends the ISA with 128-bit vector ops; multi-threading uses `SharedArrayBuffer` + `Atomics` to run pthreads across Web Workers.
- Why here: TBD
- Source: https://github.com/WebAssembly/simd/blob/master/proposals/simd/SIMD.md

## WebGPU + WGSL
- What: next-gen browser GPU API (successor to WebGL) with an explicit pipeline model; WGSL is its shader language.
- Why here: TBD
- Gotcha (from code): `var<storage, read>` vs `buffer: { type: "storage" }` mismatch — Apple WebGPU silently returns wrong data instead of a validation error; caused vec4 matmul to diverge loss to 88.67 in end-to-end training.
- Source: https://gpuweb.github.io/gpuweb/

## Tiled / register-blocked matrix multiplication (GPU)
- What: partition operand matrices into shared-memory tiles to reduce global memory traffic; register blocking accumulates partial sums in registers to further reduce shared-memory reads.
- Why here: TBD
- Gotcha (from code): 8×8 register blocking beat 4×4 in theory but lost at every measured size — exceeded Apple's per-thread register budget and forced spill.
- Source: https://siboehm.com/articles/22/CUDA-MMM

## fp16 / mixed-precision
- What: 16-bit floating point; mixed-precision trains in fp16 for speed while keeping a fp32 master copy of weights to avoid underflow/overflow.
- Why here: TBD
- Gotcha (from code): f16-packed weights were 1.7× faster standalone but *slower* when stacked on tiled matmul — tiling had already amortised the global-read savings.
- Source: https://arxiv.org/abs/1710.03740

## Sparse Autoencoder (SAE) / mechanistic interpretability
- What: a learned over-complete dictionary trained to reconstruct a model's hidden states with a sparsity penalty; used to decompose polysemantic neurons into monosemantic features.
- Why here: TBD
- Source: https://transformer-circuits.pub/2023/monosemantic-features/index.html

## Logit lens
- What: interpretability probe that projects each intermediate residual-stream state through the final unembedding to see what token the model "would predict" at that depth.
- Why here: TBD
- Source: https://www.lesswrong.com/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens

## Gradient checkpointing (activation recomputation)
- What: trade compute for memory by discarding intermediate activations during the forward pass and recomputing them during the backward pass.
- Why here: TBD
- Source: https://arxiv.org/abs/1604.06174

## AdamW optimizer
- What: Adam with decoupled weight decay (decay applied to weights directly, not through the gradient); standard default for transformer training.
- Why here: TBD
- Gotcha (from code): browser default LR was `3e-3` (10× too hot vs Python reference `3e-4`); training plateaued at loss ~2.45 and looked like a modelling ceiling.
- Source: https://arxiv.org/abs/1711.05101

## LoRA (Low-Rank Adaptation)
- What: fine-tuning method that freezes pre-trained weights and injects trainable low-rank matrices (A·B) into each projection; only A and B are updated.
- Why here: TBD
- Source: https://arxiv.org/abs/2106.09685

## Speculative decoding (draft + verify)
- What: a small fast draft model proposes K tokens; the big target verifies them in ONE batched forward and accepts the longest matching prefix — lossless vs the target's own sampling, just faster wall-clock.
- Why here: TBD
- Gotcha (from code): on Metal, greedy spec-decode is NOT byte-identical to single-token decode — batched-verify vs single-token attention aren't bit-reproducible across batch shapes, so a near-tie argmax occasionally flips (still a valid greedy decode; verified against the uncached reference). serve speedup is content-dependent (acceptance 2.3 dense → 3.3 structured) and masking-bound under `--grammar`. "Seed-carry" (feed the last burst token as the next verify's first) avoids a wasted second target forward.
- Source: https://arxiv.org/abs/2211.17192 (Leviathan et al., 2023)

## Continual learning / online adapter refresh
- What: instead of freezing a model at ship time, capture real-usage signal (corrections, edits, retries) and periodically retrain a LoRA on it so the model improves from production; the on-device version keeps all data local.
- Why here: TBD
- Source: https://docs.trajectory.ai/introduction · see `docs/prds/continual-learning-loop.md`
