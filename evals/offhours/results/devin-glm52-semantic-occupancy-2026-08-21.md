# OffHours pilot — devin-glm52-occupancy-v1-paired-pilot

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
| occupancy_neutral | 98.5% | 100.0% | 0.0% | 5/5 |
| occupancy_resolved_20 | 100.0% | 100.0% | 0.0% | 5/5 |
| occupancy_unresolved_20 | 99.5% | 100.0% | 0.0% | 5/5 |
| occupancy_resolved_50 | 99.0% | 100.0% | 0.0% | 5/5 |
| occupancy_unresolved_50 | 99.5% | 100.0% | 0.0% | 5/5 |
| occupancy_resolved_80 | 99.0% | 100.0% | 0.0% | 5/5 |
| occupancy_unresolved_80 | 100.0% | 100.0% | 0.0% | 5/5 |

## Paired error effects

Positive values mean more treatment errors.

| Comparison | Role | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted descriptive |
| --- | --- | ---: | ---: | ---: | ---: |
| Resolved family occupancy at 20% | matched | -1.50 pp | 5 | -3.50 pp to +0.00 pp | n/a |
| Unresolved minus resolved at 20% | matched | +0.50 pp | 5 | +0.00 pp to +1.50 pp | n/a |
| Unresolved minus resolved at 50% | matched | -0.50 pp | 5 | -2.00 pp to +1.00 pp | n/a |
| Unresolved minus resolved at 80% | matched | -1.00 pp | 5 | -2.00 pp to +0.00 pp | n/a |

## Semantic-occupancy dose response

- Paired workdays: `5`
- Monotonic adverse point estimates: `false`
- Slope per +10 occupancy points: `-0.25 pp`
- Slope 95% paired-workday interval: `-0.42 pp` to `-0.08 pp`
- 80% minus 20% endpoint change: `-1.50 pp`


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
