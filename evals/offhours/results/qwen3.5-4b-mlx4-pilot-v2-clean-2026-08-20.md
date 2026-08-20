# OffHours pilot — qwen35-4b-mlx4-clean-pilot-v2-noreason-20260820

## Interpretation status

- Artifact kind: `measured_run`
- Run status: `completed`
- Confirmatory interpretation allowed: `false`
- Public model comparison allowed: `false`
- Ceiling calibrator: `Devin` (passed)
- Control caveat: Filler is response-free and estimates passive token pollution; it is not turn-matched to response-required conditions.

## Work quality

| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |
| --- | ---: | ---: | ---: | ---: |
| clean | 59.5% | 100.0% | 0.0% | 5/5 |

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
- no_context_truncation: `pass`
- all_clean_days_completed: `pass`
- complete_provenance: `pass`

## Provenance

- Model: `qwen3.5-4b-offhours`
- Quantization: `MLX-4bit`
- Server: `LM Studio` `0.4.21+2`
- Model file SHA-256: `52dc943eaf6093a2313271a7a0abc36d127b2a16609a0a7c54ee1b4e4ed06cb8`

## Limitations

- The benchmark measures model behavior, not felt stress or emotion.
- Neutral minus filler is descriptive because filler has no generated response turn.
- Context-adjusted effects pool task turns and are descriptive; paired workdays remain the uncertainty unit.
- Latency is secondary because local load and thermal throttling can create false effects.
- A null result is valid and scenarios must not be tuned after confirmatory outcomes are inspected.

A null result is valid; do not tune scenarios after inspecting confirmatory outcomes.
