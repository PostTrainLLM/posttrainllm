---
title: The WebGPU execution model (for reading our shaders)
description: The mental model you need to read posttrainllm's WGSL compute kernels and explain them to
  another engineer — device/queue, pipeline, dispatch, workgroups, invocations, bind groups, the
  memory hierarchy — then how our matmul + attention shaders map onto it.
---

# The WebGPU execution model

Just enough of the model to read `webgpu/*.wgsl` and explain it cleanly. The canonical references
are [WebGPU Fundamentals](https://webgpufundamentals.org/) (compute articles) and the
[WebGPU](https://www.w3.org/TR/webgpu/) / [WGSL](https://www.w3.org/TR/WGSL/) specs — this page is
the project-specific connective tissue, not a re-explanation of the spec.

## The six nouns

1. **Adapter / Device / Queue.** The *adapter* is the physical GPU; the *device* is your logical
   handle to it; the *queue* is where you submit work. You record commands, then `queue.submit()`.
2. **Compute pipeline.** A compiled WGSL `@compute` entry point plus its layout. It says "run *this*
   shader function over a grid."
3. **Dispatch.** `dispatchWorkgroups(gx, gy, gz)` launches a 3-D grid of **workgroups**. This is how
   you say "do this kernel that many times." The grid size is *your* tiling decision.
4. **Workgroup.** One cell of the dispatch grid. It is a group of **invocations** that run together,
   can share **workgroup memory**, and can synchronize with `workgroupBarrier()`. Declared in the
   shader: `@workgroup_size(x, y, z)`. The workgroup is the *only* unit with fast shared scratch and
   cheap synchronization.
5. **Invocation.** One thread running the shader once. It knows its position via built-ins:
   `@builtin(global_invocation_id)` (where am I in the whole grid), `@builtin(local_invocation_id)`
   (where am I in my workgroup). Map these to the output element(s) this thread is responsible for.
6. **Bind group.** The shader's argument list: the buffers (and textures/samplers) it reads and
   writes, declared as `@group(g) @binding(b) var<...>`. You bind concrete GPU buffers to those slots
   before dispatch.

## The one rule + the memory hierarchy

**The rule:** invocations can cooperate (share memory, barrier) **only within a single workgroup**.
There is *no* cross-workgroup synchronization inside a dispatch — if workgroup A needs workgroup B's
output, that's a *second* dispatch. This single constraint shapes every kernel: you tile the problem
so each workgroup owns an independent chunk.

The memory tiers, fastest to slowest:

- **Registers** (`var` inside the function) — per-invocation, fastest, scarce. Overflow them and the
  compiler *spills* to device memory (the 8×8-matmul cliff — see [study_guide §8](../guides/study_guide.md)).
- **Workgroup memory** (`var<workgroup>`) — shared by a workgroup, on-chip, fast. The staging area for
  cooperative tiling. Needs `workgroupBarrier()` between "everyone writes" and "everyone reads."
- **Storage buffers** (`var<storage, read>` / `read_write`) — device global memory, large, slow. Your
  inputs/outputs live here. Minimizing trips to this tier is the whole game.

Access mode is load-bearing: `var<storage, read>` must be bound as `read-only-storage`. A mismatch
between the WGSL declaration and the bind-group layout silently returns garbage on Apple/Chromium
(no validation error) — the exact bug in [study_guide §9](../guides/study_guide.md) that drove loss to 88.67.

## How our shaders map onto it

**`webgpu/matmul_blocked.wgsl`** (the [§8](../guides/study_guide.md) walkthrough):
- Dispatch grid = output tiled into 64×64 blocks; one **workgroup per block**, `@workgroup_size(16,16)`.
- Each workgroup cooperatively loads a 64×16 slab of A and 16×64 of B into `var<workgroup>` (one barrier),
  then each of the 256 invocations computes a **4×4 sub-tile of output held in registers**, reading the
  shared slabs instead of global memory. Walk K in tiles of 16, refilling shared each tile.
- Why it's fast: every shared-memory load drives ~16 multiply-adds (compute-bound), not 1 (bandwidth-bound).
  Why 4×4 not 8×8: 8×8's 64-float accumulator spills registers → device memory → slower.

**`webgpu/attention_fa2.wgsl`** (the [§7](../guides/study_guide.md) / [online-softmax](../performance/online_softmax_in_attention.md) walkthrough):
- One **workgroup per `(batch, head, Q-tile)`**. The 16 invocations cooperatively load the Q-tile into
  workgroup memory once, then **stream K/V in blocks**, maintaining the online-softmax running state
  `(m, l, O)` and merging each block — never materializing the `[B,H,T,T]` matrix.
- The FA2 backward *design* recomputes scores from the saved per-row `L = m + log l` (one float/row)
  instead of reading a cached matrix — recompute is cheap, global reads aren't (see `docs/performance/fa2_backward_notes.md`).
  The currently shipped attention gradients are the non-fused `attn_dscores` / `attn_dvalue` in `webgpu/train.wgsl`.

## Explaining it to another engineer (the 30-second version)

"You compile a shader into a *pipeline*, then *dispatch* a grid of *workgroups*. Each workgroup is a
pack of *invocations* (threads) that share fast *workgroup memory* and can *barrier* — but workgroups
can't talk to each other within one dispatch, so you tile the problem into independent per-workgroup
chunks. Inputs/outputs are *storage buffers* (slow global memory) bound via *bind groups*; the trick
in every kernel is to stage a tile into workgroup memory or registers and reuse it many times before
going back to global. Get the bind-group access mode wrong and Apple's driver hands you garbage with
no error — so you trust *end-to-end parity*, not the validation layer."

## References

- Canonical: [WebGPU Fundamentals](https://webgpufundamentals.org/), [WebGPU spec](https://www.w3.org/TR/webgpu/), [WGSL spec](https://www.w3.org/TR/WGSL/).
- Our kernels: `webgpu/matmul_blocked.wgsl`, `webgpu/attention_fa2.wgsl` (FA2 forward), `webgpu/train.wgsl` (shipped attention gradients: `attn_dscores`/`attn_dvalue`).
- Perf rationale + the bind-group bug: [study_guide.md](../guides/study_guide.md) §7–§9.
- The host plumbing (COOP/COEP for `SharedArrayBuffer`, Memory64): [study_guide.md](../guides/study_guide.md) §4, §11.
- Where optimization ends and math begins: [essential-vs-optimization.md](./essential-vs-optimization.md).
