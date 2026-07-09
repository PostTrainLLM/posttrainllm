# Factory Run Schema

Each real factory run should write a local run directory:

```text
runs/<YYYY-MM-DD>-<target-slug>/
  config.json
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
```

`runs/` is ignored by git. Commit only small fixtures or final specialist
package metadata.

The typed Swift representation lives in
`native-mac/Sources/TinyGPTIO/FactoryRun.swift`. Keep this document and that
type in sync; it is intentionally in the pure IO target so report/dashboard
code can parse run metadata without loading MLX or a checkpoint.

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
```

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
    "threshold": {
      "primary_min": 0.95,
      "breadth_drop_max_pp": 3
    }
  }
}
```

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
  "shipped": false
}
```

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
