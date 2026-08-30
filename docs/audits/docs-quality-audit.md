# Docs Quality Audit

This page tracks whether posttrainllm documentation is actually world-class, not just
large.

## Definition

Docs are world-class when an outsider can answer:

1. What is the project?
2. What is active vs parked?
3. What did we try?
4. What worked, failed, or regressed?
5. What products/papers/blogs changed the plan?
6. What is on the roadmap?
7. What should the owner learn next?
8. How is a public claim validated?
9. How can the next run reproduce or improve the result?

## Current State

| Requirement | Current Source | Status |
|---|---|---|
| Project state | `PROJECT_STATUS.md` | strong |
| Active roadmap | `docs/NEXT.md` | strong |
| Golden path | `docs/README.md` | strong |
| Factory pipeline | `docs/factory/` | strong |
| Method vs recipe | `docs/techniques/method-vs-recipe.md` | strong |
| Technique audit inventory | `docs/techniques/audit-inventory.md` | strong |
| Attempt history | `docs/attempt-ledger.md`, `docs/attempts.json`, `docs/audits/history-coverage-audit.md`, `scripts/docs-checks/check_attempt_ledger.py` | strong |
| Exactness completion audit | `docs/audits/exactness-completion-audit.md` | complete |
| External products reviewed | `docs/external-products-reviewed.md` | good, should grow with every teardown |
| Learning pipeline | `docs/learning-pipeline.md` | strong, tied to current factory work |
| Learning progress | `docs/learning-progress.md` | good, manually maintained |
| Public artifacts | `docs/factory/public-artifacts.md` | strong |
| Enforcement | `docs/factory/enforcement.md`, `posttrainllm factory-run publish-check`, `scripts/factory/check_factory_run_publish.py` | strong |
| Docs completeness check | `scripts/docs-checks/check_docs_world_class.py` | good, checks golden-path surfaces exist |
| Old docs status | `docs/README.md`, `docs/MAP.md`, `docs/parked/` | acceptable, still noisy |

## What Improved In This Pass

- Added a canonical docs entrypoint.
- Added an attempt ledger with worked, failed, regressed, and not-tried
  attempts plus confidence labels, evidence sources, and a structured sync
  check.
- Added a history coverage audit so normalized, classified, partial, and
  narrative-only historical surfaces are separated honestly.
- Added an external products/research review ledger.
- Added a learning pipeline tied to the factory loop.
- Added a method-vs-recipe registry and SQL technique backlog.
- Added a row-level technique inventory for `docs/audits/audit_2026.md`, so broad
  technique rows are classified without being misrepresented as run attempts.
- Added an exactness completion audit that records the proof set and
  non-blocking future hardening.
- Added factory enforcement docs.
- Added a stricter publish-check script.
- Added a docs golden-path completeness check.
- Updated the SQL factory renderer to emit `slice-metrics.json` and
  `trace_review.md`.
- Wired the new docs into `PROJECT_STATUS.md`, `docs/NEXT.md`,
  `docs/MAP.md`, `docs/factory/README.md`, `docs/learn/README.md`, and
  `docs/techniques/README.md`.

## Completion Audit

The current docs meet the world-class baseline defined above:

| Question | Evidence |
|---|---|
| What is the project? | `PROJECT_STATUS.md`, `docs/README.md` |
| What is active vs parked? | `docs/doc-status.md`, `docs/NEXT.md`, `docs/parked/` |
| What did we try? | `docs/attempt-ledger.md`, `docs/attempts.json`, `docs/audits/history-coverage-audit.md`, `docs/audits/exactness-completion-audit.md` |
| What worked, failed, or regressed? | `docs/attempt-ledger.md`, `docs/techniques/sql-technique-backlog.md`, `docs/techniques/audit-inventory.md`, `docs/audits/history-coverage-audit.md` |
| What products/papers/blogs changed the plan? | `docs/external-products-reviewed.md`, `docs/techniques/trainloop-teardown.md` |
| What is on the roadmap? | `docs/NEXT.md`, `docs/techniques/sql-technique-backlog.md`, `docs/factory/public-artifacts.md` |
| What should the owner learn next? | `docs/learning-pipeline.md`, `docs/learning-progress.md` |
| How is a public claim validated? | `docs/factory/enforcement.md`, `posttrainllm factory-run publish-check`, `scripts/factory/check_factory_run_publish.py` |
| How can the next run reproduce or improve the result? | `docs/factory/run-schema.md`, `provenance.json`, `docs/techniques/` |

Verification commands:

```bash
bash evals/docs-world-class-smoke.sh
bash evals/attempt-ledger-smoke.sh
bash evals/technique-inventory-smoke.sh
bash evals/factory-publish-check-smoke.sh
npm run build # from browser/
```

## Future Hardening

These are not blockers to the world-class baseline, but they should continue to
improve:

1. **Attempt ledger still has manual source metadata.**
   It now has `docs/attempts.json` and a checker, but future run commands should
   append attempts automatically.

2. **Publish validation has two implementations.**
   `posttrainllm factory-run publish-check` is the canonical command, while
   `scripts/factory/check_factory_run_publish.py` remains as a portable smoke. This is
   acceptable, but should eventually share one implementation.

3. **Old docs are still noisy, but bounded.**
   `docs/PLAN.md`, older PRDs, and session notes remain useful but can distract
   readers. `docs/audits/history-coverage-audit.md` now names which older surfaces are
   normalized, classified, or narrative-only.

4. **External teardown corpus is shallow.**
   TrainLoop, Baseten, SQL specialists, Apple, Castform, and agent-system notes
   are captured, but every new target should get a fresh competitor/literature
   teardown.

5. **Learning progress is manual.**
   The owner learning sequence now has a progress tracker, but it is not derived
   from run artifacts.

6. **Current SQL report is still report-ready, not ship-ready.**
   Public execution benchmark and routed performance numbers remain blockers.

## Next Quality Gates

To keep improving the docs after the baseline:

1. Add structured run metadata fields for git commit, binary provenance,
   dataset hash, and exact commands.
2. Add visible `active/reference/archive/stale/superseded` banners to remaining
   old docs beyond the major entrypoints.
3. Make `docs/learning-progress.md` update from run metadata or checklist
   commands.
