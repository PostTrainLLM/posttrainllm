## 1. Report-Card Contract

- [ ] 1.1 Define a versioned report-card schema with per-field provenance and measured/derived/historical/skipped/missing/not-applicable states
- [ ] 1.2 Map primary, regression, slice, performance, leakage, frontier-ceiling, artifact, and decision fields from canonical factory-run types
- [ ] 1.3 Add schema fixtures for ship, routed ship, report-only, retry, reject, missing-evidence, and historical cases

## 2. Offline Compiler

- [ ] 2.1 Implement factory-run ingestion that performs no model load, training, generation, eval, registry, or network work
- [ ] 2.2 Implement per-field source mapping, hashes, compiler provenance, and deterministic ordering
- [ ] 2.3 Implement delta, threshold, gate, and decision consistency derivation without inventing missing values
- [ ] 2.4 Add a CLI build command that emits versioned JSON and deterministic static report output

## 3. Publication Validation

- [ ] 3.1 Extend publish validation with report-card schema, provenance, measurement-state, and decision checks
- [ ] 3.2 Add frontier-ceiling, frozen-eval, overlap/leakage, known-limitation, and routed-use disclosure checks
- [ ] 3.3 Make invalid publication exit non-zero while preserving local diagnostic output
- [ ] 3.4 Verify report-only artifacts can publish without being labeled shipped and incomplete ship claims fail closed

## 4. Public Rendering

- [ ] 4.1 Render decision, before/after gates, regressions, slices, performance, failures, caveats, evidence links, and one next action from the canonical payload
- [ ] 4.2 Add static report links and outcome labels to the existing `/artifacts` inventory without changing weight-release policy
- [ ] 4.3 Add snapshot and accessibility tests proving public output matches the JSON contract and remains readable without repo access

## 5. Dogfood Without GPU Work

- [ ] 5.1 Compile report cards from existing file-ops, ReST, SQL retry/report-only, rejected, and historical artifacts without rerunning models
- [ ] 5.2 Review each report against its source artifacts and record mapping gaps, misleading labels, and missing evidence
- [ ] 5.3 Refine the schema/validators and repeat fixture compilation until every supported outcome is honest and stable
- [ ] 5.4 Mark the format canonical only after the reviewed cohort passes, then update `PROJECT_STATUS.md`, factory docs, and public-artifact guidance
