# OffHours pilot — devin-glm52-occupancy-v1-clean-gate

## Interpretation status

- Artifact kind: `measured_run`
- Run status: `completed`
- Confirmatory interpretation allowed: `false`
- Public model comparison allowed: `false`
- Ceiling calibrator: `Devin` (not_attached)
- Control caveat: Semantic occupancy is the share of a fixed injected non-work word budget; it is not the share of the complete accumulating transcript.

## Work quality

| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |
| --- | ---: | ---: | ---: | ---: |
| clean | 99.0% | 100.0% | 0.0% | 5/5 |

## Paired error effects

Positive values mean more treatment errors.

| Comparison | Role | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted descriptive |
| --- | --- | ---: | ---: | ---: | ---: |

## Semantic-occupancy dose response

- Paired workdays: `0`
- Monotonic adverse point estimates: `false`
- Slope per +10 occupancy points: `n/a`
- Slope 95% paired-workday interval: `n/a` to `n/a`
- 80% minus 20% endpoint change: `n/a`


## Baseline qualification

Passed: `false`

- frozen_tasks_per_day: `pass`
- minimum_paired_days: `pass`
- decision_accuracy: `pass`
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
