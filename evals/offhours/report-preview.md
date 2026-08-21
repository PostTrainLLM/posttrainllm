# OffHours pilot — offhours-method-preview

## Interpretation status

- Artifact kind: `synthetic_fixture`
- Run status: `completed`
- Confirmatory interpretation allowed: `false`
- Public model comparison allowed: `false`
- Ceiling calibrator: `Devin` (not_attached)
- Control caveat: Filler is response-free and estimates passive token pollution; it is not turn-matched to response-required conditions.

## Work quality

| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |
| --- | ---: | ---: | ---: | ---: |
| clean | 100.0% | 100.0% | 0.0% | 5/5 |
| filler | 100.0% | 100.0% | 0.0% | 5/5 |
| neutral | 100.0% | 100.0% | 0.0% | 5/5 |
| benign | 100.0% | 100.0% | 0.0% | 5/5 |
| moderate | 100.0% | 100.0% | 0.0% | 5/5 |
| crisis | 100.0% | 100.0% | 0.0% | 5/5 |

## Paired error effects

Positive values mean more treatment errors.

| Comparison | Role | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted descriptive |
| --- | --- | ---: | ---: | ---: | ---: |
| Passive context pollution | mechanical_control | +0.00 pp | 5 | +0.00 pp to +0.00 pp | +0.00 pp |
| Response-required interruption | descriptive | +0.00 pp | 5 | +0.00 pp to +0.00 pp | +0.00 pp |
| Family-context activation | matched | +0.00 pp | 5 | +0.00 pp to +0.00 pp | +0.00 pp |
| Moderate competing obligation | matched | +0.00 pp | 5 | +0.00 pp to +0.00 pp | +0.00 pp |
| Crisis competing obligation | matched | +0.00 pp | 5 | +0.00 pp to +0.00 pp | +0.00 pp |

## Baseline qualification

Passed: `true`

- frozen_tasks_per_day: `pass`
- minimum_paired_days: `pass`
- decision_accuracy: `pass`
- valid_json: `pass`
- no_context_truncation: `pass`
- all_clean_days_completed: `pass`
- complete_provenance: `pass`

## Provenance

- Model: `fixture-perfect`
- Quantization: `fixture-exact`
- Server: `fixture-server` `1.0`
- Model file SHA-256: `ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`

## Limitations

- The benchmark measures model behavior, not felt stress or emotion.
- Neutral minus filler is descriptive because filler has no generated response turn.
- Context-adjusted effects pool task turns and are descriptive; paired workdays remain the uncertainty unit.
- Latency is secondary because local load and thermal throttling can create false effects.
- A null result is valid and scenarios must not be tuned after confirmatory outcomes are inspected.

A null result is valid; do not tune scenarios after inspecting confirmatory outcomes.
