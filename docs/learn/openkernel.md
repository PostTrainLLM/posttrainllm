# Open Kernel Challenge

Owner-selected experiment, 2026-10-23:
[Issue #206](https://github.com/PostTrainLLM/posttrainllm/issues/206).
Question: can a rules-compliant kernel beat SGLang on the organizer's H200?
Timebox: October 23–24, 2026, in the owner's Asia/Kolkata timezone. This is a
two-day kernel experiment; the later serving competition is outside scope.
This is an isolated CUDA experiment; the Mac application has no new dependency.

## Current state

The owner completed authentication, and all three component baselines passed on
H200. Two optimized component checks have demonstrated gains:

| Candidate | Check speedup | Reported 95% interval | Status |
| --- | --- | --- | --- |
| Fused attention preparation | 1.1404× | 1.1233–1.1575× | Passed, no flags; scored run queued |
| MoE global-expert block sizing | 1.0643× | 1.0484–1.0803× | Passed, no flags; scored run queued |
| Router dispatch | Pending | Pending | Scored run queued |
| Combined decoder layer | Pending | Pending | Baseline and candidate checks queued |

The original router passed correctness but regressed to 0.8443×; its source
remains in commit `fa8bd98` and the local receipt. A subsequent check measured
1.98× at eight tokens and 1.13× at sixteen, with regressions elsewhere. The
current candidate uses fusion only for 5–16 tokens and the baseline otherwise.
One larger-tile experiment and one small-token tile variant are also pending.

The full-layer candidate incorporates the measured attention and MoE changes.
It preserves the layer's FP32 small-batch router and stream ordering; component
correctness does not establish full-layer correctness. No scored result is
available yet. See [results.json](../../experiments/openkernel/results.json)
for dated job IDs, exact source hashes, status and measured results.

Research agents inspected requirements, repository fit, attention/MoE code and
the measured router regression. Claude reviewed the approach and candidates.
Local snapshots under ignored `runs/openkernel/<job>/` preserve exact submitted
source, hashes and raw judge results. The published timing-floor table is not
measured baseline timing; decisions use actual judge profiles.

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
`runs/`. Retain failures. Reject gains inside the reported interval (at least
±1.5%) and investigate material per-shape regressions. A syntax/lint pass is not
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
