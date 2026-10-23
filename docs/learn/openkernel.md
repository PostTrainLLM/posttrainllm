# Open Kernel Challenge

Owner-selected experiment, 2026-10-23:
[Issue #206](https://github.com/PostTrainLLM/posttrainllm/issues/206).
Question: can a rules-compliant kernel beat SGLang on the organizer's H200?
Timebox: October 23–24, 2026, in the owner's Asia/Kolkata timezone. This is a
two-day kernel experiment; the later serving competition is outside scope.
This is an isolated CUDA experiment; the Mac application has no new dependency.

## Current state

October 23 batch complete: 19 judge jobs, including six scored runs. All four
baselines and the selected scored candidates passed on the organizer's H200,
with no flags:

| Candidate | Scored speedup | Reported 95% interval | Status |
| --- | --- | --- | --- |
| Fused attention preparation | 1.1357× | 1.1187–1.1528× | Passed; every benchmark shape improved |
| MoE global-expert block sizing | 1.0645× | 1.0485–1.0804× | Passed; gains concentrated at 128–256 tokens |
| Router dispatch, BK128 | 1.0534× | 1.0376–1.0692× | Passed; fusion limited to 5–16 tokens |
| Combined decoder layer, narrowed MoE dispatch | 1.0351× | 1.0196–1.0506× | Passed; every benchmark shape improved |

The original router passed correctness but regressed to 0.8443×; its source
remains in commit `fa8bd98` and the local receipt. A subsequent check measured
1.98× at eight tokens and 1.13× at sixteen, with regressions elsewhere. The
current candidate uses fusion only for 5–16 tokens and the baseline otherwise.
The larger-token tile check measured 1.0088× with an interval including 1×;
it is inconclusive and not promoted. The selected BK128 small-token variant
scored 1.0534×, with router cases at 2.38× for eight tokens and 1.40× for sixteen.
The earlier BK64 variant scored 1.0309×; the aggregate intervals overlap, so
these runs do not establish the whole score difference as a tile-size effect.

The full-layer candidate incorporates attention and MoE changes while preserving
the layer's FP32 small-batch router and stream ordering. The initial combined
version passed all 13 correctness cases and scored 1.0254×, but regressed at
32 tokens in both check and scored runs. The selected fallback preserves
baseline MoE tiling below 256 tokens; it passed fresh correctness and improved
all 12 benchmark shapes. Its aggregate interval overlaps the initial version's;
selection also uses recovery of the measured shape regressions.
See [results.json](../../experiments/openkernel/results.json) for dated job IDs,
exact source hashes, correctness cases, per-shape timings and aggregate results.
Seven outcomes are indexed in the existing [attempt ledger](../attempt-ledger.md)
and [structured history](../attempts.json), including regressed and inconclusive
variants. These results establish the organizer workloads only, not Mac
application or end-to-end serving gains. No paid GPU was provisioned.

Research agents inspected requirements, repository fit, attention/MoE code and
the measured router regression. Claude reviewed the approach and candidates.
Local snapshots under ignored `runs/openkernel/<job>/` preserve exact submitted
source, hashes and raw judge results. The published timing-floor table is not
measured baseline timing; decisions use actual judge profiles.

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

Submissions are Apache-2.0 licensed under the challenge terms. This candidate's
baseline-compatible wrapper follows the supplied SGLang baseline; the split-K
router kernel is new experiment code. Official reference/harness files remain
local, unmodified, and outside the submitted single file.
