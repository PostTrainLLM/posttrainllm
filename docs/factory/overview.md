# Factory Overview

TinyGPT's active product is the specialist factory.

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
  `specialists/`, `tinygpt.project.json` / lock metadata.
- Runtime checks: `serve`, `bench`, `run-bench`, smoke scripts in `evals/`.

## First-Class Output

The output of the project is not just a model. It is a folder that proves what
happened:

```text
runs/<date>-<target>/
  config.json
  dataset.json
  train.log
  eval-baseline.json
  eval-candidate.json
  report.md
  artifact.json
  decision.json
```

`runs/` is local output and is gitignored. Commit schemas, fixtures, and shipped
specialist package metadata instead.

## Factory Run Center

The polish/UI center should be a readout of the factory, not a separate product
surface yet.

Minimum useful readout:

- runs
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
