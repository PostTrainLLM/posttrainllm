---
title: Advanced LLM inference & serving — interview-grade map
description: Senior/staff inference-optimization interview topics — KV cache & paging, batching, speculative decoding, quantization, attention kernels/variants, long context, serving architecture — mapped to the best external source and to where this repo touches it.
---

# Advanced LLM inference & serving — interview-grade map

Inference is the half a speech/latency background is strongest in. Format:
**what's probed**, the **single best source**, **in the repo** where real.

## Fundamentals

**1. Roofline: memory-bound decode vs compute-bound prefill.** Decode
reuses huge weight matrices once per token → bandwidth-bound; prefill is
parallel → compute-bound. Derive arithmetic intensity. "Roofline for
prefill vs decode on an H100 — where does each bottleneck?"
*Learn:* [LLM Inference Unveiled (roofline)](https://arxiv.org/abs/2402.16363) · *senior*
*In repo:* `docs/research/mac_decode_baseline_m5pro.md` — native models hit
293–767 tok/s; today's bf16 4B via the HF path managed **7 tok/s**, a
textbook bandwidth-bound-plus-unoptimized-kernel case.

**2. KV-cache memory math.** Size it by hand:
`2·n_layers·n_kv_heads·head_dim·seq·batch·bytes`; why KV (not weights) caps
batch/context. "KV for Llama-3-70B @ 8k, batch 32 — what limits concurrency?"
*Learn:* [PagedAttention/vLLM](https://arxiv.org/abs/2309.06180) · *senior*
*In repo:* `docs/kv_cache_optimization.md`; `Sample.swift` exposes
`--kv-quantize` / `--kv-preallocate`.

**3. TTFT vs ITL vs goodput.** TTFT (prefill-bound), ITL/TPOT
(decode-bound), goodput under SLOs; batch size trades TTFT against ITL.
"p95 TTFT<300ms, ITL<40ms — tune the scheduler." *Learn:* [Inference Trilemma](https://www.digitalocean.com/blog/llm-inference-tradeoffs) · *mid*
*In repo:* Pace's TTFW hunt (330→119ms) is a TTFT story;
[`speech-and-systems-topics.md` §1](speech-and-systems-topics.md).

## Memory & scheduling

**4. PagedAttention.** Naive contiguous KV wastes 60–80% (fragmentation);
OS-style paging + block tables fix it and enable copy-on-write prefix
sharing. *Learn:* [PagedAttention](https://arxiv.org/abs/2309.06180) · *senior*

**5. Prefix / prompt caching (RadixAttention).** Reuse shared system
prompts / few-shot / chat history via a radix tree of KV blocks. "2k-token
shared system prompt — avoid recomputing it per request?"
*Learn:* [SGLang/RadixAttention](https://lmsys.org/blog/2024-01-17-sglang/) · *senior*
*In repo:* Pace sends `cache_prompt: true` on every request — this exact win.

**6. Continuous / in-flight batching.** Iteration-level scheduling injects
/ evicts requests every decode step so the GPU never idles on stragglers.
"Why does static batching tank throughput with heterogeneous lengths?"
*Learn:* [Orca (OSDI'22)](https://www.usenix.org/conference/osdi22/presentation/yu) · *senior*
*In repo:* posttrainllm serve is single-stream — know this as the throughput
lever you'd add for multi-tenant serving.

## Decoding & quantization

**7. Speculative decoding.** Draft proposes k tokens, target verifies in
one parallel pass; rejection sampling keeps the distribution **exact**.
"Why doesn't it change outputs, and when does it lose?" *Learn:* [Speculative Decoding](https://arxiv.org/abs/2211.17192) · *senior*
*In repo:* `SpeculativeDecode.swift` (B14, T=0 byte-equality gate).

**8. Self-speculation (Medusa, EAGLE).** Bolt-on heads / feature-level
autoregression beat a separate draft model on acceptance and avoid serving
two models. *Learn:* [EAGLE](https://arxiv.org/abs/2401.15077) · *staff*

**9. Weight quantization (GPTQ vs AWQ).** GPTQ's Hessian/second-order error
compensation vs AWQ's activation-aware salient-channel scaling; weight-only
int4 helps memory-bound decode. "Pick a scheme for a latency-sensitive 70B."
*Learn:* [AWQ](https://arxiv.org/abs/2306.00978) · *senior*
*In repo:* `posttrainllm gptq` / `hqq` (`GPTQ.swift`, `HQQ.swift`); quantized-HF
checkpoint loading (commit ccf8937) is what let today's A1 load a 4-bit base.

**10. fp8 / activation quant / formats.** fp8 on Hopper/Blackwell, int8
SmoothQuant for activation outliers, GGUF for CPU/edge. "weight-only int4
vs fp8 weight+act — which for throughput, which for accuracy?"
*Learn:* [TensorRT-LLM quantization](https://nvidia.github.io/TensorRT-LLM/blogs/quantization-in-TRT-LLM.html) · *senior*
*In repo:* `posttrainllm gguf-load` / `to-coreml` (the edge/ANE path).

**11. KV-cache quantization.** The lever for long context + large batch;
harder than weight quant (outlier keys, accuracy cliffs). *Learn:* [roofline survey](https://arxiv.org/abs/2402.16363) · *staff*
*In repo:* `Sample.swift --kv-quantize`.

## Kernels, attention & long context

**12. Attention variants MHA/MQA/GQA/MLA.** KV-head sharing shrinks the
cache and raises arithmetic intensity; GQA is the dense standard, MLA
(DeepSeek) compresses KV to a low-rank latent (~90%+ reduction). "Why
MHA→GQA, and what does MLA add?" *Learn:* [GQA](https://arxiv.org/abs/2305.13245) · [MLA/DeepSeek-V2](https://arxiv.org/abs/2405.04434) · *senior*
*In repo:* Qwen3-4B (the A1 base) uses GQA — that's why its KV cache is small.

**13. FlashAttention v2/v3.** IO-aware tiling avoids the N×N matrix; v3
adds Hopper async (warp-specialization, TMA, fp8); recompute-in-backward.
"Why faster despite recomputing softmax stats?" *Learn:* [FlashAttention-3](https://arxiv.org/abs/2407.08608) · *staff*
*In repo:* posttrainllm rides MLX's fused attention — the kernel you *don't* hand-write.

**14. Long context: RoPE scaling + sparse attention.** Position
interpolation vs NTK-aware vs YaRN; sliding-window (Mistral), ring/blockwise
for sequence parallelism. "Extend 4k→128k — what changes and why does naive
interpolation degrade?" *Learn:* [Extending RoPE / YaRN](https://blog.eleuther.ai/yarn/) · *staff*
(RoPE itself: [`advanced-ml-systems-eval.md`](advanced-ml-systems-eval.md) §2.)

## Serving architecture

**15. Disaggregated prefill/decode & chunked prefill.** Split phases onto
separate GPU pools (needs fast RDMA KV transfer) vs co-locate + interleave;
goodput tradeoffs. "Prefill spikes blow your decode ITL SLO — disaggregate
or chunk?" *Learn:* [DistServe](https://arxiv.org/abs/2401.09670) · *staff*

**16. Inference parallelism: TP / EP / multi-LoRA.** TP (split matmuls,
all-reduce/layer, NVLink-bound); expert parallel for MoE (all-to-all, load
imbalance); multi-LoRA serving (many adapters on one base, S-LoRA). "Serve
a 671B MoE on 8 GPUs — TP vs EP vs hybrid?" *Learn:* [Inference Handbook: parallelism](https://handbook.modular.com/inference-optimization/data-tensor-pipeline-expert-hybrid-parallelism/) · *staff*
*In repo:* `serve --lora` is single-base adapter stacking — the seed of
multi-LoRA serving.

## Curated deep-reading path

Use this sequence after the numbered topic map. It moves from the universal
bottleneck model to one-GPU kernels, fused attention, production serving,
quantization quality, and finally multi-accelerator scaling. Papers and books
are mixed deliberately with implementation worklogs: learn the governing idea,
then see it survive contact with code and measurements.

1. **Build the bottleneck model.** [Making Deep Learning Go Brrrr From First
   Principles](https://horace.io/brrr_intro.html) separates compute,
   memory-bandwidth, and framework/launch-overhead regimes. Use that diagnosis
   before reaching for an optimization.
2. **Optimize one foundational kernel.** [How to Optimize a CUDA Matmul Kernel
   for cuBLAS-like Performance](https://quatricmorph.github.io/posts/gpu/)
   progresses through coalescing, shared-memory tiling, block/warp tiling,
   vectorized access, occupancy, and autotuning.
3. **Learn the attention algorithm.** [FlashAttention: Fast and
   Memory-Efficient Exact Attention with
   IO-Awareness](https://arxiv.org/abs/2205.14135) derives why reducing HBM
   traffic changes the algorithm, not just its implementation.
4. **Study the advanced fused kernel.** [A Case Study in CUDA Kernel Fusion:
   FlashAttention-2 on Hopper](https://research.colfax-intl.com/nvidia-hopper-flashattention-2/)
   applies CUTLASS layouts, TMA, WGMMA, asynchronous pipelines, and tile-size
   tradeoffs. Read this after steps 2–3.
5. **Follow kernels through the compiler.** [Triton Kernel Compilation
   Stages](https://pytorch.org/blog/triton-kernel-compilation-stages/) follows
   a kernel from Python AST through Triton IR, GPU IR, LLVM IR, and device code.
6. **Move from a model to a serving scheduler.** [Continuous Batching From
   First Principles](https://huggingface.co/blog/continuous_batching) derives
   ragged batching and dynamic request scheduling from attention and KV-cache
   behavior.
7. **Quantify inference economics.** [All About Transformer
   Inference](https://jax-ml.github.io/scaling-book/inference/) connects TTFT,
   per-token latency, batching, KV memory, arithmetic intensity, and model
   parallelism.
8. **Read a real engine end to end.** [SGLang Deep
   Dive](https://blog.frankzhwei.me/posts/sglang_deep_dive/) tours scheduling,
   RadixAttention, paged KV, CUDA graphs, speculative decoding, kernels,
   distributed execution, and observability.
9. **Measure quantization as distribution drift.** [How Fireworks Evaluates
   Quantization](https://fireworks.ai/blog/fireworks-quantization) explains
   prefill/generation KL divergence and token rejection rate alongside noisy
   task metrics and use-case gates.
10. **Derive the single-chip-to-cluster boundary.** [How to Scale Your
    Model](https://jax-ml.github.io/scaling-book/) develops rooflines,
    Transformer FLOPs, communication collectives, accelerator topology,
    training parallelism, and inference scaling from first principles.
11. **Apply the distributed-training toolbox.** [The Ultra-Scale
    Playbook](https://huggingface.co/spaces/nanotron/ultrascale-playbook)
    combines educational implementations, production Nanotron anchors, and
    measured scaling experiments across data, tensor, pipeline, and context
    parallelism plus ZeRO and communication overlap. It is also indexed in
    [`advanced-llm-training.md`](advanced-llm-training.md).

## Worked performance-engineering case studies

Ali Taha's writing is a useful bridge from the concepts above to measured
kernel and model work. Read the long, code-backed pieces as the durable path;
use the shorter X threads as supplementary field notes.

**Blackwell matmul, from naive kernel to cuBLAS-class performance.** This
four-part series builds the optimization stack incrementally: tiling and the
memory hierarchy, Tensor Cores and TMA, 2-SM MMA and pipelining, then a
persistent CLC scheduler. Keep the result's scope in view: performance claims
are tied to particular Blackwell shapes and configurations.

1. [Introduction](https://www.modular.com/blog/matrix-multiplication-on-nvidias-blackwell-part-1-introduction)
2. [Using the hardware](https://www.modular.com/blog/matrix-multiplication-on-nvidias-blackwell-part-2-using-hardware-features-to-optimize-matmul)
3. [The optimizations behind 85% of SOTA](https://www.modular.com/blog/matrix-multiplication-on-nvidias-blackwell-part-3-the-optimizations-behind-85-of-sota-performance)
4. [Breaking SOTA](https://www.modular.com/blog/matrix-multiplication-on-blackwell-part-4---breaking-sota)

**Quantized inference, end to end.** [Four Bits: 4-bit quantization for
FLUX.2](https://www.baseten.co/blog/four-bits/) connects profiling, NVFP4
blockwise scaling, kernel overhead, calibration, output quality, and
end-to-end latency rather than stopping at a microbenchmark.

**Supplementary field notes.** These are useful snapshots of current model
and kernel work, but their short-form format makes them starting points for
follow-up rather than standalone references:

- [22580: From GPT-2 to Kimi K3, explained](https://x.com/waterloo_intern/status/2081762065392541951?s=20)
- [Notes on writing the fastest video kernel in the world](https://x.com/waterloo_intern/status/2070643039668974060?s=20)
- [TurboQuant](https://x.com/AliesTaha/status/2037272772305707405)
- [Quantization-aware distillation for Qwen 2512](https://x.com/AliesTaha/status/2030074784894308770)
- [Optimizing FLUX.2 on B200](https://x.com/AliesTaha/status/2024493443905683859)

## Suggested order

For targeted interview review, use topics 1–3 first, then 4–6 and 12–13;
read 7 and 9 against the repo implementations. For durable systems learning,
follow the curated deep-reading path in order, then read the Ali Taha case
studies. That makes the Blackwell and FLUX results applications of an existing
mental model rather than isolated performance tricks.
