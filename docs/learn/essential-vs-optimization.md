---
title: Mathematically essential vs engineering optimization
description: "The single most useful lens on this project — which parts compute the model's function (irreducible math, the correctness oracle) vs which parts only make that function cheaper/faster (the optimization layer). Plus the one number that polices the boundary: loss drift."
---

# Mathematically essential vs engineering optimization

The whole project splits cleanly into two layers, and keeping them separate is the difference
between understanding posttrainllm and memorizing it.

- **Mathematically essential** — the code that *defines what function the model computes*. Change
  it and the model computes something **different**. The oracle is [`python_ref/model.py`](../../python_ref/model.py):
  the cleanest statement of the math, the thing every other backend is validated against.
- **Engineering optimization** — the code that computes that *same* function **faster, smaller, or
  on different silicon**. Delete it and the model computes the identical function, just slower or
  bigger.

**The litmus test:** *"If I removed this, would the model compute a different function, or the same
function more slowly?"* Different ⇒ essential. Same ⇒ optimization.

## The two columns

| Mathematically essential (defines the function) | What it computes |
|---|---|
| Token + position embeddings | tokens → vectors; inject order |
| Self-attention: `softmax(QKᵀ/√d ⊙ causalmask) · V` | mix information across positions |
| Multi-head | run attention in `H` subspaces, concat |
| LayerNorm + residuals | stabilize + let gradients skip |
| MLP + GELU | per-position non-linear transform |
| Output projection → logits | hidden → vocab scores |
| Cross-entropy loss | scores → a scalar to minimize |
| Backprop (chain rule through all the above) | loss → per-parameter gradients |
| Adam/AdamW update | gradients → weight step |

| Engineering optimization (preserves the function) | What it speeds/shrinks | Must preserve |
|---|---|---|
| Matmul tiling + 4×4 register blocking ([study_guide §8](../guides/study_guide.md)) | arithmetic intensity → compute-bound | bit-parity matmul |
| `vec4<f32>` packed loads ([§9](../guides/study_guide.md)) | 128-bit memory transactions | same result (the bug that wasn't) |
| FlashAttention-2 ([online-softmax](../performance/online_softmax_in_attention.md), §7) | O(T²)→O(T) memory; recompute on backward | **identical** attention math |
| KV cache | decode O(T²)→O(T) compute | same logits |
| Quantization (4-bit/8-bit) | weights smaller | *approximately* same weights (lossy!) |
| WASM / WebGPU backends | run on CPU-SIMD / GPU | parity with `python_ref` |
| Memory64 (`-sMEMORY64`) | address heaps >4 GB | same kernels |
| Gradient checkpointing | recompute activations → less RAM | identical gradients |

Two subtleties worth internalizing:
- **FA2 is *optimization*, not math.** It computes the exact same attention output — it just never
  materializes the `[B,H,T,T]` matrix and recomputes scores on the backward pass. The online-softmax
  trick is algebraically identical to textbook softmax; the win is structural, not numerical.
- **Quantization is the one optimization that *isn't* lossless.** It approximates the weights, so it
  legitimately changes the output a little — which is exactly why it shows up as a *real* accuracy
  delta in evals (we measured bf16 vs 4-bit = +4 on tool-calling), not as a parity bug.

## Loss drift — the number that polices the boundary

How do you *prove* an optimization preserved the math? **Loss drift.**

> **Loss drift** = the percent difference between an optimized backend's training loss and the
> Python reference's loss at the **same step N**, same seed, same data, same hyperparameters.
> `drift = |loss_backend − loss_ref| / loss_ref`.

It is the single number that says "this optimization is still computing the right function":

- **< ~2.5–5% drift at 50 steps = numerically equivalent.** Floating-point addition isn't
  associative, so a tiled GPU kernel sums partial products in a different order than the reference;
  that reorder produces small, *bounded* deviation. This is expected and benign.
- **Larger drift = a real bug**, not "just precision." It means the optimization changed the
  function — a wrong gradient, a transposed tile, a bad bind-group. Example ([study_guide §9](../guides/study_guide.md)):
  a `vec4` integration passed its standalone kernel test but drove training loss to **88.67** while
  the reference sat at **2.94** — a ~30× drift. The cause was a bind-group access-mode mismatch
  returning wrong data; the one-line fix dropped drift below 1%.

This is also **why parity testing beats standalone kernel benchmarks**: a standalone benchmark
checks the kernel in isolation (ideal shapes, fresh cache) and answers "is it fast + self-consistent?"
Drift checks the kernel *inside the real pipeline* and answers "does it still compute the model's
function?" Only the second question is the one that ships. (See [study_guide §9](../guides/study_guide.md).)

## Why this lens matters

- **It tells you what mastery requires.** You should be able to **reimplement the essential column
  from scratch, without AI** — that's the real exam (it's `python_ref/model.py`, ~300 lines). The
  optimization column you should understand *in principle* (why tiling, why FA2, why a KV cache), but
  any specific kernel is substitutable; the principle is the knowledge, the WGSL is an artifact.
- **It tells you where bugs live.** A wrong *output* is usually an essential-layer bug (the math).
  A wrong *speed/memory* with correct output is an optimization-layer issue. A correct standalone
  kernel with wrong end-to-end loss is an optimization that broke the math — caught only by drift.
- **It tells you what's safe to change.** Swapping a matmul kernel is safe if drift stays low.
  Changing the attention formula is a math change and needs re-deriving the backward pass.

## References

- Oracle for the essential column: [`python_ref/model.py`](../../python_ref/model.py).
- Optimization-layer deep dives: [study_guide.md](../guides/study_guide.md) §7 (FA2), §8 (register blocking),
  §9 (parity + the drift bug); [online-softmax](../performance/online_softmax_in_attention.md);
  [WebGPU execution model](./webgpu-execution-model.md).
- The math, taught from scratch: roadmap [Phases 1–4](../archive/learning_roadmap.md); sessions 1–8 in this dir.
