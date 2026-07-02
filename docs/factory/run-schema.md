# Factory Run Schema

Each real factory run should write a local run directory:

```text
runs/<YYYY-MM-DD>-<target-slug>/
  config.json
  dataset.json
  train.log
  eval-baseline.json
  eval-candidate.json
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
tinygpt factory-run render \
  --config config.json \
  --dataset dataset.json \
  --baseline eval-baseline.json \
  --candidate eval-candidate.json \
  --decision decision.json \
  --artifact artifact.json \
  --out runs/<id>

tinygpt factory-run validate runs/<id>
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
    "training_command": "tinygpt sft ..."
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

## `artifact.json`

```json
{
  "artifact_id": "pace-planner-sft-v1",
  "kind": "adapter",
  "path": "~/.cache/tinygpt/models/pace-planner-sft-v1",
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
  "next_action": "Register specialist package and add model card.",
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

## `report.md`

Use the template in `docs/factory/reports.md`.
