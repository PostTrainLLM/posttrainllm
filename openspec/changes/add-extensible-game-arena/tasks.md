## 1. Freeze the arena contract

- [x] 1.1 Add the arena config, schema constants, competition-family rules, and trial source manifest.
- [x] 1.2 Freeze rating priors, bootstrap seed/count, qualification minimums, and forfeit policy before scoring.
- [x] 1.3 Strictly validate this OpenSpec change.

## 2. Implement scoring and validation

- [x] 2.1 Implement standard-library head-to-head Arena Elo fitting with deterministic uncertainty.
- [x] 2.2 Implement standard-library paired-score summaries and bootstrap uncertainty.
- [x] 2.3 Fail closed on malformed, duplicate, disconnected, or semantically incompatible evidence.
- [x] 2.4 Keep qualification state independent from the numerical estimate.

## 3. Add initial adapters

- [x] 3.1 Normalize the existing paired-color chess match artifact.
- [x] 3.2 Normalize completed Character 2048 model-versus-random trials.
- [x] 3.3 Preserve source paths, trace hashes, incomplete attempts, forfeits, and failed-gate decisions.
- [x] 3.4 Generate and validate the first candidate arena report without model calls.

## 4. Build the arena surface

- [x] 4.1 Add an Arena route in the existing benchmark visual language.
- [x] 4.2 Render family-correct ratings, intervals, sample sizes, qualification, and limitations.
- [x] 4.3 Add game switching, evidence drill-through, responsive states, and accessible controls.
- [x] 4.4 Update the benchmark catalog and product truth without claiming FIDE Elo or a specialist win.

## 5. Verify and report

- [x] 5.1 Add focused unit tests and a no-model smoke command.
- [x] 5.2 Run strict OpenSpec validation, JSON validation, typecheck, and build.
- [x] 5.3 Inspect the UI at 390, 768, and 1440 pixels and complete the design receipt.
- [x] 5.4 Update `PROJECT_STATUS.md` with what the trial proves and what remains unqualified.
