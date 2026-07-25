## 1. Lifecycle Contract

- [x] 1.1 Add versioned lifecycle, phase, transition, failure, and discovery-pointer types to `TinyGPTIO`
- [x] 1.2 Encode the normal and alternate transition graph, including required skip reasons and terminal-state rejection
- [x] 1.3 Validate lifecycle run identity against `config.json` and require canonical decision evidence before `decided`
- [x] 1.4 Add bounded failure sanitization that rejects private payload fields and oversized summaries
- [x] 1.5 Add JSON fixtures for normal, report-only, evaluation-only, imported, failed, malformed, and terminal runs

## 2. Atomic Persistence And Reconciliation

- [x] 2.1 Implement a short-lived per-run lifecycle lock with explicit stale-lock diagnostics
- [x] 2.2 Implement expected-revision compare-and-swap transitions using same-filesystem atomic replacement
- [x] 2.3 Implement validated atomic `current-run.json` and `latest-run.json` pointer writers and readers
- [x] 2.4 Implement run-root scanning that lists all valid lifecycle-managed runs without trusting pointers
- [x] 2.5 Implement dry-run and write-mode reconciliation for stale pointers, abandoned temporary files, and stale locks
- [x] 2.6 Add race, stale-writer, interrupted-write, path-escape, pointer-drift, and idempotent-reconciliation tests

## 3. Metadata-Only CLI

- [x] 3.1 Add `factory-run init` and `factory-run status` with human-readable and JSON output
- [x] 3.2 Add `factory-run transition` with expected revision, transition reason, parent/successor metadata, and actionable errors
- [x] 3.3 Add `factory-run list` filters for active, terminal, failed, imported, and stale runs
- [x] 3.4 Add `factory-run reconcile` with default dry-run behavior and an explicit write flag
- [x] 3.5 Prove lifecycle CLI operations do not initialize MLX, load checkpoints, access the network, or perform model work

## 4. Factory Integration And Migration

- [x] 4.1 Extend `FactoryRunFolder` with optional lifecycle read/write/validation while preserving legacy folder behavior
- [x] 4.2 Update native factory render and Python assembly paths to advance state only after durable fragment validation
- [x] 4.3 Record sanitized failure transitions for integrated metadata workflows without copying logs or model output
- [x] 4.4 Implement explicit legacy import that records only the furthest phase proven by validated files and marks it imported
- [x] 4.5 Add read-only Mac app run discovery from the shared IO contract without introducing a background scheduler
- [x] 4.6 Add privacy-safe lifecycle fields to Foundry receipts without granting publication or deployment authority
- [x] 4.7 Stage enforcement so lifecycle metadata is required only for newly created schema-versioned runs after compatibility gates pass

## 5. Verification And Documentation

- [x] 5.1 Add Swift unit tests for every required transition, alternate edge, terminal rejection, decision boundary, and privacy rule
- [x] 5.2 Add no-GPU smoke coverage for init, transition, list, reconcile, assembly success, assembly failure, and JSON output
- [x] 5.3 Add legacy complete, report-only, partial, and invalid run fixtures proving migration does not fabricate history
- [x] 5.4 Update factory run schema, enforcement, overview, Foundry evidence, and operator documentation with lifecycle and recovery rules
- [x] 5.5 Run the smallest relevant Swift tests, lifecycle smokes, docs checks, OpenSpec validation, and `git diff --check`
- [x] 5.6 After implementation ships, archive this change and update `PROJECT_STATUS.md` with the delivered lifecycle capability and remaining limitations
  - Shipped to `main` on 2026-07-25; `PROJECT_STATUS.md` records the capability and remaining limitations.
