---
title: "Session 10 — Attention and transformer blocks: routing information"
description: "By now a sequence is a matrix: `(seq_len, d_model)`, one vector per token"
---

# Session 10 — Attention and transformer blocks: routing information

> Fills **Module 7** of [`curriculum.md`](curriculum.md). Session 9 gave you
> matmul and shapes; Session 6 turned tokens into vectors. This session is the
> one operation that made transformers win: attention — how a token pulls
> information from other tokens — and the block that repeats it.

## Where we are

By now a sequence is a matrix: `(seq_len, d_model)`, one vector per token
(Session 6), and you can trace a matmul's shapes (Session 9). But those token
vectors are still isolated — nothing has let the word "it" look back at the noun
it refers to, or let a SQL `WHERE` clause see which table was named earlier.

**Attention is the mechanism that moves information between positions.** An MLP
transforms each token independently; attention is the only place tokens talk to
each other. That is the whole reason it matters.

---

## The problem attention solves

Take "the cat sat on the mat because **it** was tired." To represent "it"
usefully, the model needs "cat." Those tokens are five positions apart. An MLP
sees one token at a time and cannot reach across. You need an operation where
each position can **look at every other position and pull in what's relevant.**

That is attention: for each token, compute how much it should attend to every
other token, then take a weighted average of their information.

---

## Query, Key, Value — the three roles

Every token vector is projected (three matmuls — Session 9) into three vectors:

| Vector | Question it encodes | Analogy |
|---|---|---|
| **Query** (Q) | "what am I looking for?" | a search box |
| **Key** (K) | "what do I offer?" | a document's index tag |
| **Value** (V) | "what do I pass on if matched?" | the document's contents |

```text
token vector x  (d_model,)
   ├─ x · W_Q → q   "what I'm looking for"
   ├─ x · W_K → k   "what I advertise"
   └─ x · W_V → v   "what I hand over"
```

`W_Q`, `W_K`, `W_V` are learned weight matrices — this is where attention's
parameters live. Every token produces its own q, k, v.

---

## The attention computation, step by step

Four steps. Each is a Session-9 operation.

**1. Scores — how well does each query match each key?** Dot product every
query with every key. High dot product = "these two are relevant to each other."

```text
scores = Q · Kᵀ
(seq, d) · (d, seq) → (seq, seq)    the d's cancel
```

The result is a `(seq, seq)` grid: `scores[i][j]` = how much token `i` should
attend to token `j`.

**2. Scale.** Divide by `√d_head`. Large `d` makes dot products large, which
makes the next step (softmax) too sharp; the scale keeps gradients healthy.

**3. Softmax — turn scores into weights that sum to 1.** Applied per row, so
each token's attention over all tokens is a probability distribution.

```text
row i: [2.1, 0.3, 5.0, -1.0]  →  softmax  →  [0.05, 0.01, 0.93, 0.01]
                                              (sums to 1; token i mostly
                                               attends to position 2)
```

**4. Weighted sum of Values.** Multiply the weights by V — each token becomes a
blend of the Values it attended to.

```text
out = softmax(Q·Kᵀ / √d) · V
(seq, seq) · (seq, d) → (seq, d)
```

The output has the same shape as the input, but every token vector now contains
information pulled from the tokens it found relevant. "it" now carries "cat."

**The whole thing in one line:**

```text
Attention(Q, K, V) = softmax( Q·Kᵀ / √d_head ) · V
```

Two matmuls with a softmax between them. That is the operation that replaced
recurrence and made LLMs scale. In this repo it lives in
[`python_ref/model.py`](../../python_ref/model.py) as the math oracle, and in
[`webgpu/attention_fa2.wgsl`](../../webgpu/attention_fa2.wgsl) as the fused
FlashAttention-2 kernel doing the identical math without ever writing the full
`(seq, seq)` matrix to memory.

---

## Causal masking — no peeking at the future

A language model predicts the next token, so token `i` must not attend to tokens
after it (that would be seeing the answer). Before softmax, set the upper
triangle of the score grid to `-∞`; softmax turns `-∞` into weight 0.

```text
scores after masking (• = kept, × = masked to -∞):

        t0   t1   t2   t3
  t0  [  •    ×    ×    ×  ]
  t1  [  •    •    ×    ×  ]
  t2  [  •    •    •    ×  ]
  t3  [  •    •    •    •  ]   ← token 3 sees all; token 0 sees only itself
```

This lower-triangular mask is why a decoder can be trained on a whole sequence
at once yet still only ever look backward. Get the mask wrong and evals look
suspiciously perfect (the model is reading the future) — a classic silent bug.

---

## Multi-head attention — several conversations at once

One attention is one kind of relationship. Real models run **several heads in
parallel**, each with its own `W_Q/W_K/W_V`, so one head can track subject–verb
agreement while another tracks the table a column belongs to. Split `d_model`
into `h` heads of size `d_head = d_model / h`, attend in each, concatenate.

```text
d_model=512, h=8  →  8 heads × d_head=64
each head: Attention on its 64-dim slice  →  (seq, 64)
concat all 8  →  (seq, 512)  →  one more matmul (W_O) to mix them
```

**GQA (grouped-query attention)**, which modern models including the Qwen bases
this repo trains use, shares K and V across groups of query heads to shrink the
KV cache. Same operation, fewer K/V projections. See
[`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md) for GQA, RoPE
positional encoding, and attention variants, and
[`advanced-llm-inference.md`](advanced-llm-inference.md) for why the KV cache
(the stored K and V of past tokens) dominates inference memory.

---

## The transformer block — attention is only half

A transformer **block** wraps attention with three more pieces, and the model is
just this block stacked N times:

```text
        x ──────────────┐
        │               │ (residual: keep the original around)
   ┌────▼────┐          │
   │ LayerNorm│          │
   └────┬────┘          │
   ┌────▼──────────┐    │
   │  Attention     │    │   ← tokens exchange information
   └────┬──────────┘    │
        ▼               │
        + ◄─────────────┘   (add residual back)
        │
        ├───────────────┐
   ┌────▼────┐          │
   │ LayerNorm│          │
   └────┬────┘          │
   ┌────▼──────────┐    │
   │  MLP (FFN)     │    │   ← each token transformed independently
   └────┬──────────┘    │
        ▼               │
        + ◄─────────────┘
        │
        ▼  (out — same shape as x, feeds the next block)
```

- **Residual connection** (`x + sublayer(x)`): the input is added back after
  each sublayer. Gradients flow straight through the `+`, so 32-layer models
  train without vanishing gradients. This "residual stream" is also what
  interpretability reads — see below.
- **LayerNorm**: normalizes each token vector to stable scale before each
  sublayer, keeping training numerically calm (ties back to Session 8's
  precision and stability notes).
- **MLP / FFN**: two matmuls with a non-linearity between (Session 4 — this is
  the "make depth useful" piece). Usually widens `d_model → 4·d_model → d_model`.
  This is where most parameters and most stored *facts* live.

Attention **routes** information between tokens; the MLP **processes** each
token. A block does both; a model is `N` blocks plus an embedding at the bottom
(Session 6) and an LM head at the top that projects back to vocabulary logits.

---

## You can watch this happen in this repo

The browser playground ships an **attention heatmap** — for any prompt it renders
the per-head attention weights (the `softmax(Q·Kᵀ)` grid) from the last block.
The **logit lens** projects each block's residual stream through the LM head to
show when a prediction crystallizes across depth. Both are documented in
[`../interpretability.md`](../interpretability.md). Reading that doc after this
session is the "inspect it" exercise: you will recognize the `(seq, seq)` grid
and the residual stream as the exact objects defined here.

---

## Self-check

Don't peek:

1. **Why can't an MLP alone let "it" refer back to "cat" five tokens earlier,
   but attention can?**
2. **Q·Kᵀ produces what shape from a `(seq, d)` Q and K, and what does entry
   `[i][j]` mean?**
3. **What does the causal mask do, and what goes wrong in evals if you forget
   it?**
4. **A model has `d_model=512` and 8 heads.** What is `d_head`, and what shape
   does each head's attention output have?
5. **Trap:** you remove every residual connection from a 24-layer model and
   training loss refuses to drop. What broke, and why did the residual fix it?

---

## Where this connects

- **Back to Session 9:** attention is two matmuls and a softmax; every shape
  here obeys the cancellation rule. Back to Session 6: the vectors attention
  operates on are the token embeddings.
- **Forward to Module 9 (post-training):** LoRA most often adapts exactly the
  `W_Q/W_K/W_V/W_O` attention projections — the matrices introduced here are the
  ones fine-tuning usually touches.
- **Repo anchors:** posttrainllm's math oracle
  [`python_ref/model.py`](../../python_ref/model.py),
  [`webgpu/attention_fa2.wgsl`](../../webgpu/attention_fa2.wgsl) +
  [`../online_softmax_in_attention.md`](../online_softmax_in_attention.md) +
  [`../fa2_forward_notes.md`](../fa2_forward_notes.md) (the same math, fused and
  memory-safe), [`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md)
  (RoPE/GQA/MoE), [`../interpretability.md`](../interpretability.md) (watch it).
- **Factory consequence:** when a SQL adapter learns to attend from a `JOIN`
  back to the right table, that is these attention weights shifting. When you
  choose which modules LoRA targets, you are choosing which of the matrices in
  this session get a low-rank update.
