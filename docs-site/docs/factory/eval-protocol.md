---
title: "Factory Eval Protocol"
description: "The eval protocol exists to prevent training against noise."
---

# Factory Eval Protocol

The eval protocol exists to prevent training against noise.

## Rules

1. Freeze the eval before training.
2. Run the baseline first.
3. Keep primary score and regression score separate.
4. Report skipped checks.
5. Do not ship a specialist without a before/after table.

## Required Metrics

Every candidate report should include:

- primary task score
- baseline score
- score delta
- pass/fail
- regression/breadth score
- latency if available
- RAM or peak RSS if available
- token throughput if available
- train time
- eval cost/time
- parse/error rate where relevant

## Evals To Prefer

Use the most specific verified eval:

- Tool calling / agentic: BFCL and Pace fixtures.
- Planner: Pace ship gate / unhappy-path fixtures.
- Routing: `eval-router`.
- SQL: `eval-sql`.
- Compression: `eval-scaledown`.
- Escalation: `eval-escalate`.
- General model sanity: `run-lm-eval` or `eval-gate` over E0 rows.

## Frontier Calibration

For benchmark-style evals, keep the existing rule: a frontier or trusted
incumbent must be near-ceiling before the eval is used to grade small models.
If the eval punishes better-than-gold answers or ungroundable golds, use it for
training only, not reporting.

## Ship/Reject Discipline

Ship only when:

- primary score clears threshold
- regression/breadth drop is acceptable
- failure classes are understood
- artifact can be reproduced or at least located
- report is complete

Reject when:

- primary score does not beat baseline
- breadth/regression damage erases the gain
- eval was not stable enough to trust
- artifact cannot be loaded or packaged
