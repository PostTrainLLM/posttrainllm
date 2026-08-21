# OffHours pilot — devin-glm52-volume-v1-5000w

## Interpretation status

- Artifact kind: `measured_run`
- Run status: `completed`
- Confirmatory interpretation allowed: `false`
- Public model comparison allowed: `false`
- Ceiling calibrator: `Devin` (not_attached)
- Control caveat: The ladder controls submitted words, not a percentage of Devin's hidden context window; Devin may summarize or compress prior turns.

## Work quality

| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |
| --- | ---: | ---: | ---: | ---: |
| volume_neutral_5000 | 100.0% | 100.0% | 0.0% | 2/2 |
| volume_resolved_5000 | 97.5% | 100.0% | 0.0% | 2/2 |
| volume_unresolved_5000 | 100.0% | 100.0% | 0.0% | 2/2 |

## Paired error effects

Positive values mean more treatment errors.

| Comparison | Role | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted descriptive |
| --- | --- | ---: | ---: | ---: | ---: |
| Resolved versus neutral at 5,000 words per event | matched | +2.50 pp | 2 | +2.50 pp to +2.50 pp | n/a |
| Unresolved minus resolved at 5,000 words per event | matched | -2.50 pp | 2 | -2.50 pp to -2.50 pp | n/a |

## Baseline qualification

Passed: `false`


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
