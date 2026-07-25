## Context

The canonical factory folder is optimized for completed evidence:
`config.json`, dataset/eval fragments, report, artifact, and `decision.json`.
`FactoryRunFolder` writes those files atomically, training has checkpoint and
lock primitives, and publication has strict validation. Those surfaces do not
form an in-progress run control plane. A partial directory can mean a healthy
active run, an interrupted writer, a historical import, or abandoned output,
and consumers currently have to guess which.

This change spans the pure Swift IO target, metadata-only CLI, Python assembly
bridge, Mac app run discovery, and sanitized Foundry evidence. It must remain
local-first, work without MLX/model loading, preserve private-data boundaries,
and add no unapproved heavy workload.

## Goals / Non-Goals

**Goals:**

- Make the current phase and last durable transition of a factory run explicit.
- Reject invalid and concurrent stale updates instead of silently regressing
  state.
- Make active/latest run discovery fast while keeping per-run metadata
  authoritative and repairable.
- Allow interrupted or stale state to be diagnosed without parsing private
  logs or loading a checkpoint.
- Preserve completed legacy runs and terminal decision semantics.

**Non-Goals:**

- Automatically resuming training or choosing a recovery recipe.
- A distributed scheduler, queue, daemon, or hosted control plane.
- Storing prompts, completions, dataset rows, checkpoints, or log contents in
  lifecycle metadata.
- Automatically publishing artifacts or changing manual release authority.
- Treating lifecycle completion as evidence that quality gates passed.

## Decisions

### Add one authoritative `run-status.json` snapshot per run

Each lifecycle-managed run stores a versioned snapshot containing:

- `schema_version`
- `run_id`
- `revision`
- `phase`
- `updated_at`
- last transition command/source and optional reason
- optional parent/successor relationship
- optional sanitized failure code and summary
- an `imported` marker when status was derived from pre-existing evidence

The initial phase vocabulary is:

```text
created
data-ready
training
trained
evaluating
evaluated
packaging
packaged
reporting
decided
failed
```

The normal path follows the factory loop. Explicit alternate edges allow
evaluation-only, report-only, and imported runs to omit inapplicable training
or packaging stages, but every skipped edge requires a machine-readable reason.
Any non-terminal phase can transition to `failed`. `decided` and `failed` are
terminal; a retry creates a new run linked to the prior run instead of mutating
historical evidence.

`decision.json` remains the quality/product outcome. `run-status.json` only
answers operational lifecycle questions.

Alternative considered: infer status from whichever fragments currently exist.
Rejected because file presence cannot distinguish an active writer, stale
partial run, deliberate report-only flow, and corruption.

### Use locked compare-and-swap transitions plus atomic replacement

A transition acquires a short-lived per-run metadata lock, reads the current
snapshot, checks an expected revision, validates the transition, writes a
same-filesystem temporary file, and atomically replaces the destination.
Revision increments exactly once after a successful transition. Temporary
files are ignored during reads and cleaned during reconciliation.

Alternative considered: rely only on Foundation's atomic write. Rejected
because atomic replacement prevents torn content but does not prevent two
stale writers from overwriting each other.

### Keep discovery pointers advisory and rebuildable

The run root can contain atomic `current-run.json` and `latest-run.json`
pointers with only a relative run path, run id, lifecycle revision, phase, and
update time. A pointer is never accepted without reading and matching the
target's `run-status.json`. `factory-run list` scans status files; `reconcile`
can rebuild missing or stale pointers deterministically.

`current-run.json` identifies the operator-selected or most recently updated
non-terminal run, not a claim that no other run exists. `latest-run.json`
identifies the most recently updated terminal run.

Alternative considered: maintain a mandatory central registry. Rejected
because a single index would become another source of truth and a larger
corruption/concurrency boundary.

### Put the contract in the pure IO target

Lifecycle types, validation, persistence, and reconciliation live beside
`FactoryRun` in `TinyGPTIO`. The CLI and Mac app use the same implementation.
The Python assembly bridge either invokes the native metadata command or follows
fixture-tested schema parity; it does not invent a third lifecycle vocabulary.

Alternative considered: implement status only in the Python assembler.
Rejected because live native commands and the Mac app would drift from it.

### Expose explicit metadata-only CLI operations

The `factory-run` command gains operations equivalent to:

```text
init
status
transition
list
reconcile
```

Mutating commands support JSON output, expected revision, and dry-run where
appropriate. They do not load MLX, start a server, train, evaluate, package,
publish, or access the network.

Lifecycle hooks update state only after the corresponding durable artifact
write succeeds. Errors after a run exists can record a sanitized `failed`
transition, but lifecycle code never treats a successful command exit alone as
quality evidence.

### Migrate without fabricating history

Existing `factory-run validate` and publication behavior remain compatible
during the migration. An explicit import/reconcile path may create a
`run-status.json` for a legacy folder only at the furthest phase proven by its
validated files. A completed folder with a valid `decision.json` can be marked
`decided` and `imported=true`; it does not receive invented timestamps for
earlier phases.

After representative legacy fixtures and live metadata-only flows pass, new
run creation can require lifecycle metadata. Tightening publication checks for
new-schema runs is a later task within this change, not an immediate breaking
change for historical evidence.

## Risks / Trade-offs

- [Lifecycle becomes a second decision system] → Keep phase separate from
  `decision.json`; `decided` requires a valid decision but does not duplicate it.
- [Writers crash while holding the metadata lock] → Reconciliation diagnoses
  stale locks using recorded PID/time without killing processes automatically.
- [Pointers drift after a crash] → Treat them as advisory, validate targets on
  every read, and rebuild them by scanning authoritative status files.
- [Legacy imports overstate history] → Mark imports and record only the
  furthest phase proven by current files.
- [Failure summaries leak private data] → Allow bounded codes and sanitized
  summaries only; never copy command output, prompts, rows, or logs.
- [Too many states create operator burden] → CLI integrations perform normal
  transitions; manual transitions are an escape hatch with validation and
  reasons, not the default workflow.
- [Status says complete while evidence is weak] → Publish and eval checks remain
  independent and authoritative for quality.

## Migration Plan

1. Add typed lifecycle fixtures, legal-transition tests, and pure IO helpers.
2. Add metadata-only CLI operations and atomic advisory pointers.
3. Integrate factory rendering/assembly and fixture-backed failure paths.
4. Import representative complete, report-only, failed, and partial legacy
   folders without changing their canonical evidence.
5. Add read-only Mac app and Foundry consumption after privacy tests pass.
6. Require lifecycle metadata only for newly created schema-versioned runs once
   compatibility fixtures are green.

Rollback stops emitting lifecycle files and removes advisory pointers. Existing
canonical run fragments, decisions, specialist packages, and reports remain
valid and unchanged.

## Resolved Questions

- `current-run.json` automatically follows the most recently updated valid
  non-terminal run. It remains advisory and does not imply exclusivity.
- Stale non-terminal runs remain active-with-warning until an explicit operator
  transition. Reconciliation never marks a run failed.
- Lifecycle metadata is required only for runs newly created by lifecycle
  schema v1 writers. Legacy folders remain readable and publish-compatible
  without status until explicitly imported.
