## 1. Report-Card Contract

- [x] 1.1 Define a versioned report-card schema with per-field provenance and measured/derived/historical/skipped/missing/not-applicable states
- [x] 1.2 Map primary, regression, slice, performance, leakage, frontier-ceiling, artifact, and decision fields from canonical factory-run types
- [x] 1.3 Add schema fixtures for ship, routed ship, report-only, retry, reject, missing-evidence, and historical cases

## 2. Offline Compiler

- [x] 2.1 Implement factory-run ingestion that performs no model load, training, generation, eval, registry, or network work
- [x] 2.2 Implement per-field source mapping, hashes, compiler provenance, and deterministic ordering
- [x] 2.3 Implement delta, threshold, gate, and decision consistency derivation without inventing missing values
- [x] 2.4 Add a CLI build command that emits versioned JSON and deterministic static report output

## 3. Publication Validation

- [x] 3.1 Extend publish validation with report-card schema, provenance, measurement-state, and decision checks
- [x] 3.2 Add frontier-ceiling, frozen-eval, overlap/leakage, known-limitation, and routed-use disclosure checks
- [x] 3.3 Make invalid publication exit non-zero while preserving local diagnostic output
- [x] 3.4 Verify report-only artifacts can publish without being labeled shipped and incomplete ship claims fail closed

## 4. Public Rendering

- [x] 4.1 Render decision, before/after gates, regressions, slices, performance, failures, caveats, evidence links, and one next action from the canonical payload
- [x] 4.2 Add static report links and outcome labels to the existing `/artifacts` inventory without changing weight-release policy
- [x] 4.3 Add snapshot and accessibility tests proving public output matches the JSON contract and remains readable without repo access

## 5. Dogfood Without GPU Work

- [x] 5.1 Compile report cards from existing file-ops, ReST, SQL retry/report-only, rejected, and historical artifacts without rerunning models
- [x] 5.2 Review each report against its source artifacts and record mapping gaps, misleading labels, and missing evidence
- [x] 5.3 Refine the schema/validators and repeat fixture compilation until every supported outcome is honest and stable
- [x] 5.4 Mark the format canonical only after the reviewed cohort passes, then update `PROJECT_STATUS.md`, factory docs, and public-artifact guidance

## Implementation Notes

Two tasks landed with a scope carve-out. Both are recorded in
`docs/factory/report-card-cohort.md` and `PROJECT_STATUS.md` rather than being
quietly closed.

**2.4 — CLI surface.** The runnable CLI is Python
(`scripts/build_fine_tune_report_card.py`,
`scripts/check_fine_tune_report_card.py`), mirroring the existing
`check_factory_run_publish.py` ↔ Swift publish-check pair. The canonical schema
boundary is `native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift`, decoded
against real compiler output by `evals/fine-tune-report-card-smoke.sh` via bare
`swiftc` over the pure IO target. A `posttrainllm factory-run report-card`
subcommand is deferred: the `TinyGPT` target pulls MLX, so that code is only
verifiable behind a full package build.

**5.1 — cohort coverage.** Three real cards are published (file-ops distilled and
ReST fused as `routed-ship`; the SQL routed POC as `report-only`). The SQL
retry runs live only under gitignored `runs/` and the rejected
`qwen3-4b-multibackend-distilled` has no committed `eval_report.json`, so both
are documented absences with fixture coverage, which the spec's dogfood
requirement permits. No published card claims a verified ship — the ship-path
evidence (frontier ceiling, leakage check) does not exist for any real candidate
yet, and each card lists that as a blocker.
