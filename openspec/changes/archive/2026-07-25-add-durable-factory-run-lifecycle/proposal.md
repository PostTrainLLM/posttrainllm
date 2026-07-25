## Why

posttrainllm has a strong schema for completed factory evidence, atomic checkpoint
writes, run locks, and terminal ship/retry/reject decisions, but it does not have
one durable contract for the state of an in-progress factory run. The CLI, Mac
app, scripts, and future Foundry automation therefore cannot reliably answer
which run is active, which phase completed, whether a writer is stale, or how to
recover after interruption without inferring state from partial files.

## What Changes

- Add a versioned factory-run lifecycle record with explicit phases, monotonic
  revision, timestamps, transition provenance, and a sanitized failure state.
- Define legal transitions and fail closed on stale, invalid, regressive, or
  post-terminal updates.
- Write lifecycle changes and active/latest-run pointers atomically, while
  treating pointers as repairable indexes rather than sources of truth.
- Add metadata-only CLI operations to create, inspect, transition, list, and
  reconcile factory runs without loading a model or using the GPU.
- Integrate lifecycle updates with existing factory-run assembly and the native
  train/eval/package/report boundaries without replacing canonical run
  artifacts or `decision.json`.
- Preserve validation and publication compatibility for existing run folders
  that predate lifecycle metadata; migration is explicit and never fabricates
  unobserved phase history.
- Keep automatic training resume, automatic publication, remote orchestration,
  and multi-host scheduling out of scope.

## Capabilities

### New Capabilities

- `factory-run-lifecycle`: Durable lifecycle schema, legal transition behavior,
  atomic discovery pointers, recovery/reconciliation, CLI operations, and
  backward compatibility for factory runs.

### Modified Capabilities

- None.

## Impact

- Native IO: typed lifecycle and atomic transition helpers beside
  `FactoryRun`/`FactoryRunFolder`.
- CLI: metadata-only `factory-run` lifecycle and discovery subcommands.
- Factory scripts: lifecycle hooks around assembly and explicit failure
  recording where a run directory already exists.
- Mac app / Foundry: consume sanitized lifecycle metadata for run discovery;
  neither surface gains publication authority.
- Tests/docs: transition-matrix, stale-writer, interruption, reconciliation,
  legacy-run, and privacy fixtures plus updates to the factory run contract.
- Dependencies/deploy: no new production dependency, migration, deployment,
  model execution, training run, or release.
