# Open Kernel Challenge

Owner-selected experiment, 2026-10-23:
[Issue #206](https://github.com/PostTrainLLM/posttrainllm/issues/206).
Question: can a rules-compliant kernel beat SGLang on the organizer's H200?
Timebox: October 23–24, 2026, in the owner's Asia/Kolkata timezone. This is a
two-day kernel experiment; the later serving competition is outside scope.
This is an isolated CUDA experiment; the Mac application has no new dependency.

## Current state

Two bounded rounds complete: 28 organizer H200 jobs, comprising 18 checks and
10 scored runs. Twenty-seven passed correctness; one attention draft failed GPU
compilation and was corrected. All four selected scored sources passed fresh
correctness with no flags:

| Candidate | Scored speedup | Reported 95% interval | Measured scope |
| --- | --- | --- | --- |
| Narrow paged split-K attention + fused prep | 1.2804× | 1.2612–1.2996× | All 12 shapes faster than SGLang |
| MoE block sizing + fused small-batch norm | 1.2236× | 1.2053–1.2420× | Small-batch gains; 32-token case 0.988× |
| Single-token GEMV + narrow router dispatch | 1.0673× | 1.0513–1.0834× | One-token projections 1.13–1.20× |
| Decoder layer + fused small-batch expert norm | 1.1070× | 1.0903–1.1236× | All 12 shapes faster than SGLang |

At 2026-10-23 19:39 UTC (October 24, 01:09 Asia/Kolkata), the live overall
rank was **321 of 586**, versus 369 of 546 before the second round. Individual
ranks were attention 219/329, dense 449/481, MoE 317/380 and layer 252/284.
The field grew during the runs; these are dated snapshots, not fixed placements.
Results improved, but placement remains outside the top 50.

See [results.json](../../experiments/openkernel/results.json) for every job ID,
exact source hash, correctness case, per-shape timing, evaluator image and the
leaderboard snapshot. Thirteen outcomes from the two rounds are indexed in the
existing [attempt ledger](../attempt-ledger.md) and
[structured history](../attempts.json), including failures and regressions.
These results establish organizer workloads only, not Mac application or
end-to-end serving gains. No paid GPU was provisioned.

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
256 tokens. The new GEMV and split-K attention are **not** composed into this
layer source; that would require a separate full-layer correctness and timing run.

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
2.05×. No tuning or GPU jobs remain running from this round.

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
while the current API/site says November 19. Neither date affects this two-day timebox.

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
