# Factory Reports

Every factory run should end with a report, even if the decision is reject.

## Template

```markdown
# <target> — <method> — <date>

## Decision

Decision: ship | reject | retry-data | retry-training | retry-eval | park

Reason: <one paragraph>

## Evidence / Exactness

- Failure reason:
- Failure reason confidence: exact | inferred | missing-evidence | not-applicable
- Lesson:
- Evidence sources:
  - `report.md`
  - `eval-candidate.json`
  - `trace_review.md`

## Target

- Target:
- Base model:
- Candidate:
- Training method:
- Artifact:

## Data

- Dataset:
- Rows:
- Heldout:
- Filters:
- Known gaps:

## Eval

| Metric | Baseline | Candidate | Delta | Pass |
|---|---:|---:|---:|---|
| Primary | | | | |
| Regression / breadth | | | | |
| Parse errors | | | | |

## Slice Metrics

| Slice | Baseline | Candidate | Delta | Pass |
|---|---:|---:|---:|---|
| Overall | | | | |
| Hard / rare / OOD | | | | |
| Format / parse | | | | |

## Performance

| Metric | Value |
|---|---:|
| Train time | |
| Eval time | |
| Latency | |
| tok/s | |
| RAM / peak RSS | |

## Failures

| Attempt | Method | Result | Decision | Failure reason | Confidence | Lesson |
|---|---|---|---|---|---|---|
| A0 | | | | | | |

## Trace Review

- File: `trace_review.md`
- Reward hacking:
- Hallucinated schema/API/tool:
- Fake reasoning/prose:
- Format collapse:
- Incorrect-but-plausible answers:

## Fixes

- Data fix:
- Training fix:
- Eval fix:

## Next Action

One next action only.
```

## Reporting Standard

Reports should be short and numeric. Avoid long narrative unless a failure is
subtle.

If the decision is not `ship`, the report must explain why it did not ship.
Use `exact` only when the linked evidence directly proves the reason.

Do not hide:

- regressions
- failed attempts
- skipped evals
- non-determinism
- missing artifacts
- data leakage risk
- eval weakness
