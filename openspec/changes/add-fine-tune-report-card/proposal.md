## Why

posttrainllm already records rigorous factory runs, but a third party must understand repo-specific files to judge whether a fine-tune improved the target, damaged breadth, or lacks enough evidence to ship. A portable Fine-Tune Report Card makes the factory's before/after discipline legible without requiring anyone to run training or own a GPU.

## What Changes

- Add a canonical report-card compiler that consumes existing baseline, candidate, eval, performance, and decision artifacts rather than rerunning models.
- Render gains, regressions, slice failures, leakage checks, latency, RAM, throughput, training cost/time, missing evidence, and the `ship`/`retry`/`reject` decision in a stable schema.
- Produce both machine-readable JSON and a public static report surface that distinguishes measured, derived, skipped, missing, and historical values.
- Validate frontier-ceiling and frozen-eval provenance, and fail closed when a claimed result cannot be traced to the source artifacts.
- Dogfood the report card on every Pace specialist run and publish the existing successful, routed, report-only, and rejected candidates as the first honest examples.
- Keep model training, hosted evaluation, weight upload, and GPU execution out of scope; this change packages existing evidence and routes interested users to the factory CLI.

## Capabilities

### New Capabilities

- `fine-tune-report-card`: Canonical evidence ingestion, validation, decision semantics, JSON contract, static rendering, and dogfood/publication workflow for fine-tune comparisons.

### Modified Capabilities

- None.

## Impact

- CLI/scripts: a report-card build and validation entrypoint over canonical factory-run artifacts.
- Schemas: a versioned report-card JSON contract aligned with `docs/factory/run-schema.md` and the existing decision vocabulary.
- Public artifacts: static report pages integrated with the current `/artifacts` inventory and links to reproducible source evidence.
- Quality: fixture-based validation across shipped, routed, retry, reject, missing-evidence, and historical-data cases.
- OpenSpec is initialized on `main` as repo-local planning metadata; no training run, dependency addition, deployment, or model publication is part of this proposal.
