## 1. Lifecycle Contract

- [ ] 1.1 Add versioned lifecycle, phase, transition, failure, and discovery-pointer types to `TinyGPTIO`
- [ ] 1.2 Encode the normal and alternate transition graph, including required skip reasons and terminal-state rejection
- [ ] 1.3 Validate lifecycle run identity against `config.json` and require canonical decision evidence before `decided`
- [ ] 1.4 Add bounded failure sanitization that rejects private payload fields and oversized summaries
- [ ] 1.5 Add JSON fixtures for normal, report-only, evaluation-only, imported, failed, malformed, and terminal runs

## 2. Atomic Persistence And Reconciliation

- [ ] 2.1 Implement a short-lived per-run lifecycle lock with explicit stale-lock diagnostics
- [ ] 2.2 Implement expected-revision compare-and-swap transitions using same-filesystem atomic replacement
- [ ] 2.3 Implement validated atomic `current-run.json` and `latest-run.json` pointer writers and readers
- [ ] 2.4 Implement run-root scanning that lists all valid lifecycle-managed runs without trusting pointers
- [ ] 2.5 Implement dry-run and write-mode reconciliation for stale pointers, abandoned temporary files, and stale locks
- [ ] 2.6 Add race, stale-writer, interrupted-write, path-escape, pointer-drift, and idempotent-reconciliation tests

## 3. Metadata-Only CLI

- [ ] 3.1 Add `factory-run init` and `factory-run status` with human-readable and JSON output
- [ ] 3.2 Add `factory-run transition` with expected revision, transition reason, parent/successor metadata, and actionable errors
- [ ] 3.3 Add `factory-run list` filters for active, terminal, failed, imported, and stale runs
- [ ] 3.4 Add `factory-run reconcile` with default dry-run behavior and an explicit write flag
- [ ] 3.5 Prove lifecycle CLI operations do not initialize MLX, load checkpoints, access the network, or perform model work

## 4. Factory Integration And Migration

- [ ] 4.1 Extend `FactoryRunFolder` with optional lifecycle read/write/validation while preserving legacy folder behavior
- [ ] 4.2 Update native factory render and Python assembly paths to advance state only after durable fragment validation
- [ ] 4.3 Record sanitized failure transitions for integrated metadata workflows without copying logs or model output
- [ ] 4.4 Implement explicit legacy import that records only the furthest phase proven by validated files and marks it imported
- [ ] 4.5 Add read-only Mac app run discovery from the shared IO contract without introducing a background scheduler
- [ ] 4.6 Add privacy-safe lifecycle fields to Foundry receipts without granting publication or deployment authority
- [ ] 4.7 Stage enforcement so lifecycle metadata is required only for newly created schema-versioned runs after compatibility gates pass

## 5. Verification And Documentation

- [ ] 5.1 Add Swift unit tests for every required transition, alternate edge, terminal rejection, decision boundary, and privacy rule
- [ ] 5.2 Add no-GPU smoke coverage for init, transition, list, reconcile, assembly success, assembly failure, and JSON output
- [ ] 5.3 Add legacy complete, report-only, partial, and invalid run fixtures proving migration does not fabricate history
- [ ] 5.4 Update factory run schema, enforcement, overview, Foundry evidence, and operator documentation with lifecycle and recovery rules
- [ ] 5.5 Run the smallest relevant Swift tests, lifecycle smokes, docs checks, OpenSpec validation, and `git diff --check`
- [ ] 5.6 After implementation ships, archive this change and update `PROJECT_STATUS.md` with the delivered lifecycle capability and remaining limitations
