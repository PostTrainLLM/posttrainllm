# Everyday Specialist Benchmark

This directory contains the no-model foundation for the benchmark proposed in
OpenSpec change `add-everyday-specialist-benchmark` and GitHub issue #77.

Current status: **Pace intent routing is frontier-qualified on sealed V1**.
Two more qualified task families and the general cohort renderer are still
required before the benchmark suite itself is ready to launch.

## What exists

- `configs/everyday-benchmark/contracts-v1.json` is the versioned contract
  catalog for suites, tasks, entries, instance sets, imported predictions,
  runs, results, resource measurements, system traces, and receipts.
- `configs/everyday-benchmark/suite-v1.json` and `tasks/` freeze the first suite
  and deterministic Pace intent-routing task contract.
- `fixtures/pace-intent-public-dev-v1.json` contains 28 reviewed synthetic
  development cases across Pace's existing seven labels. Devin GLM-5.2
  generated a balanced candidate pool; the committed cases were selected
  against `specialists/pace-intent-router-v8/prompt.md`. They are public and
  must never be presented as held-out or sealed.
- `fixtures/entries/` exercises the required `generalist`, `adapted`, and
  `system` disclosure tracks.
- `scripts/check_everyday_benchmark.py` validates artifacts fail-closed,
  including cross-artifact identity, resource math, and receipt privacy.
- `scripts/run_everyday_benchmark.py` scores caller-supplied predictions and
  emits validated `run.json`, `result.json`, and aggregate-only `receipt.json`.
- `scripts/calibrate_selective_cascade.py` fits only a predeclared signal grid
  on public-development predictions, refuses sealed calibration, and composes a
  system prediction artifact only when all configured quality, coverage,
  escalation, and final-accuracy targets pass.
- `configs/everyday-benchmark/policies/pace-intent-selective-v1.json` freezes the
  development 90/10 target and an ordered specialist -> local generalist ->
  disabled external-frontier path compatible with the future capability graph.
- `pace-intent-sealed-v1.md` is the privacy-safe first official comparison.
  Its four receipts disclose instance identity, frontier qualification,
  leakage/custody evidence, aggregate scores, and result hashes without raw
  sealed prompts or outputs.

The no-model runner understands all four adapter identities—local package,
OpenAI-compatible endpoint, imported predictions, and capability graph—but it
does not invoke any of them. Predictions must be supplied explicitly. This
keeps CI free of credentials, network access, model loading, and training.

## Verify

```bash
bash evals/everyday-benchmark-smoke.sh
```

The smoke validates committed configs and fixtures, then exercises success and
rejection paths for disclosure, credentials, repeated-pass coverage,
same-instance comparison, exact/confusion/slice scoring, system selective-risk
metrics, public-only calibration, infeasible-policy rejection, resource
derivation, receipt privacy, determinism, and overwrite protection.

The committed 28-row public fixture is an infrastructure fixture, not a strong
calibration ruler. Threshold selection remains provisional until a larger,
generator-independent public development set is reviewed. A selected policy is
then frozen before any newly generated sealed evaluation; sealed V1 is never a
threshold-fitting input.

Local cohort outputs belong under ignored `runs/` or `benchmark-runs/`. The
remaining launch blockers are two more frontier-qualified task families and
the deterministic cross-task cohort renderer.
