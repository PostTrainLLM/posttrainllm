# Factory Run Schema

Each real factory run should write a local run directory:

```text
runs/<YYYY-MM-DD>-<target-slug>/
  config.json
  run-status.json      (required for newly created lifecycle-v1 runs)
  dataset.json
  train.log
  eval-baseline.json
  eval-candidate.json
  slice-metrics.json
  trace_review.md
  provenance.json
  report.md
  artifact.json
  decision.json
  eval-validity.json   (optional)
  cost.json            (optional)
```

`runs/` is ignored by git. Commit only small fixtures or final specialist
package metadata.

The typed Swift representation lives in
`native-mac/Sources/TinyGPTIO/FactoryRun.swift`. Keep this document and that
type in sync; it is intentionally in the pure IO target so report/dashboard
code can parse run metadata without loading MLX or a checkpoint.

Operational phase state lives in the separate
[`run-lifecycle.md`](run-lifecycle.md) contract. `run-status.json` records
progress and recovery metadata only; `decision.json` remains the quality and
product-outcome authority. Existing folders without lifecycle metadata remain
valid legacy folders.

Use the CLI wrapper to render or validate a folder:

```bash
posttrainllm factory-run render \
  --config config.json \
  --dataset dataset.json \
  --baseline eval-baseline.json \
  --candidate eval-candidate.json \
  --decision decision.json \
  --artifact artifact.json \
  --out runs/<id>

posttrainllm factory-run validate runs/<id>
posttrainllm factory-run status --json runs/<id>
posttrainllm factory-run list --active runs/
```

## Assembling a folder from emitted fragments

When the train/eval/decision steps drop their fragments (`config.json`,
`dataset.json`, `eval-baseline.json`, `eval-candidate.json`, `decision.json`,
optionally `artifact.json` / `slice-metrics.json` / `trace_review.md`) into the
run directory, assemble the derived files (`provenance.json`, `report.md`,
`train.log`) with the generic bridge:

```bash
python3 scripts/assemble_factory_run.py runs/<id> --publish-check
```

It is metadata-only (no server, no training, no GPU eval): it computes the eval
delta, hashes the real dataset sources into `provenance.json`, renders the
`reports.md` template, and — with `--publish-check` — runs
`check_factory_run_publish.py --allow-report-only`. The output validates against
the typed Swift `FactoryRunFolder`. `scripts/render_sql_factory_run.py` remains
the SQL-specific one-shot renderer for the routed POC.

The assembler initializes lifecycle metadata when absent, advances to
`reporting` only after derived artifacts are durably written, then advances to
`decided` only after `decision.json` is present. A post-initialization assembly
failure records only the bounded `assembly-failed` code and generic sanitized
summary.

## Live command evidence

For a new lifecycle run, freeze and validate `config.json` and `dataset.json`,
initialize the lifecycle, and advance it to `data-ready` before model work.
The following opt-in flags then record evidence at the command boundary:

```bash
posttrainllm sft <base> --data <train.jsonl> --out <adapter.lora> \
  --factory-run runs/<id>

posttrainllm eval-gate --spec <eval-gate.json> \
  --candidate <candidate.jsonl> --factory-run runs/<id>

posttrainllm eval-compare <baseline-and-candidate.jsonl> \
  --factory-run runs/<id>
```

`sft` requires `data-ready`, marks `training` before model loading, and writes a
bounded `train.log`, measured local training time in `cost.json`, and an
unshipped adapter `artifact.json` before marking `trained`. An interrupted or
failed command remains in the last honest active phase for explicit operator
reconciliation; a partial adapter is not promoted as trained evidence.

`eval-gate` requires `trained`, verifies that the frozen primary suite and
baseline E0 rows exist before suite execution, and writes the same gate's
typed `eval-baseline.json` and `eval-candidate.json` before marking
`evaluated`. A quality-gate failure is still a completed evaluation and is
recorded honestly with `passed: false`.

`eval-compare` derives `slice-metrics.json` only when its E0 inputs name exactly
one baseline and one candidate with compatible metrics and instance counts. It
does not change lifecycle or decision state. None of these commands creates
`decision.json`, assembles a report, packages, publishes, or deploys.

The no-model contract smoke is:

```bash
bash evals/factory-run-live-evidence-smoke.sh
```

## `run-status.json` and discovery pointers

New native renders and Python assemblies are lifecycle-v1 writers. They emit
`run-status.json` and atomically refresh advisory `current-run.json` /
`latest-run.json` files in the run root. Readers always verify a pointer against
the target status; scanning status files is the repairable source for discovery.

Lifecycle metadata is intentionally optional during reads so historical run
folders keep the same validation and publication semantics. Use
`factory-run init --import-legacy`, never ordinary validation, to create an
honest imported snapshot. See [`run-lifecycle.md`](run-lifecycle.md) for the
schema, transition graph, CAS rules, stale-active policy, and recovery commands.

## `config.json`

```json
{
  "run_id": "2026-07-02-pace-planner-sft-v1",
  "target": "pace-planner",
  "owner_goal": "Improve Pace planner action grounding without breadth regression.",
  "base_model": {
    "id": "Qwen/Qwen3-4B-Instruct-2507",
    "revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
    "precision": "bf16"
  },
  "candidate": {
    "method": "sft-lora",
    "adapter_format": "tgla",
    "training_command": "posttrainllm sft ..."
  },
  "eval": {
    "primary": "pace-v11-ship-gate",
    "regression": "bfcl-heldout-breadth",
    "primary_slice": "pace_v11_heldout",
    "regression_slice": "bfcl_breadth",
    "threshold": {
      "primary_min": 0.95,
      "breadth_drop_max_pp": 3
    }
  }
}
```

`primary_slice` and `regression_slice` are optional and name the entry in
`slice-metrics.json` that carries each gate's row count and — for the regression
gate, which has no `eval-*.json` pair of its own — its baseline/candidate scores.

State them whenever the slices exist. The [report card](report-card.md) will not
guess: without a pointer the gate's sample size and before/after evidence are
reported as `missing`. Naming a slice that is absent from a present
`slice-metrics.json` is a hard error, not a silent downgrade.

## `dataset.json`

```json
{
  "dataset_id": "pace-planner-v11-sft",
  "sources": [
    {
      "kind": "trace",
      "path": "evals/...",
      "rows": 709
    }
  ],
  "processing": {
    "dedupe": true,
    "quality_filter": true,
    "heldout_split": "locked"
  },
  "counts": {
    "train_rows": 0,
    "heldout_rows": 0,
    "dropped_rows": 0
  }
}
```

## `eval-baseline.json` and `eval-candidate.json`

Use the existing E0/eval-gate shape when possible. Add run metadata around it
instead of inventing another scoring format.

Required fields:

- model id
- command
- suite
- score
- pass/fail
- date
- latency if available
- RAM/peak RSS if available
- notes on non-determinism or skipped checks

## `slice-metrics.json`

Reports the primary metric by meaningful task slice. For SQL, generate it with:

```bash
python3 scripts/score_sql_slices.py <eval-row-trace.jsonl> --out slice-metrics.json
```

Required fields:

- overall score
- slice names
- rows per slice
- score per slice

Do not publish an overall-only win if the artifact is meant to be a specialist.

## `trace_review.md`

Qualitative failure review. For SQL, generate it with:

```bash
python3 scripts/review_sql_trace.py --rows <rows-or-preds.jsonl> --out trace_review.md
```

Required checks:

- reward hacking
- hallucinated schema/API/tool
- fake reasoning or prose wrappers
- format collapse
- incorrect-but-plausible answers

## Optional report-card fragments

These two fragments record evidence the base schema has no home for. Both are
optional and absent-tolerant: without them the matching
[report-card](report-card.md) fields stay `missing` rather than being zero-filled,
so existing run folders keep validating and compiling unchanged.

### `eval-validity.json`

Required for a report card to present a **fully verified** ship.

```json
{
  "frontier": {
    "model": "gpt-5.5 via codex exec",
    "command": "python3 scripts/bfcl_multiturn_codex.py ...",
    "date": "2026-07-20",
    "by_suite": { "pace-v11-ship-gate": 1.0 }
  },
  "frozen_eval": {
    "id": "pace-v11-heldout",
    "rows": 120,
    "sha256": "<hash>",
    "note": "Locked before training."
  },
  "overlap_check": {
    "result": "no-overlap",
    "command": "python3 scripts/<overlap checker>.py",
    "note": "0/120 held-out prompts appear in train."
  },
  "known_limitations": ["Single-reference exact match on 8 rows."]
}
```

Attribution is **per suite only**: a frontier ceiling is a property of a
benchmark, not of a run, so a suite with no `by_suite` entry has no recorded
ceiling and cannot contribute to a verified ship.

`frontier.by_suite` keys are eval suite names, so the primary and regression
gates can carry different ceilings. `overlap_check.result` must be exactly
`no-overlap` or `overlap-detected`; the latter blocks publication. Per
[`eval-protocol.md`](eval-protocol.md), a benchmark a frontier model cannot ~ace
is a broken ruler — record the score honestly rather than omitting it.

### `cost.json`

```json
{
  "training_time_seconds": 1840,
  "training_cost_usd": 0,
  "training_cost_usd_note": "Local run; no paid model API was used.",
  "eval_time_seconds": 260
}
```

Any `<field>_note` is carried into the report card beside the value. Omit a field
entirely rather than writing `0` for "not measured".

## Publish Check

Before publishing or releasing a run report, run:

```bash
posttrainllm factory-run publish-check --allow-report-only runs/<id>
```

Before shipping a package, run without `--allow-report-only`:

```bash
posttrainllm factory-run publish-check runs/<id>
```

See [`enforcement.md`](enforcement.md) for the exact enforcement layers.

To compile the run into a portable public proof artifact, use
[`report-card.md`](report-card.md).

## `provenance.json`

Machine-readable reproducibility metadata:

```json
{
  "schema_version": 1,
  "renderer": "scripts/render_sql_factory_run.py",
  "renderer_command": "python3 scripts/render_sql_factory_run.py --out <run-dir>",
  "git": {
    "commit": "<sha>",
    "branch": "main",
    "dirty": true
  },
  "commands": {
    "baseline": "posttrainllm generate ...",
    "candidate": "scripts/run_sql_routed_generate.py ...",
    "training": "posttrainllm sft ...",
    "publish_check": "posttrainllm factory-run publish-check --allow-report-only <run-dir>"
  },
  "datasets": [
    {
      "path": "evals/...",
      "rows": 50,
      "sha256": "<hash>"
    }
  ]
}
```

Required fields:

- git commit, branch, dirty flag
- exact baseline/candidate/training command strings or explicit pointers
- dataset paths, row counts, and SHA-256 hashes
- renderer and publish-check command

## `artifact.json`

```json
{
  "artifact_id": "pace-planner-sft-v1",
  "kind": "adapter",
  "path": "~/.cache/posttrainllm/models/pace-planner-sft-v1",
  "base_model": "Qwen/Qwen3-4B-Instruct-2507",
  "format": "tgla",
  "package_dir": "specialists/pace-planner-sft-v1",
  "shipped": false,
  "routing_constraint": null
}
```

`routing_constraint` is optional. Set it to the named route or task envelope the
artifact is safe inside. A shipped candidate whose regression or breadth gate
failed may only publish a report card with this set — see
[`report-card.md`](report-card.md#publication-gate).

## `decision.json`

```json
{
  "decision": "ship",
  "reason": "Primary score cleared threshold with acceptable breadth retention.",
  "failure_reason": null,
  "failure_reason_confidence": "not-applicable",
  "lesson": "This recipe passed the frozen gates without hidden blockers.",
  "next_action": "Register specialist package and add model card.",
  "evidence_sources": [
    "report.md",
    "eval-candidate.json",
    "trace_review.md"
  ],
  "blocked_by": []
}
```

Allowed decisions:

- `ship`
- `reject`
- `retry-data`
- `retry-training`
- `retry-eval`
- `park`

`failure_reason_confidence` must be one of:

- `exact`
- `inferred`
- `missing-evidence`
- `not-applicable`

Non-`ship` decisions must include `failure_reason`, `lesson`, and at least one
`evidence_sources` entry. `ship` decisions should use
`failure_reason_confidence: "not-applicable"` and still include evidence sources
for the positive claim.

## `report.md`

Use the template in `docs/factory/reports.md`. Reports must include an
`## Evidence / Exactness` section matching `decision.json`.
