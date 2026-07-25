# Factory Run Lifecycle

`run-status.json` is the durable operational state for a lifecycle-managed
factory run. It answers which phase last completed and who recorded that
transition. It does not replace `decision.json`, infer quality, resume work,
publish an artifact, or grant deployment authority.

The implementation is pure Foundation in
`native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift`. Lifecycle commands are
metadata-only: they do not initialize MLX, load a model/checkpoint, access the
network, train, evaluate, package, publish, or deploy.

## Status contract

New lifecycle-v1 runs contain:

```json
{
  "schema_version": 1,
  "run_id": "2026-07-25-example",
  "revision": 3,
  "phase": "training",
  "updated_at": "2026-07-25T10:00:00Z",
  "last_transition": {
    "source": "operator",
    "command": "factory-run transition",
    "reason": null
  },
  "parent_run_id": null,
  "successor_run_id": null,
  "failure": null,
  "imported": false,
  "import_evidence": []
}
```

Canonical phases:

```text
created -> data-ready -> training -> trained -> evaluating -> evaluated
        -> packaging -> packaged -> reporting -> decided
```

Any non-terminal phase may move to `failed`. `decided` and `failed` are
terminal. A retry is a new run with `parent_run_id`; terminal history is never
rewritten.

Evaluation-only and report-only flows may use these alternate edges:

```text
created|data-ready -> evaluating
created|data-ready|trained|evaluated -> reporting
```

Every alternate edge requires a lowercase machine-readable reason such as
`evaluation-only`, `report-only`, or `metadata-only-assembly`. A transition to
`decided` requires a valid `decision.json`.

Failure metadata is limited to a machine-readable code and a one-line
240-character summary. Never put command output, paths containing private
material, prompts, completions, rows, predictions, logs, checkpoint state, or
secrets in that summary.

## Operator commands

```bash
# New run with config.json already written
posttrainllm factory-run init --json runs/<id>

posttrainllm factory-run status --json runs/<id>

posttrainllm factory-run transition \
  --phase data-ready \
  --expected-revision 1 \
  --json \
  runs/<id>

# Alternate edge
posttrainllm factory-run transition \
  --phase reporting \
  --expected-revision 1 \
  --reason report-only \
  runs/<id>

# Sanitized terminal failure
posttrainllm factory-run transition \
  --phase failed \
  --expected-revision 3 \
  --failure-code metadata-write-failed \
  --failure-summary "Factory metadata validation failed." \
  runs/<id>

posttrainllm factory-run list --active --json runs/
posttrainllm factory-run list --stale runs/
posttrainllm factory-run reconcile --json runs/          # dry-run
posttrainllm factory-run reconcile --write --json runs/  # explicit repair
```

Every mutation is a compare-and-swap. The caller must supply the revision it
read; a stale revision never overwrites newer state. A short-lived per-run lock
serializes writers, and the status snapshot is replaced atomically on the same
filesystem.

## Discovery and recovery

`current-run.json` points to the most recently updated valid non-terminal run.
`latest-run.json` points to the most recently updated valid terminal run. The
pointers are advisory: readers verify path containment, run id, revision,
phase, and timestamp against the target `run-status.json`. Multiple active runs
are valid and `list` reports all of them.

`reconcile` scans authoritative per-run status files. Dry-run reports malformed
or stale pointers, abandoned `.run-status.*.tmp` files, stale metadata locks,
and proposed repairs. `--write` may rebuild/remove pointers, remove abandoned
temporary files, and remove stale metadata locks. It never kills a process,
changes a run phase, resumes work, or marks a stale run failed.

A non-terminal status older than 24 hours is returned as
`active-with-warning`. It remains active until an operator explicitly
transitions it or creates a linked retry run.

## Legacy compatibility

Folders without `run-status.json` remain readable and publish-compatible.
Lifecycle is required only for folders newly created by lifecycle-v1 writers.
Do not infer legacy status during ordinary validation.

To opt a legacy folder in explicitly:

```bash
posttrainllm factory-run init --import-legacy --json runs/<id>
```

Import records one snapshot at the furthest phase proven by valid files and
sets `imported=true` plus `import_evidence`. It records the import time and
command only; it does not invent earlier transitions or timestamps. A valid
complete bundle may import as `decided`; report-only and partial folders stop
at the evidence they actually contain.
