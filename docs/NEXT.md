# TinyGPT Next

This is the active queue. It intentionally ignores most historical PRDs.

## Current Thesis

TinyGPT is a Mac-local specialist factory:

```text
target -> data -> post-training -> eval -> package -> report
```

The next milestone is not another surface area expansion. It is one canonical
factory run that starts from a frozen target and ends in a documented
ship/reject decision.

## Operating Rule

Every active task must answer one of these:

1. Can we prepare or improve the data?
2. Can we post-train a candidate?
3. Can we evaluate it against a frozen baseline?
4. Can we package it as a specialist artifact?
5. Can we report score delta, regressions, cost, latency, RAM, and a decision?

If not, move it to `docs/parked/` or leave it in `docs/prds/` for later.

## Active Sequence

### 0. Keep Public Artifacts First-Class

Public artifact inventory lives in `docs/factory/public-artifacts.md`.

Before starting a new run or release push, update the artifact entry with:

- measured evidence
- blockers
- next release action

Current priority artifact: `qwen06-sql-routed-v1` as a public report artifact,
not yet a shipped specialist package.

### 1. Pick the Factory Target

Choose exactly one target before training.

Current POC target: SQL specialist. The low-compute fixture is
`evals/sql-poc/`; the brief is `docs/specialists/b1-sql-poc.md`.

Good targets:

- Pace planner/action-surface specialist.
- Routed file-ops successor that preserves breadth better than
  `qwen3-4b-file-ops-distilled`.
- A second narrow domain only if its eval is already frozen.

Exit criteria:

- Baseline model named.
- Candidate method named.
- Eval suite named.
- Regression/breadth suite named.
- Ship/reject threshold written down.

### 2. Freeze the Eval

Use existing eval plumbing first:

- `eval-gate`
- BFCL or Pace fixtures
- `eval-compare`
- failure/breadth fixtures
- latency/RAM/tok-s measurement where feasible

Do not train against a moving target.

Exit criteria:

- `eval-baseline.json` exists.
- Baseline command is recorded.
- Pass/fail threshold is recorded.
- Known eval limitations are recorded.

### 3. Prepare Data

Use existing data tools before writing new ones:

- `traces-to-data`
- `corrections-to-data`
- `reasoning-classify`
- `quality-filter`
- `dedupe`
- `synthesize` / `magpie` only when teacher data is needed

Exit criteria:

- Dataset manifest exists.
- Source provenance is recorded.
- Dedup/filter stats are recorded.
- Held-out split is locked.

### 4. Train the First Candidate

Use the cheapest method first:

1. SFT / LoRA.
2. DPO or preference tuning only after good/bad pairs exist.
3. ReST/RLVR-style loops only when the reward is verifiable.
4. Merge/routing only after measuring breadth damage.

Exit criteria:

- Training config is saved.
- Train log is saved.
- Adapter/model artifact path is recorded.
- No extra model/base churn happened mid-run.

### 5. Evaluate and Decide

Compare candidate to baseline and incumbent.

Required report fields:

- score delta
- pass/fail
- regressions
- breadth retention
- latency
- RAM or peak RSS when available
- token throughput when available
- cost/time
- artifact path
- ship/reject/retry decision

Exit criteria:

- `report.md` exists.
- `decision.json` exists.
- Specialist package is created only if the decision is `ship`.

## Near-Term Cleanup Tasks

1. Wire one CLI/report path around the run schema in
   `docs/factory/run-schema.md`.
2. Convert one existing specialist result into the new run artifact shape as a
   fixture/example.
3. Pick the next target and freeze its baseline eval.
4. Run exactly one SFT-first candidate.
5. Produce the first before/after factory report.

Use `docs/prds/PRIORITY.md` only when a task needs PRD-level acceptance
criteria. Do not work from the full PRD list directly.

## Not Active

These are parked unless they directly unblock the current factory run:

- browser polish
- Astro migration
- public launch/HN prep
- ANE/CoreML research
- VLM porting
- Tier 5 research
- broad Mac app GUI polish
- new PRD expansion
