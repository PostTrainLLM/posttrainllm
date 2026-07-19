# Session 9 — Vectors, matrices, tensors: the shapes that carry everything

> Fills **Module 3** of [`curriculum.md`](curriculum.md). Session 2 fit a line
> with one input and two parameters. Real models multiply and add over arrays
> of numbers by the million. This session is the array machinery — enough to
> read a shape error and know which axis is wrong.

## Where we are

Session 2's model was `y = mx + b`: one input scalar `x`, two scalar
parameters `m` and `b`. A transformer does the same *kind* of arithmetic —
multiply, add, repeat — but over vectors and matrices instead of single
numbers. Nothing conceptually new happens. The bookkeeping is the whole game.

If you can trace a shape through one layer, you can read almost any model dump,
any stack trace ending in `RuntimeError: mat1 and mat2 shapes cannot be
multiplied`, and any LoRA rank decision. That is the entire ambition here.

---

## The three objects

| Name | Rank (n-dim) | Example | In this repo |
|---|---|---|---|
| **Scalar** | 0 | `3.0` | one logit, the loss, a learning rate |
| **Vector** | 1 | `[0.2, -1.1, 0.7]` | one token's embedding, one row of logits |
| **Matrix** | 2 | 3×4 grid | a weight matrix, a batch of vectors |
| **Tensor** | n | (batch, seq, dim) | the actual activations flowing through the model |

"Tensor" is just the general word: a scalar is a rank-0 tensor, a vector rank-1,
a matrix rank-2. Everything past that (rank-3, rank-4) is the same idea with
more axes. There is no new math — only more indices to keep straight.

**Shape** is the tuple of axis lengths. A 3×4 matrix has shape `(3, 4)`. The
activation tensor mid-model has shape `(batch, seq_len, d_model)`, e.g.
`(8, 256, 512)` for a small run. Read shapes left-to-right as "outer to inner."

---

## The one operation that matters: the dot product

Session 2's `m * x` was a scalar multiply. Promote both sides to vectors and the
generalization is the **dot product**: multiply element-wise, then sum.

```text
w = [ 2, -1,  3 ]
x = [ 1,  4,  2 ]

w · x = (2·1) + (-1·4) + (3·2) = 2 - 4 + 6 = 4
```

That single number is one neuron's pre-activation. `y = mx + b` was the
one-dimensional case: `w · x + b` with length-1 vectors. Everything a
transformer computes is millions of these, arranged so a GPU can do them at
once.

**Exercise (do this one by hand):** rewrite the Session 2 line `y = 3x + 1` at
`x = 2` as a dot product. Answer: `w = [3]`, `x = [2]`, `w · x = 6`, plus bias
`1` → `7`. The line was a dot product all along.

---

## Matrix–vector: a whole layer at once

A layer has many neurons, each with its own weight vector. Stack those vectors
as **rows** of a matrix `W`, and the whole layer is one matrix–vector product:

```text
        x = [1, 4, 2]         (input vector, shape (3,))

W = [  2  -1   3 ]  row 0 → neuron 0
    [  0   1  -1 ]  row 1 → neuron 1
    (shape (2, 3): 2 neurons, 3 inputs each)

W x = [ (2·1 + -1·4 + 3·2) ,        →  [ 4,
        (0·1 +  1·4 + -1·2) ]           2 ]   (shape (2,))
```

Read the shapes: `(2, 3) · (3,) → (2,)`. The **inner dimensions must match**
(the `3` on both sides), and they cancel; the outer dimensions survive. That
cancellation rule is the single most useful thing in this session.

```text
(a, b) · (b, c) → (a, c)      the two b's must match and disappear
```

Nine times out of ten a shape error is a `b` that does not match a `b`.

---

## Matrix–matrix: a whole batch at once

Training never feeds one vector. It feeds a **batch** of them, stacked as rows.
One matrix multiply then transforms the entire batch:

```text
X shape (batch=4, in=3)   ·   Wᵀ shape (in=3, out=2)   →   (batch=4, out=2)
```

Same cancellation: the `3`s meet in the middle and vanish; `batch` and `out`
survive. This is why GPUs love transformers — the core of a forward pass is a
stack of big matrix multiplies, the one thing GPUs do fastest.

**The oracle in this repo:** [`python_ref/model.py`](../../python_ref/model.py)
is the from-scratch reference model. Every `@` (Python matmul) in it is exactly
this operation. The WGSL kernels under [`webgpu/`](https://github.com/PostTrainLLM/posttrainllm/blob/main/webgpu) —
`matmul.wgsl`, `matmul_tiled.wgsl`, `matmul_blocked_vec4.wgsl` — are that *same*
matmul, hand-optimized for the GPU. The math is fixed; the kernels only change
how fast it runs. That split is the whole point of
[`essential-vs-optimization.md`](essential-vs-optimization.md).

---

## The extra axis: batch and sequence

A transformer activation is usually rank-3: `(batch, seq_len, d_model)`.

```text
(8, 256, 512)
 │    │    └── d_model: 512 numbers describe each token   (the vector)
 │    └─────── seq_len: 256 tokens in the sequence         (the matrix, per item)
 └──────────── batch: 8 independent sequences at once      (the stack)
```

A matmul against a weight `(512, 512)` acts on the **last** axis and leaves the
other two alone: `(8, 256, 512) · (512, 512) → (8, 256, 512)`. That "operate on
the last axis, broadcast over the rest" pattern is how one weight matrix
processes every token of every sequence in the batch in a single call.

---

## Two operations that trip everyone: transpose and broadcasting

**Transpose** (`ᵀ`) swaps two axes. A `(3, 2)` matrix becomes `(2, 3)`. Half of
all shape errors are fixed by transposing one operand so the inner dims line up.
When you see `(batch, in) · (in, out)`, the weight is often stored as
`(out, in)` and silently transposed — that is the framework doing it for you.

**Broadcasting** stretches a smaller shape to fit a larger one without copying
data. Adding a bias vector `(512,)` to activations `(8, 256, 512)` works because
the `(512,)` is broadcast across all `8×256` positions. The rule: align shapes
from the right; each axis must either match or be `1`.

```text
(8, 256, 512)
(           512)   ← broadcast over batch and seq  ✓
(8,   1, 512)      ← broadcast over seq only        ✓
(8, 256,   7)      ← 512 vs 7, neither is 1          ✗ error
```

---

## Why this is exactly what LoRA touches

A weight matrix `W` of shape `(out, in)` — say `(2048, 2048)` — has ~4.2M
parameters. **LoRA** does not train `W`. It freezes `W` and learns two small
matrices `A` `(r, in)` and `B` `(out, r)` with rank `r` (e.g. 16), then adds
their product:

```text
W_effective = W + B·A
            (out, in) = (out, in) + (out, r)·(r, in)
```

Check the shapes: `(out, r)·(r, in) → (out, in)`, the `r`s cancel — it lines up
with `W` exactly, so the sum is legal. Parameter count drops from `out·in`
(4.2M) to `r·(out+in)` (~65K), ~1.5% of full fine-tuning. **The entire reason
LoRA works is the shape arithmetic in this session:** a big matrix is
approximated by the product of two skinny ones. See
[`../lora_guide.md`](../lora_guide.md) and
[`../factory/lora-geometry.md`](../factory/lora-geometry.md) — the "geometry" in
that title is literally these matrix shapes and the rank between them.

---

## Reading a real shape error

```text
RuntimeError: mat1 and mat2 shapes cannot be multiplied (8x512 and 2048x2048)
```

Decode it with the cancellation rule:

- `mat1` is `(8, 512)` — a batch of 8, each a 512-vector.
- `mat2` is `(2048, 2048)` — a weight expecting 2048 inputs.
- Inner dims: `512` (mat1) vs `2048` (mat2). They do not match.

The activation is 512-wide but the layer wants 2048. Either the wrong layer is
being applied, or an earlier projection that should have widened 512→2048 was
skipped. You did not need to know the model to localize the bug — only the
shapes.

---

## Self-check

Don't peek:

1. **A layer has weight shape `(768, 256)`.** What input vector length does it
   expect, and what output length does it produce?
2. **You multiply `(4, 3)` by `(3, 5)`.** What is the output shape, and which
   number cancelled?
3. **Why can a bias of shape `(512,)` be added to activations of shape
   `(8, 256, 512)` but a bias of shape `(256,)` cannot?**
4. **LoRA on a `(4096, 4096)` matrix with rank 8.** How many parameters does it
   train, versus full fine-tuning? (Full: `4096²`. LoRA: `8·(4096+4096)`.)
5. **Trap:** a matmul reports shapes `(8, 256, 512)` and `(512, 2048)`. Does
   this work, and what is the output shape? (Yes — the matmul hits the last
   axis; output `(8, 256, 2048)`.)

---

## Where this connects

- **Back to Session 2:** `y = mx + b` was a length-1 dot product. Nothing new
  was added — only more indices.
- **Forward to Session 10 (attention):** attention is three matrices Q, K, V and
  two matmuls (`QKᵀ`, then `·V`). You cannot follow attention without the
  cancellation rule from this session.
- **Repo anchors:** posttrainllm's math oracle is
  [`python_ref/model.py`](../../python_ref/model.py);
  [`webgpu/matmul*.wgsl`](https://github.com/PostTrainLLM/posttrainllm/blob/main/webgpu) is the same math optimized;
  [`llm-mechanics-fundamentals.md`](llm-mechanics-fundamentals.md) covers the
  attention/MoE shapes that build on this;
  [`essential-vs-optimization.md`](essential-vs-optimization.md) is the doctrine
  that these shapes define the model and everything else is speed.
- **Factory consequence:** every LoRA rank sweep, every "why did this adapter
  regress breadth" question, and every OOM you hit is a statement about these
  shapes and how big they are. Rank is a shape choice with a cost and a
  capacity, nothing more.
