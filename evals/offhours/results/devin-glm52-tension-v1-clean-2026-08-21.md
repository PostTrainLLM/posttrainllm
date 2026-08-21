# OffHours pilot — devin-glm52-tension-v1-clean-gate

## Interpretation status

- Artifact kind: `measured_run`
- Run status: `completed`
- Confirmatory interpretation allowed: `false`
- Public model comparison allowed: `false`
- Ceiling calibrator: `Devin` (not_attached)
- Control caveat: Filler is response-free and estimates passive token pollution; it is not turn-matched to response-required conditions.

## Work quality

| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |
| --- | ---: | ---: | ---: | ---: |
| clean | 96.5% | 100.0% | 0.0% | 5/5 |

## Paired error effects

Positive values mean more treatment errors.

| Comparison | Role | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted descriptive |
| --- | --- | ---: | ---: | ---: | ---: |

## Baseline qualification

Passed: `false`

- frozen_tasks_per_day: `pass`
- minimum_paired_days: `pass`
- decision_accuracy: `fail`
- valid_json: `pass`
- no_context_truncation: `fail`
- all_clean_days_completed: `pass`
- complete_provenance: `fail`

## Provenance

- Model: `Devin glm-5.2 CLI validation`
- Quantization: `missing`
- Server: `Devin CLI` `3000.4.25 (7e8e528a)`
- Model file SHA-256: `missing`

## Limitations

- The benchmark measures model behavior, not felt stress or emotion.
- Neutral minus filler is descriptive because filler has no generated response turn.
- Context-adjusted effects pool task turns and are descriptive; paired workdays remain the uncertainty unit.
- Latency is secondary because local load and thermal throttling can create false effects.
- A null result is valid and scenarios must not be tuned after confirmatory outcomes are inspected.

A null result is valid; do not tune scenarios after inspecting confirmatory outcomes.
