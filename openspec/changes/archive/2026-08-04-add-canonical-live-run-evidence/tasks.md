## 1. Contract and pure persistence

- [x] 1.1 Add a model-free factory evidence helper for preflight, typed atomic
  writes, phase enforcement, and lifecycle advancement
- [x] 1.2 Add pure tests for valid writes, invalid phases/identity, incomplete
  evidence, repeated calls, and no invented outcome state

## 2. Live command integration

- [x] 2.1 Add opt-in `sft --factory-run` preflight and successful training
  evidence emission without changing existing invocations
- [x] 2.2 Add opt-in `eval-gate --factory-run` primary-suite baseline/candidate
  emission and evaluated transition
- [x] 2.3 Add opt-in `eval-compare --factory-run` deterministic slice-metrics
  emission without lifecycle advancement

## 3. Verification and durable truth

- [x] 3.1 Add a no-model command-boundary smoke covering the complete
  data-ready -> training -> trained -> evaluating -> evaluated path
- [x] 3.2 Run focused Swift/pure smokes, strict OpenSpec validation, formatting,
  and `git diff --check`; defer GPU verification pending owner approval
- [x] 3.3 Update factory docs and `PROJECT_STATUS.md`, archive the completed
  OpenSpec change, and link the implementation PR to issue #69 without closing
  unrelated target-specific or QLoRA follow-up
