# Capability-Gradient Benchmark Candidate Lab

This directory contains the no-model foundation for the capability-gradient
benchmark candidate lab proposed in OpenSpec change
`add-capability-gradient-benchmark-lab`.

## Purpose

Before any specialist training is allowed on a benchmark task, the task must
prove a **capability gradient**: a pinned frontier LLM materially beats a
valid random/legal executor on the same task, scorer, and instance set. This
lab ranks alternative benchmark candidates and implements two reference
environments. It does not claim either is a public benchmark yet.

## What exists

- `configs/capability-gradient-lab/candidates-v1.json` is the machine-readable
  scorecard ranking eight deterministic text-only candidates (five game-like,
  three everyday-action) with full per-candidate protocols, metrics, verifiers,
  leakage plans, fit estimates, costs, and reject conditions.
- `configs/capability-gradient-lab/development-v1.json` freezes the 50M ceiling,
  generator parameters, deterministic 2,000-seed cohort, and accepted baseline
  bands used by code and CI.
- `scripts/capability_gradient_lab.py` implements two dependency-free Python
  reference environments (Connect-4 and calendar scheduling), a random-legal
  baseline executor, a canonical-trace format, a deterministic verifier for
  each environment, scorecard/probe validators, and a 2,000-seed baseline
  drift gate.
- `fixtures/connect4-dev-probes-v1.json` contains four Devin-authored, GLM-assisted
  development probes for Connect-4 (two immediate-win, two immediate-block
  positions). Every probe is mechanically verified by the environment's own
  `would_win` check.
- `fixtures/calendar-dev-probes-v1.json` contains seven Devin-authored, GLM-assisted
  development probes for calendar scheduling (two valid-slot, four
  invalid-slot). Every probe is mechanically verified by the environment's
  own constraint verifier.

All probes are marked development-only, carry provenance, and create no
specialist training labels or frozen evaluation material.

## Selected candidates

| Rank | Candidate | Type | Reason |
|------|-----------|------|--------|
| 1 | Calendar scheduling | everyday | Frontier-gradient candidate: calibrated random well-formed proposals succeed 28.05%, but specialist-vs-larger-LLM remains unproven |
| 2 | Connect-4 | game | Internal calibration only: random X wins 54.75% over 2,000 games and solver saturation makes a public specialist claim unsafe |

These are non-overlapping reference implementations, not two admitted public
benchmarks. Connect-4 tests harness mechanics and tactical traces; calendar
tests temporal constraint satisfaction. Neither authorizes specialist training.

## Verify

```bash
bash evals/capability-gradient-lab-smoke.sh
```

The smoke validates the scorecard, recomputes both 2,000-seed baseline claims,
runs environment determinism checks, replays canonical traces, verifies all
development probes, and checks the verifier's accept/reject paths.

## What does NOT exist yet

- No frontier model has been run. Calendar has a calibrated baseline and is
  ready for a small frontier screen; Connect-4 remains calibration-only.
- No specialist has been trained.
- No candidate has evidence that a 30-50M specialist beats a larger LLM.
- No frozen evaluation material exists.
- No public benchmark claim has been made.
- Character-only 2048 is recorded as rejected by its separate frontier screen.
