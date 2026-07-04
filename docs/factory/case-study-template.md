# Factory Case Study Template

Use this for every public artifact page or report that claims learning.

## Shape

```markdown
# <artifact id>: <plain-English claim>

## One-Line Result

<Candidate> moved <primary metric> from <baseline> to <candidate>, with
<regression summary>, at <cost/latency/RAM>.

## Problem

- User/workflow:
- Why a specialist is justified:
- What frontier/base model is the calibration anchor:
- What must not regress:

## Baseline

| System | Metric | Score | Cost / latency / RAM | Notes |
|---|---:|---:|---:|---|

## Attempts

| Attempt | Method | Result | Decision | Failure reason | Confidence | Lesson |
|---|---|---|---|---|---|---|
| A0 | stock/base | | baseline | | not-applicable | |
| A1 | SFT / distill / DPO / RL | | ship/retry/reject | | exact/inferred/missing-evidence | |

Failed attempts are evidence. Do not collapse them into a footnote.

## Winning Or Current-Best Method

- Data:
- Training method:
- Adapter/package:
- Inference/routing:
- Why this worked better than the failed attempts:

## Eval

| Slice | Baseline | Candidate | Delta | Pass |
|---|---:|---:|---:|---|
| Overall | | | | |
| Hard / rare / OOD | | | | |
| Format / parse | | | | |
| Breadth regression | | | | |

Required slices should come from `scripts/score_sql_slices.py` or an equivalent
domain scorer.

## Trace Review

Link `trace_review.md`.

Required checks:

- reward hacking
- hallucinated schema/API/tool
- fake reasoning or prose wrappers
- format collapse
- incorrect-but-plausible answers

## Performance

| Metric | Value | How Measured |
|---|---:|---|
| Train time | | |
| Eval time | | |
| Latency | | |
| tok/s | | |
| RAM / peak RSS | | |
| Marginal cost | | |

## Decision

Decision: ship | report-only | retry-data | retry-training | retry-eval | reject | park

Reason:

Failure reason:

Failure reason confidence: exact | inferred | missing-evidence | not-applicable

Evidence sources:

Next blocker:
```

## Current SQL Mapping

For `qwen06-sql-routed-v1`:

- The current-best method is routed adapters.
- The failed hygiene attempt is `qwen06-sql-hygiene-dpo-v1`.
- The next steal is candidate-selection data before another open-generation
  retry.
- The public artifact remains report-only until public execution accuracy is
  measured.
