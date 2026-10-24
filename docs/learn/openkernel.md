# Open Kernel Challenge

Owner-selected experiment, October 23–24, 2026 (Asia/Kolkata):
[Issue #206](https://github.com/PostTrainLLM/posttrainllm/issues/206).
Question: can a rules-compliant kernel beat SGLang on the organizer's H200?
This is an isolated CUDA experiment; the Mac application has no new dependency.
Only the free official queue is authorized. Serving and paid GPUs are outside scope.

## Current state

At 2026-10-24 05:45 UTC the overall rank was **414 of 740**. All 53 earlier
jobs completed. One final check is queued, bringing the submitted total to 54.
The previous autonomous worker is stopped; no unrestricted iteration remains.
These are dated leaderboard observations, not fixed placements.

| Selected exact-source scored candidate | Speedup | Reported 95% interval |
| --- | --- | --- |
| Joint-head FP8 paged attention | 1.3723× | 1.3517–1.3995× |
| MoE block sizing + fused small-batch norm | 1.2236× | 1.2053–1.2420× |
| Single-token GEMV + narrow router dispatch | 1.0673× | 1.0513–1.0834× |
| Composed decoder layer | 1.1366× | 1.1196–1.1537× |

All selected sources passed fresh correctness with no flags. Attention score
`939615aea8b24931` is 7.18% above its earlier 1.2804× incumbent, and its exact
scored source is now selected locally. The layer target has not been reached.
See [results.json](../../experiments/openkernel/results.json) for all job IDs,
source hashes, correctness cases, per-shape timings and evaluator identities.
Check results are off-board and are not scored submissions or serving evidence.

## One final bet and stop condition

On October 24 the owner authorized **one best bet, then quit unless overall
rank reaches the top 100**. This supersedes the prior freeze and the top-ten
aspiration. No parameter sweep, paid GPU or alternate candidate is authorized.

Final check `b5f1d79d24524705` uses
[final-layer.py](../../experiments/openkernel/candidates/final-layer.py), SHA-256
`48655c1bef954efc8c894169eacc504c1338a44a102e18a62bd5a4d1f329e894`.
It combines the checked norm/local-ID fusion, joint-head attention and whole-row
small projections with one new scheduling change: align only local expert routes,
discard negative IDs, and use Marlin's non-EP specialization. Every valid route,
weight, numerical boundary and fresh input remains part of the computation.
This removes repeated scans of invalid expert blocks, not valid GEMM arithmetic.
No causal attribution to that change alone will be made from this composition.

Claude and an independent source reviewer checked negative-ID filtering,
all-invalid routing, padding sentinels, masked scratch reads and FP32 router input.
The pinned AOT align kernel supports `ignore_invalid_expert`; the separate JIT
implementation Claude initially inspected does not establish that API contract.
Source review and local lint passed; CUDA compilation, correctness and timing
remain pending on the H200 check.

The exact source may receive at most one scored run if it passes with no flags,
its point estimate exceeds the strongest prior layer check (1.179121×) by at
least 3% (at least 1.214495×), its lower reported interval exceeds 1.196808×,
and every matched benchmark case has at most 5% latency regression against that
prior check. The bounded watcher enforces these conservative gates; otherwise stop.
After scoring, refresh overall rank and stop if it is outside the top 100.
Local `runs/openkernel-control/submission-policy.json` and its guarded launcher
bind this allowance to the exact source and reserve each job slot before sending.

## Completed continuation evidence

| Trial | Speedup | Decision |
| --- | --- | --- |
| Norm plus local-ID layer fusion, `ec00131830f54653` | 1.1791× | Strongest prior layer check; unscored |
| Joint-head attention in layer, `0c5c8d83f1fa489f` | 1.1628× | Failed earlier 3% and nonoverlap gate |
| Whole-row dense/router, `350b4c2c87ef4312` | 1.1131× | Component check passed; used in final composition |
| Attention merge/norm/gate fusion, `a848d0b7c8794535` | 1.3068× | Below selected attention |
| Wider attention key tile, `30ed1e95b2984d51` | 1.2293× | Reject; 255 registers and 96 spills in large full decode |
| Shared-load verification attention, `583215fc82cb43db` | 0.8432× | Reject; 254–255 registers, zero spills |
| Grouped BF16-decoded NVFP4, `59b8264c0c8d4e59` | 0.2987× | Reject; 96 registers, zero spills; GEMMs dominate |
| Single-token direct tensor-core MoE, `cac9617e49ed43eb` | 0.9063× | Reject versus Marlin |
| Global-density tile at M128, `048fe1129b344184` | 1.1346× | No layer gain; not repeated |
| Lossless M1 / larger-tile dense pooler | 1.0310× / 1.0466× | Below selected dense |

Diagnostic profiles place attention at roughly 50–55% of summed kernel duration
in larger full-context decode, and expert GEMMs at 44–51% in larger verification.
Overlapping streams mean these percentages are not additive end-to-end savings.
Compiler register/spill counts do not identify the hardware limiter by themselves.

Research used primary [FlashInfer competition winner reports](https://github.com/flashinfer-ai/mlsys26-contest/tree/main/writeups),
[FlashAttention-3](https://tridao.me/blog/2024/flash3/) and
[H100 kernel-boundary analysis](https://hazyresearch.stanford.edu/blog/2025-05-27-no-bubbles).
Blackwell FP4 instructions and TMEM recipes are not H200 drop-ins. Marlin already
provides pipelined packed-weight execution; a raw Triton rewrite regressed badly.
The remaining scheduling bet is source-supported but does not establish a path
to top 100. Earlier research and failed attempts remain evidence, not a backlog.

A separate Hugging Face diagnostic batch was rejected before launch (402/403).
No paid GPU job was created. Every measured result here is from official H200 jobs.

## What the second round changed

The single-token GEMV uses one launch for dense projections,
while preserving other dense dispatch and the measured 5–16-token router path.
Scored run `1095cf9b43bf49a0` measured 1.0673×, versus the first round's 1.0534×.
Their aggregate intervals overlap; the stronger evidence is that all four
one-token projection gains repeated in check and scored runs. The router itself
is unchanged in this round.

Claude identified the small-batch PyTorch fallback in SGLang's post-expert norm
wrapper; an agent traced its numerical and sentinel contracts. The candidate
launches the existing Triton norm kernel below 32 tokens, preserving FP32
reduction, weight-first normalization and invalid-expert masking. Scored run
`20b3199ecbd847f2` measured 1.2236×, versus 1.0645× previously, with small-batch
cases at 1.22–1.49×. The unchanged 32-token path retains a small regression.
The imported helper is pinned to SGLang's
[fused norm implementation](https://github.com/sgl-project/sglang/blob/a55ab7d5ae1bba59ac351e55026fe7f7644ecc5f/python/sglang/kernels/ops/muse_spark_v12/fused_post_expert_norm_weighted_sum_triton.py).

The same norm change passed inside the full decoder layer. Scored run
`1c749497f0bf4c89` measured 1.1070×, versus 1.0351× previously. It retains the
layer's FP32 small-batch router, stream ordering and baseline MoE tiling below
256 tokens. That round did not compose GEMV and split-K attention into the layer.
Continuation check `2928071145b44c58` and scored run `e5f50469aadf4638` now
qualify that composition at 1.1366x; the exact scored bytes are selected.

The new attention kernel uses paged GQA split-K with live cache metadata, every
legal key, FP32 online softmax and split reduction. FP8 Q/K/V convert losslessly
to BF16; probabilities use BF16, finer than FA3's FP8 probability operands.
The first draft failed compilation because masked FP8 loads used integer zero;
floating-point zero fixed that backend type error. The broad dispatch then passed
correctness but measured only 1.0564×, below the existing 1.1357× candidate.
Long-context verification at batches 16 and 32 regressed to 0.553× and 0.537×.

The selected dispatch uses custom attention for one-token decoding and
single-request sliding verification on supported page-one/GQA8/unit-scale
configurations. Other shapes retain FA3. Scored run `3439c74e04594576` passed
fresh correctness and measured 1.2804×, with single-request sliding decoding at
2.05×. Those second-round jobs are complete; continuation jobs are listed above.

## Retained first-round evidence

The original broad router passed correctness but regressed to 0.8443×; its source
remains in commit `fa8bd98` and the local receipt. Narrowing fusion to 5–16 tokens
recovered the performance regression. A larger-token tile check measured 1.0088×
with an interval including 1× and was not promoted. BK64 and BK128 router scored
intervals overlap, so they do not establish the whole score difference as a
tile-size effect.

The initial combined layer scored 1.0254× but regressed at 32 tokens. Restoring
baseline MoE tiling below 256 tokens recovered the measured shape regressions
and scored 1.0351×; the selected layer retains that fallback alongside the new
small-batch norm fusion. Component gains are not assumed to compose.

Research agents inspected requirements, repository fit, source and profiles;
Claude reviewed the approach and new kernels. Local snapshots under ignored
`runs/openkernel/<job>/` preserve every exact submitted source and raw receipt.
The published timing-floor table is not measured baseline timing; selection uses
actual judge profiles and comparisons with the incumbent as well as SGLang.

## Lessons carried forward from prior PostTrain experiments

The closest retained predecessor is the WASM/WebGPU kernel work in the
[attempt ledger](../attempt-ledger.md) and
[archived integration lessons](../archive/lessons.md).
The ledger records 3–4× isolated WASM matmul speedups becoming only
1.03–1.06× end-to-end. The older f16-packed-weight experiment became slower
when stacked onto existing tiling; larger register blocks also regressed.
These are historical platform-specific results, not H200 predictions.

For this run, retain failed attempts and exact sources; keep per-shape results
beside the aggregate; preserve numerical checks and baseline fallbacks; and
measure the combined layer before claiming that component gains compose.
The old [headline-speedup correction](../decision_log.md)
also motivates retaining raw judge receipts, GPU identity, evaluator image,
source hashes and intervals. A single fast router case is not the dense board's
speedup, and a component check is not an end-to-end layer result.

## Run

For a fresh machine, install the official `okc` CLI and personally run `okc login`: it asks you to
accept the rules and terms and complete GitHub authentication. Never commit or
print the account token. Organizer judging provides the H200 execution; no
paid host is needed for this first experiment. The Mac cannot validate CUDA.

From the repository root, fetch the official material into a separate scratch
directory first: `okc init` writes a starter named `submission.py`.

```sh
okc init muse_bf16_proj runs/openkernel-official
```

Compare its files against `experiments/openkernel/provenance.json` before using
them. Keep the existing candidate; do not overwrite it with the starter.
Run the untouched baseline first, explicitly naming the problem:

```sh
okc check muse_bf16_proj runs/openkernel-official/baseline.py --json
okc check experiments/openkernel/muse_bf16_proj/submission.py --json
```

Use fresh-input correctness and the per-shape profiles to revise the candidate.
Record candidate SHA-256 and git revision beside each job's JSON in ignored
`runs/`. Retain failures. Treat a gain as inconclusive when the reported interval
includes 1× (the judge uses at least ±1.5%), and investigate material per-shape
regressions. A syntax/lint pass is not
a CUDA compilation, graph-capture, numerical-correctness or speed result.
Enter a scored run after useful measured evidence and review. The judge reruns
fresh correctness and timing for the scored file:

```sh
okc submit experiments/openkernel/muse_bf16_proj/submission.py --json
```

Recheck `okc problems --json` for current limits. On 2026-10-23 each problem
allows 20 checks and 10 scored runs daily, resetting at 00:00 UTC. Same-code
runs can be deduplicated; do not treat a repeated old job as independent timing.
The judge image already contains PyTorch, Triton and SGLang. No CUDA package
is added to PostTrain's normal dependency graph.

## Competition context and sources

The kernel track closes November 4 at 11:59 pm PT. The serving track opens
November 5 at noon PT and supplies an 8×H200 node. Cash prizes are on the
serving board; top-50 overall kernel placement grants queue priority.
Serving changes must be a permitted diff against SGLang commit
`a55ab7d5ae1bba59ac351e55026fe7f7644ecc5f`, not a patch to this repository.
No serving work is planned in this timebox. The terms PDF says the contest ends November 18,
while the API/site at the initial review said November 19. Neither date affects this two-day timebox.

- [Official CLI, API and technical rules](https://openkernelchallenge.dev/llms.txt)
- [Live problem and limits](https://openkernelchallenge.dev/api/v1/problems/muse_bf16_proj)
- [Terms](https://openkernelchallenge.dev/terms.pdf)
- [Serving status](https://openkernelchallenge.dev/api/v1/serving)
- [Triton dot precision](https://triton-lang.org/main/python-api/generated/triton.language.dot.html)

Submissions are Apache-2.0 licensed under the challenge terms. The wrappers and
fused QK/cache preparation follow the supplied SGLang source. The split-K router,
GEMV and paged attention kernels are new experiment code; the post-expert norm
kernel is imported from pinned SGLang. Official reference/harness files remain
local, unmodified, and outside each submitted single file.
