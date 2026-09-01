# Exactness Completion Audit

This audit answers one question: are the posttrainllm docs now exact enough to be
trusted as the operating system for the project?

## Completion Standard

The docs pass is complete when the repository has:

1. A current docs golden path.
2. A structured attempt ledger with evidence, final status, confidence,
   lesson, and next action, with no unresolved `not-tried` state.
3. A human-readable ledger synced to the structured ledger.
4. A coverage audit that distinguishes attempts, technique inventory,
   narrative history, and learning notes.
5. A structured treatment of the broad `audit_2026.md` technique audit.
6. Factory run/report schemas that require exactness fields before publishing.
7. A learning path and progress tracker tied to the active factory loop.
8. Smoke checks that fail when the above surfaces drift.
9. A completion validator that rejects unresolved attempts, uncovered
   techniques, dangling learning paths, or missing public surfaces.

## Evidence

| Requirement | Evidence | Status |
|---|---|---|
| Docs golden path | `docs/README.md`, `scripts/docs-checks/check_docs_world_class.py` | complete |
| Structured attempt ledger | `docs/attempts.json` schema v3, `scripts/docs-checks/check_attempt_ledger.py` | complete |
| Human-readable attempt ledger | `docs/attempt-ledger.md` synced by `evals/attempt-ledger-smoke.sh` | complete |
| Historical coverage boundary | `docs/audits/history-coverage-audit.md` | complete |
| Technique audit treatment | `docs/techniques/audit-inventory.md`, `scripts/docs-checks/check_technique_inventory.py` | complete |
| Factory exactness fields | `docs/factory/run-schema.md`, `docs/factory/reports.md`, `docs/factory/case-study-template.md`, `scripts/factory/check_factory_run_publish.py`, native `factory-run publish-check` | complete |
| Learning path | `docs/learn/curriculum.md`, `docs/learning-pipeline.md`, `docs/learning-progress.md`, `scripts/docs-checks/check_learning_roadmap.py` | complete |
| Rendered public docs | `browser` Astro build renders docs including the new audit pages | complete |
| Closed learning-lab contract | `docs/recipes/registry.json`, `docs/learn/path-registry.json`, `scripts/docs-checks/check_project_completion.py` | complete |

## Current Counts

Structured attempt ledger:

| Metric | Count |
|---|---:|
| Total attempts | 75 |
| Exact confidence | 64 |
| Inferred confidence | 5 |
| Not-applicable confidence | 4 |
| Missing-evidence confidence | 2 |

Technique audit inventory:

| Bucket | Count |
|---|---:|
| Keep/default | 45 |
| Experimental | 8 |
| Flagged | 30 |
| Delete | 0 |
| Tracked audit rows | 83 |

## Closed Boundary

There is no implicit documentation-hardening backlog after this pass. Future
automation, provenance fields, or learning checkpoints begin only when the
owner opens a fresh experiment after the learning phase. Historical absences
remain explicit limitations rather than AI follow-up work.

## Verification

The current proof set is:

```bash
bash evals/attempt-ledger-smoke.sh
bash evals/technique-inventory-smoke.sh
bash evals/docs-world-class-smoke.sh
bash evals/factory-publish-check-smoke.sh
bash evals/learning-roadmap-smoke.sh
bash evals/project-completion-smoke.sh
python3 -m py_compile scripts/docs-checks/check_attempt_ledger.py scripts/docs-checks/check_docs_world_class.py scripts/factory/check_factory_run_publish.py scripts/docs-checks/check_learning_roadmap.py scripts/docs-checks/check_technique_inventory.py scripts/sql/render_sql_factory_run.py
git diff --check
cd browser && npm run build
```

## Verdict

The docs are now exact enough to operate from:

- attempts are structured and confidence-labeled;
- broad technique rows are classified instead of misreported as attempts;
- old narrative surfaces have explicit treatment rules;
- factory reports must carry exactness fields;
- the learning path is tied to the same factory loop;
- smoke checks guard the core docs surfaces.

Any future automation or provenance work begins under a fresh owner-selected
experiment; it is not unfinished work in this closed project.
