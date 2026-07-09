# Exactness Completion Audit

This audit answers one question: are the posttrainllm docs now exact enough to be
trusted as the operating system for the project?

## Completion Standard

The docs pass is complete when the repository has:

1. A current docs golden path.
2. A structured attempt ledger with evidence, status, confidence, lesson, and
   next action.
3. A human-readable ledger synced to the structured ledger.
4. A coverage audit that distinguishes attempts, technique inventory,
   narrative history, and learning notes.
5. A structured treatment of the broad `audit_2026.md` technique audit.
6. Factory run/report schemas that require exactness fields before publishing.
7. A learning path and progress tracker tied to the active factory loop.
8. Smoke checks that fail when the above surfaces drift.

## Evidence

| Requirement | Evidence | Status |
|---|---|---|
| Docs golden path | `docs/README.md`, `scripts/check_docs_world_class.py` | complete |
| Structured attempt ledger | `docs/attempts.json` schema v2, `scripts/check_attempt_ledger.py` | complete |
| Human-readable attempt ledger | `docs/attempt-ledger.md` synced by `evals/attempt-ledger-smoke.sh` | complete |
| Historical coverage boundary | `docs/history-coverage-audit.md` | complete |
| Technique audit treatment | `docs/techniques/audit-inventory.md`, `scripts/check_technique_inventory.py` | complete |
| Factory exactness fields | `docs/factory/run-schema.md`, `docs/factory/reports.md`, `docs/factory/case-study-template.md`, `scripts/check_factory_run_publish.py`, native `factory-run publish-check` | complete |
| Learning path | `docs/learn/curriculum.md`, `docs/learning-pipeline.md`, `docs/learning-progress.md`, `scripts/check_learning_roadmap.py` | complete |
| Rendered public docs | `browser` Astro build renders docs including the new audit pages | complete |

## Current Counts

Structured attempt ledger:

| Metric | Count |
|---|---:|
| Total attempts | 53 |
| Exact confidence | 39 |
| Inferred confidence | 5 |
| Not-applicable confidence | 9 |
| Missing-evidence confidence | 0 |

Technique audit inventory:

| Bucket | Count |
|---|---:|
| Keep/default | 45 |
| Experimental | 8 |
| Flagged | 30 |
| Delete | 0 |
| Tracked audit rows | 83 |

## Non-Blocking Future Hardening

These are useful improvements, but they are not evidence that the docs pass is
incomplete:

1. Generate `docs/attempts.json` entries automatically from future factory run
   folders.
2. Share implementation between the Python factory publish checker and the
   native Swift publish checker.
3. Add visible status banners to every old archive/reference page.
4. Derive `docs/learning-progress.md` from checklist/run metadata instead of
   manual edits.
5. Add git commit, binary provenance, dataset hash, exact commands, cost, RAM,
   latency, tok/s, report URL, and artifact URL to future run records.

## Verification

The current proof set is:

```bash
bash evals/attempt-ledger-smoke.sh
bash evals/technique-inventory-smoke.sh
bash evals/docs-world-class-smoke.sh
bash evals/factory-publish-check-smoke.sh
bash evals/learning-roadmap-smoke.sh
python3 -m py_compile scripts/check_attempt_ledger.py scripts/check_docs_world_class.py scripts/check_factory_run_publish.py scripts/check_learning_roadmap.py scripts/check_technique_inventory.py scripts/render_sql_factory_run.py
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

Future work should improve automation and provenance depth, not reopen the
basic docs exactness question.
