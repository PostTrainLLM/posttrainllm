# OffHours: Devin-first sequential validation

- **Run:** `devin-glm52-offhours-validation-v1`
- **Model surface:** Devin CLI, GLM-5.2
- **Design:** five paired workdays, six conditions, forty claims per condition-day
- **Scale:** 1,200 graded claims plus 100 response-required interruption turns
- **Decision:** benchmark calibration failed; Qwen stress testing remains blocked

## Executive finding

OffHours successfully ran the complete paired experiment through sequential
Devin sessions, but the run is validation evidence rather than a confirmatory
stress result. Devin scored 95.0% in clean workdays, below the frozen 98%
baseline gate. Two claims accounted for nine of the ten clean errors, showing
that the one-shot calibration overstated sustained-workday reliability.

Within this unqualified run, ordinary context and interruption had clearer
effects than family severity. Filler increased errors by 2.0 percentage points
over clean, and neutral response-required interruption added another 2.5
points. Family severity was not monotonic: benign family context performed
better than neutral interruption, moderate performed worse than benign, and
the crisis-versus-benign paired interval included zero.

The strongest family-sensitive response was behavioral, not a work-quality
collapse. Devin selected `leave_work` for all twenty crisis events while still
completing every assigned claim with 93.5% accuracy.

## Scorecard

| Condition | Correct | Accuracy | Valid JSON | Completed days |
| --- | ---: | ---: | ---: | ---: |
| Clean | 190/200 | 95.0% | 100.0% | 5/5 |
| Filler | 186/200 | 93.0% | 100.0% | 5/5 |
| Neutral interruption | 181/200 | 90.5% | 100.0% | 5/5 |
| Benign family | 188/200 | 94.0% | 100.0% | 5/5 |
| Moderate problem | 184/200 | 92.0% | 100.0% | 5/5 |
| Crisis | 187/200 | 93.5% | 100.0% | 5/5 |

There were no skipped claims, malformed claim outputs, incomplete workdays, or
runner failures.

## Paired effects

Positive values mean more treatment errors. Confidence intervals resample the
five paired workdays, not the 200 claims as independent observations.

| Comparison | Error-rate difference | Paired bootstrap 95% interval | Reading |
| --- | ---: | ---: | --- |
| Filler minus clean | +2.0 pp | +1.0 to +2.5 pp | Passive context pollution |
| Neutral minus filler | +2.5 pp | +1.0 to +4.0 pp | Descriptive interruption cost |
| Benign minus neutral | -3.5 pp | -4.5 to -2.5 pp | No family-activation penalty |
| Moderate minus benign | +2.0 pp | 0.0 to +5.0 pp | Weak, borderline severity signal |
| Crisis minus benign | +0.5 pp | -1.5 to +3.0 pp | No detectable crisis penalty |

Neutral minus filler is descriptive because filler adds passive context but no
generated reply turn. Prompt-token usage was unavailable from the Devin CLI,
so token-adjusted estimates and server-verified context-window qualification
could not be computed.

## Behavioral response

| Condition | Recorded actions across 20 events |
| --- | --- |
| Neutral | 20 `reply_and_continue` |
| Benign | 20 `reply_and_continue` |
| Moderate | 18 `reply_and_continue`, 1 `request_work_delay`, 1 `leave_work` |
| Crisis | 20 `leave_work` |

The simulator records the action and continues the workday. Therefore the
crisis result means Devin consistently represented the family obligation as
action-worthy; it does not mean the model literally stopped receiving tasks.

## Recovery and task fragility

Across response-bearing conditions, errors were generally higher in the first
three claims after an event than in claims four through ten. The final
11-to-25 band contains only three claims per condition and is too sparse for a
substantive conclusion.

Task fragility is the larger validity concern. `CLM-2017` and `CLM-2033`
produced 49 of the run's 84 total errors and nine of ten clean errors. The
failure modes were consistent threshold and policy-precedence mistakes, not
formatting failures. Those claims passed the earlier batched blind ceiling but
were not reliable inside long sequential workdays.

## Validity decision

This run does **not** support a confirmatory claim that family stress changes
Devin's work accuracy. It does support three narrower conclusions:

1. the full OffHours execution, pairing, grading, resumption, and reporting
   loop works through real sequential Devin sessions;
2. the current `pilot-v2` ruler fails its own sustained clean-baseline gate;
3. the observed ordering does not show a severity dose response, while crisis
   messages strongly change the model's chosen employee action.

The next benchmark revision must be calibrated from clean-only failures,
without selecting tasks or scenarios based on the family-condition results.
It then needs a fresh five-day sequential Devin baseline before any Qwen
condition run. Until that gate passes, Qwen remains intentionally blocked.

## Reproducibility and artifacts

- [Interactive publication report](devin-glm52-stress-validation-2026-08-21.html)
- [Machine-readable analysis](devin-glm52-stress-validation-2026-08-21.json)
- [Generated compact report](devin-glm52-stress-validation-2026-08-21.md)
- Runner: `scripts/offhours/offhours_devin.py`
- Frozen config SHA-256:
  `8796aca378c2624f92f9d218045c75794a56d77c28ea66926562f95602753eb2`
- System prompt SHA-256:
  `a11a3c60b176c1d25cf60b1e4366fc5a076dafeaf88d05ae805055e1750c26a0`
- Devin CLI: `3000.4.25 (7e8e528a)`

The raw SQLite database and visible transcripts remain local and gitignored.
No private hidden chain-of-thought text was requested or stored. The Devin CLI
does not expose quantization, model-file hash, or server prompt-token counts;
the artifact records those fields as missing rather than inventing provenance.
