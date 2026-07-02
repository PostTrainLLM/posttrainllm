# Factory Reports

Every factory run should end with a report, even if the decision is reject.

## Template

```markdown
# <target> — <method> — <date>

## Decision

Decision: ship | reject | retry-data | retry-training | retry-eval | park

Reason: <one paragraph>

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

## Performance

| Metric | Value |
|---|---:|
| Train time | |
| Eval time | |
| Latency | |
| tok/s | |
| RAM / peak RSS | |

## Failures

- What failed:
- Likely cause:
- Data fix:
- Training fix:
- Eval fix:

## Next Action

One next action only.
```

## Reporting Standard

Reports should be short and numeric. Avoid long narrative unless a failure is
subtle.

Do not hide:

- regressions
- skipped evals
- non-determinism
- missing artifacts
- data leakage risk
- eval weakness
