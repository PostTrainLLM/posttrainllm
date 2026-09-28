# How an LLM actually works (the matmul-first explanation)

**Audience:** anyone who understands "tokens are character chunks, model predicts next token" but wants to see *where matrix multiplication comes in* and *why everything is built around it.*

**Premise:** modern LLMs are basically "a giant pile of matrices that, multiplied in sequence with text input, output sensible text." This doc traces every matmul in a forward pass.

## The 60-second version

| Step | What happens | Matmuls |
|---|---|---|
| Token IDs → vectors | Index rows of the token-embedding table; one-hot × matrix is a mathematical equivalence | 0 |
| Self-attention (per layer) | Project to Q/K/V; compute attention; weighted sum; output projection | 6 |
| Feed-forward (per layer) | Expand → non-linearity → contract | 2 |
| Final projection | Last token's vector × embedding-matrixᵀ → vocabulary scores | 1 |
| Softmax → next token | Normalize vocabulary scores, then select/sample; not a matmul | 0 |

For a **simplified 12-layer illustration**, the displayed six attention plus
two MLP matrix products make **8 × 12 = 96 conceptual products in the body**,
plus one output projection. The input lookup is not a dense matmul. Fusion,
prefill/decode shape, and implementation determine actual kernel launches;
these counts are an anatomy aid, not a latency model. The reference model's
actual layer count comes from `configs/model.byte-tinygpt-v0.json`.

## The full trace

### 0. Token IDs become vectors (a lookup)

The model can't work with token IDs (`42`, `1337`) directly — those are just labels. So:

```
token_id 42  →  embedding[42]  →  a vector of d_model floats
                                   (for Huge: 256 floats)
```

`embedding` is a learned matrix of shape `[vocab_size × d_model]`. Looking
up row 42 is mathematically equivalent to `one_hot(42) · embedding`, but
`torch.nn.Embedding` and this repo's `python_ref/model.py` perform a lookup,
not a dense multiplication. See the [PyTorch Embedding reference](https://docs.pytorch.org/docs/2.14/generated/torch.nn.Embedding.html).

After this, your token "hello" is a 256-number vector. The model now thinks in continuous space.

### 1. Positions represented (method varies)

In the [Python reference](https://github.com/PostTrainLLM/posttrainllm/blob/ffb934d/python_ref/model.py), learned position vectors
are looked up and added to token vectors. Other architectures differ:
[RoPE](https://arxiv.org/abs/2104.09864) rotates attention queries and keys;
[ALiBi](https://arxiv.org/abs/2108.12409) biases query-key attention scores
according to distance. Neither is an addition to token embeddings.

After Steps 0+1 in this reference, the activation has shape
`[batch, sequence_length, d_model]`; each row is an initial representation,
not a fixed meaning independent of context.

### 2-N: transformer blocks (the heavy lifters)

Each block has two sub-layers:

#### Sub-layer A: self-attention (6 matmuls)

```
X is [seq_len × d_model]

Q = X · W_Q       ← matmul: project to "query" space
K = X · W_K       ← matmul: project to "key" space
V = X · W_V       ← matmul: project to "value" space

scores = Q · Kᵀ   ← matmul: every query meets every key
                    shape: [seq_len × seq_len]

softmax(scores) → attention probabilities

output = softmax_scores · V    ← matmul: weighted sum of values
final  = output · W_O          ← matmul: project back to d_model
```

In causal attention, a query compares against keys at its own and earlier
positions only; the mask excludes future positions. See the
[reference implementation](https://github.com/PostTrainLLM/posttrainllm/blob/ffb934d/python_ref/model.py).

#### Sub-layer B: feed-forward MLP (2 matmuls)

```
intermediate = X · W_1     ← matmul: expand d_model → d_mlp (4× usually)
intermediate = GELU(intermediate)   ← non-linearity (element-wise)
output = intermediate · W_2 ← matmul: contract d_mlp → d_model
```

Two matmuls + one non-linearity. The non-linearity is what makes deep networks more powerful than a single matmul — otherwise stacking layers would mathematically collapse to one big matmul.

### N+1: output projection (one matmul)

After all blocks, you have a `[seq_len × d_model]` matrix. Take the last row (the last token's representation after seeing all context):

```
logits = last_row · embedding_matrixᵀ
         ([d_model]) · ([d_model × vocab_size]) → [vocab_size]
```

This reference reuses the input embedding weights (transposed) for the output
projection. This **weight tying** saves a separate output-weight matrix; other
models may use an untied head.

### N+2: softmax + sample (not a matmul)

```
probabilities = softmax(logits)
next_token = argmax(probabilities)  OR  sample(probabilities)
```

Softmax normalizes scores across the vocabulary; then select or sample a
token. Argmax can be applied directly to logits when only the top token is
needed.

## Why matrix multiplication specifically?

Three compounding reasons:

| Why | Detail |
|---|---|
| **Simplest learnable transformation** | `y = W·x` has one free parameter set (W). Easy to differentiate, easy to optimize via gradient descent. |
| **Composes well** | Two stacked matmuls = mathematically one bigger matmul. To get expressive power, you sprinkle non-linearities (GELU, softmax) between them. Non-linearities give the *capacity* to learn; matmuls do the *work*. |
| **Hardware mapping** | Matrix operations can use accelerator hardware efficiently for suitable shapes, precision, and batch size. Actual utilization depends on memory traffic, launch overhead, kernels, and workload. |

## Where the model's "knowledge" lives

Learned parameters include matrices, embeddings, biases, and normalization
parameters. In this reference, the major matrix groups are:

- `embedding_matrix` — what each token "means" as a vector
- `W_Q`, `W_K`, `W_V`, `W_O` (per layer) — what aspects of meaning to compare, how
- `W_1`, `W_2` (per layer) — how to transform each token's representation given context

When you **train**, you learn the values in these matrices via backpropagation.
When you **fine-tune**, you nudge them slightly toward your task.
When you **distill**, a student learns from teacher outputs or trajectories;
its matrices are not normally copied element for element.
When you **quantize**, you represent selected weights or activations at lower
precision, with an accuracy and runtime tradeoff.
When you **prune**, you remove or zero selected weights or structures.
When you **edit** a model, you apply a targeted parameter intervention whose
effect must be checked.

A "22M parameter model" counts **22 million learned scalar values** across
all parameter tensors. Storage depends on dtype and packaging.

## Why size and bandwidth matter

**Why size matters:** more parameters can add capacity, but quality also
depends on architecture, data, training, and evaluation. Parameter count alone
does not predict capability or runtime cost for architectures such as MoE.

**Why memory bandwidth matters at decode:** for an unfused, batch-one dense
model whose weight working set exceeds cache, weight reads can dominate each
token step. A 7B-parameter bf16 weight set occupies about 14 GB before
metadata and other state. `bandwidth / weight_bytes` is a rough weight-traffic
ceiling only under those assumptions; batching, cache reuse, quantization,
KV traffic, compute, and launch overhead change observed tok/s. Always state
model, precision, batch, context, device, and timing boundary before using
such an estimate.

**Why architecture matters:** the operations, routing/state, and their order
determine different speed, memory, and quality tradeoffs.

## Mental model summary

> A decoder language model turns token IDs into vectors, applies repeated
> attention and feed-forward transformations with normalization and residual
> paths, then projects to vocabulary scores. Training adjusts learned
> parameters to reduce an objective; inference uses those parameters without
> a gradient step.
>
> Each generated token depends on a forward step, often with cached earlier
> keys and values. Position representation, normalization, residuals, and
> causal masking materially affect the function and correctness; operation
> counts here describe the illustrated math, not hardware kernel counts.

## Further reading

- 3blue1brown's "Neural Networks" series on YouTube — visual intuition for matmul
- The Annotated Transformer (Harvard NLP) — every line of attention code annotated
- Karpathy's "Let's build GPT" — implements all this from scratch in PyTorch
- `native-mac/Sources/TinyGPTModel/TransformerBlock.swift` — our actual Swift implementation; ~515 lines covering Q/K/V projection, attention, MLP exactly as described above

## Related posttrainllm docs

- `docs/sessions/2026-06-06-mac-specialist-platform.md` — strategy doc; covers memory bandwidth math + tokenization frontier
- `docs/learn/README.md` — active learning index
