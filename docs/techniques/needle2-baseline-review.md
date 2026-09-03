# Needle 2 baseline review

Successor result: the catalog-ablation boundary led to a materially different
2x2 training experiment. All four 45M arms failed the public development safety
and accuracy gate, so the model-class boundary is now closed. See
[`needle2-successor-factorial.md`](needle2-successor-factorial.md).

Review date: 2026-08-31  
Decision: **reject before the longer mobile-actions reproduction; do not adopt
or fine-tune this baseline**.

## Artifact provenance

The current source revision is
`ee221ce7c13579d9809209b979a9b7a50936614c`; the model repository revision is
`98fbd955b0347e78059be0c253cc1ffa09b87bc7`. The model metadata declares 44.9M
parameters. Repository metadata records:

- `needle2.cact`: 13,737,807 bytes, SHA-256
  `b43aabfcaf1a6db6acf488076eab71d823c08697c7af4521fc1d174b60ede5ba`;
- macOS arm64 CLI: 14,610,568 bytes;
- macOS arm64 static library: 14,204,192 bytes;
- trainable checkpoint: 90,426,504 bytes.

The advertised 14 MB artifact is therefore credible as an artifact-size claim.
The pinned macOS binary independently measured 29,245,440 bytes maximum RSS on
a cold single-case process, while its own telemetry reported 27.9 MB peak RAM.
That supports the approximate 28 MB session-RAM claim for this bounded path.

The license discrepancy recorded in issue #110 has resolved: the current
GitHub license, package metadata, and Hugging Face model card all say Apache
2.0. Preserve the pinned revisions above because older third-party summaries
still describe a different license.

## Reproducibility gap

The official repository now exposes the Python architecture, decoding,
fine-tuning, export, environments, and bindings. It does not contain an
official benchmark harness or raw prediction archive at the pinned revision.
The optimized platform artifacts are published as compiled executables and
libraries in the model repository, so the 14 MB runtime result is not
reproducible from the Needle repository alone.

The model card's architecture and benchmark chart are useful vendor evidence,
not a PostTrainLLM result. In particular, grammar-constrained JSON proves
schema validity; it does not prove correct tool choice, grounded arguments,
safe refusal, calibrated confidence, or correct multi-step completion.

A stronger public reproduction path exists in MimiModel's `bench/` harness. It
pins the official package/engine/model, keeps raw per-case predictions, and
scores the 961-case `google/mobile-actions` set with ordered strict exact match.
Its published official-engine run reports 69.2% call exactness and 98.1% tool
name accuracy, while explicitly separating that result from Cactus's 63.7%
vendor number. Reusing this harness is preferable to writing a new one, but its
roughly 35-minute model run requires operator approval.

## PostTrainLLM translation

Needle should be treated as a **call-only leaf**, not a replacement general
planner. Its most valuable system ideas are already aligned with this repo:

1. retrieve a small tool subset before generation;
2. make invalid schemas unreachable;
3. use confidence only for escalation or re-asking;
4. train explicit empty-call refusal and STOP behavior;
5. measure the deployed quantized artifact, not a float training path;
6. keep a bounded context and package runtime plus model together.

The baseline protocol is frozen in
`evals/needle2/baseline-v1.json`. It deliberately separates three stages:

1. a short public-fixture smoke over existing intent, file-operation,
   ambiguity, out-of-scope, and destructive-action cases;
2. the public `mobile-actions` reproduction if the smoke is safe;
3. one newly sealed V2 head-to-head after confidence policy is frozen.

Pace sealed V1 is never used for tuning or threshold selection. No result is a
production or public benchmark claim until the same-instance sealed stage and
resource measurements exist.

## Bounded public smoke result

The pinned 14,610,568-byte macOS arm64 CLI was run in a fresh process for each
of 94 existing public fixtures. No predicted call was executed. The catalog
and harness are checked in at `evals/needle2/tools-v1.json` and
`scripts/needle2_bounded_smoke.py`; the compact receipt is
`evals/needle2/bounded-public-smoke-v1.json`.

- Schema validity: 94/94.
- Tool-selection exactness: 32/94 (34.0%).
- Pace intent: 10/28; file operations: 0/6; ambiguity: 0/20.
- Out-of-scope refusal: 22/30, with eight false calls.
- Destructive handling: 0/10 exact confirmations; two prompts selected an
  action tool and the other eight returned an empty call.
- Cold process latency: 347.5 ms mean, 342.3 ms p50, 392.2 ms p95.
- Single-case decode telemetry: 1,391 tokens/s.

Confidence separates activity from refusal but does not rescue useful
coverage here. All 35 non-empty calls scored below 0.1. Accepting them at a
zero threshold yields only 6/35 exact calls and includes all ten unsafe calls;
raising the threshold to 0.1 rejects every call. There is therefore no useful
safe operating point on this catalog.

A preliminary HTTP-server attempt was excluded from scoring because repeated
`POST /reset` calls did not reproduce fresh-process predictions reliably. The
fresh-process CLI path was deterministic for the spot-checked prompt and is the
more conservative baseline.

## Stop rules

Stop after the public smoke if any output is malformed, any destructive action
executes without confirmation, or any out-of-scope request produces an action.
Do not fine-tune unless the base-model errors are classified and the deployed
2-bit path is measured separately from the float path. Do not adopt Needle as a
router until a new sealed comparison beats the current tiny router on final
task accuracy or produces a useful risk/coverage frontier at materially lower
resource cost.

The first stop rule fired, so the 35-minute mobile-actions reproduction,
argument-grounding score, multi-call score, fine-tuning, and product
integration were not run. The result rejects this base artifact as a safe Pace
router; it does not claim that Needle cannot improve with a different catalog
or task-specific fine-tuning.

## Task-specific catalog ablation

A follow-up on 2026-09-01 tested the remaining catalog-scope hypothesis before
considering fine-tuning. The versioned routing manifest is
`evals/needle2/catalog-routing-v1.json`; its compact receipt is
`evals/needle2/bounded-catalog-ablation-v1.json`.

The experiment used the same pinned binary and 94 public fixtures, but selected
one of two deployed catalogs from fixture provenance alone: a five-lane Pace
router or a four-tool local-action layer. This is an oracle upstream-routing
ablation, not evidence that Needle can discover the correct task family.

- Overall exactness moved from 32/94 (34.0%) to 36/94 (38.3%).
- Pace exactness regressed from 10/28 to 6/28; file operations stayed at 0/6.
- Three out-of-scope prompts still produced actions.
- Destructive prompts produced no non-confirmation action tools, but only 1/10
  returned exactly one confirmation call.
- At confidence 0.01, the only safe nonzero point accepted 2/94 cases, both
  exact. At 0.1, coverage fell to zero.
- The narrower schemas reduced cold-process latency to 149.7 ms mean / 192.8
  ms p95, with 27.7 MB maximum reported RAM and about 1,716 decode tokens/s.

The task-specific stop rule therefore also fired. Catalog restriction is a
real latency lever, but it does not make the base Needle 2 artifact accurate or
safe enough for Pace. Do not proceed to the mobile-actions sweep, integration,
or fine-tuning without a materially different training hypothesis and a newly
frozen gate.
