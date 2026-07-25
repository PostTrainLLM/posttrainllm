# Factory Overview

posttrainllm's active product is the specialist factory.

The factory should turn a base model plus task data into a measured specialist
artifact:

```text
target -> data -> post-training -> eval -> package -> report
```

For the fuller project/learning split and the post-training pillar map, see
[`post-training-factory.md`](post-training-factory.md).

## Factory Contract

A valid factory run has:

- a frozen target
- a frozen baseline
- a dataset manifest
- a training config
- an eval result before and after training
- a packaged artifact or explicit rejection
- a report with cost, latency, regressions, and decision

Anything else is research or tooling. It may be valuable, but it is not the
factory proof.

## Current Assets

Use these before adding new tooling:

- Data: `traces-to-data`, `corrections-to-data`, `quality-filter`,
  `reasoning-classify`, `dedupe`, `download-dataset`, `extractor-data`.
- Post-training: `sft`, `dpo`, `distill`, `es`, `merge`, `bake-lora`.
- Evals: `eval-gate`, `eval-compare`, `eval-bfcl`, `eval-tau-bench`,
  `run-lm-eval`, `eval-humaneval`, `eval-sql`, `eval-router`,
  `eval-scaledown`, `eval-escalate`.
- Packaging: `export-mlx`, specialist package directories under
  `specialists/`, `posttrainllm.project.json` / lock metadata.
- Runtime checks: `serve`, `bench`, `run-bench`, smoke scripts in `evals/`.

## First-Class Output

The output of the project is not just a model. It is a folder that proves what
happened:

```text
runs/<date>-<target>/
  config.json
  run-status.json
  dataset.json
  train.log
  eval-baseline.json
  eval-candidate.json
  report.md
  artifact.json
  decision.json
```

For new lifecycle-v1 runs, `run-status.json` makes in-progress phase, revision,
and last durable transition explicit. It is operational metadata only:
`decision.json` remains the outcome authority and the publish gate remains
independent. Existing folders without status remain valid legacy evidence.
See [`run-lifecycle.md`](run-lifecycle.md).

`runs/` is local output and is gitignored. Commit schemas, fixtures, and shipped
specialist package metadata instead.

## Factory Run Center

The polish/UI center should be a readout of the factory, not a separate product
surface yet.

Minimum useful readout:

- runs
- active/terminal lifecycle phase, revision, update time, and stale warning
- target
- dataset version
- base model
- training method
- eval score
- regression score
- cost/time
- latency/RAM/tok-s
- artifact path
- decision

CLI first. UI second.

The Mac app reads the shared pure-IO lifecycle contract only when the operator
presses Refresh. It does not run a background scheduler, transition runs, resume
training, or gain publication authority.
