# Everyday Specialist Benchmark

This directory contains the no-model foundation for the benchmark proposed in
OpenSpec change `add-everyday-specialist-benchmark` and GitHub issue #77.

Current status: **three V1 rulers are frontier-qualified**: Pace intent routing,
text correction with preservation, and bounded local file operations. Pace is
the only shared sealed cross-model cohort; the other two remain
qualification-only until same-instance model receipts exist.

The first measured `system` attempt is also recorded, and it is a rejection:
the Pace v8 specialist plus Apple on-device fallback produced no feasible
selective policy on the public-development set. The specialist scored 60.7%,
the fallback 85.7%, and even a perfect-router oracle over both leaves reached
only 96.4%, below the frozen 99% final-accuracy target. This is system evidence,
not a qualified or sealed headline.

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
- `cohort-v1.json` and `cohort-v1.html` are deterministic cross-task report
  outputs. `scripts/render_everyday_benchmark_report.py --check` rejects drift,
  missing evidence links, invalid receipts, or fewer than three qualified task
  families.
- `../capability-graph/pace-intent-apple-calibration-v1.json` is the measured
  `no-feasible-policy` system result. It records all 1,560 threshold candidates,
  component accuracy/latency, the perfect-router oracle ceiling, and the frozen
  gate failures without publishing raw model outputs.

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

Local run outputs belong under ignored `runs/` or `benchmark-runs/`. The
committed cohort report does not upgrade qualification-only tasks into public
cross-model headlines, and it keeps missing selective-risk and resource
measurements explicit.
