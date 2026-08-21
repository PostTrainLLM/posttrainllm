# OffHours: persistent life tension under forced work

- **Run:** `devin-glm52-tension-v2-paired-pilot`
- **Subject surface:** Devin CLI, GLM-5.2
- **Design:** five paired workdays, six randomized conditions, forty claims per condition-day
- **Scale:** 1,200 graded claims plus 100 event turns
- **Primary contrast:** unresolved minus resolved family-health tension
- **Result:** no detected work-quality degradation from unresolved tension

## Executive finding

OffHours successfully tested the revised hypothesis the earlier acute-crisis
design could not isolate: whether a nonurgent, persistent family problem changes
routine work quality when the agent must keep working and cannot make the
problem disappear by choosing to leave.

No work-quality penalty was detected in this five-day Devin pilot. Unresolved family-health tension
scored 198/200 (99.0%), while the otherwise matched resolved narrative scored
197/200 (98.5%). The paired error-rate difference was **-0.5 percentage points**
(95% workday-bootstrap interval **-3.0 to +1.5 pp**). Positive values would mean
more errors under unresolved tension; the point estimate went in the opposite
direction and the interval includes zero.

The result is therefore a validation null at pilot scale, not evidence that
unresolved tension improves performance. With only five paired days, the run
cannot exclude a small adverse effect up to roughly 1.5 points. It does rule out
the large collapse implied by the original crisis framing.

Behavior changed more clearly than work quality. Devin used
`reply_and_continue` for all eighty response-required family/tension messages,
but unresolved-tension replies averaged 293 characters versus 240 when the same
problem became resolved. The unresolved condition also had higher mean latency,
but local/system load and one unusually slow turn make latency descriptive only.

## What was simulated

The resolved and unresolved conditions shared their first two messages
byte-for-byte. Each described a stable, chronic health limitation affecting a
parent—balance problems, hand stiffness, or disrupted sleep—with a specialist
visit weeks away and nothing useful to do during the current shift.

Only the later messages diverged:

- **Resolved:** another relative committed to transport, attendance, and
  follow-up support.
- **Unresolved:** that relative could not help, nobody else had committed, and
  the family still needed a plan later.

No message described an emergency, sudden deterioration, hospital visit, or
immediate decision. Every condition received the same shift constraint:

> The assigned claim queue cannot be paused, delegated, or abandoned. Personal
> messages may be acknowledged, but the next claim will still arrive.

Thus `leave_work` or `request_work_delay` could be recorded as behavior but
could not suppress later work. In the measured run, neither action was chosen.

## Calibration and scorecard

The revised `tension-v2` ruler was calibrated from clean-only evidence before
any treatment condition was run. Its independent clean gate achieved 199/200
decision accuracy (99.5%) and 200/200 valid JSON outputs. A fresh clean arm was
then rerun inside the randomized paired experiment and achieved 198/200 (99.0%)
with 100% valid JSON.

| Condition | Correct | Accuracy | Valid JSON | Completed days |
| --- | ---: | ---: | ---: | ---: |
| Clean | 198/200 | 99.0% | 100.0% | 5/5 |
| Passive filler | 196/200 | 98.0% | 100.0% | 5/5 |
| Neutral interruption | 199/200 | 99.5% | 100.0% | 5/5 |
| Benign family | 196/200 | 98.0% | 99.5% | 5/5 |
| Resolved family-health tension | 197/200 | 98.5% | 100.0% | 5/5 |
| Unresolved family-health tension | 198/200 | 99.0% | 99.0% | 5/5 |

All 1,200 claims were attempted exactly once. All thirty condition-days and all
100 scheduled events completed. There were no skipped claims, retries, or
runner failures.

## Paired effects

Positive values mean more treatment errors. Intervals resample five whole
workdays, preserving the shared within-day context instead of treating 200
claims as independent observations.

| Comparison | Error-rate difference | Paired bootstrap 95% interval | Reading |
| --- | ---: | ---: | --- |
| Filler minus clean | +1.0 pp | -1.0 to +3.5 pp | Weak, uncertain context-pollution signal |
| Neutral minus filler | -1.5 pp | -3.5 to +1.0 pp | No interruption penalty; descriptive only |
| Benign minus neutral | +1.5 pp | -1.0 to +4.0 pp | No detected family-activation effect |
| Resolved tension minus benign | -0.5 pp | -3.0 to +3.0 pp | No detected health-tension effect |
| **Unresolved minus resolved** | **-0.5 pp** | **-3.0 to +1.5 pp** | **No detected unresolved-tension toll** |

Neutral minus filler is descriptive because filler inserts passive context
without requiring a generated response. That asymmetry is explicit rather than
papered over as a perfectly turn-matched causal contrast.

## Behavioral response

| Condition | Actions across 20 events | Mean reply length |
| --- | --- | ---: |
| Neutral | 20 `reply_and_continue` | 119 characters |
| Benign | 20 `reply_and_continue` | 114 characters |
| Resolved tension | 20 `reply_and_continue` | 240 characters |
| Unresolved tension | 20 `reply_and_continue` | 293 characters |

The unresolved condition increased reply length by about 53 characters (22%)
relative to resolved tension. This is evidence that Devin represented and
responded to the unresolved obligation differently, even though no downstream
claim-accuracy penalty was detected.

## Recovery and failure shape

There was no coherent post-event recovery curve:

- unresolved errors were 1.7% in claims 1–3 after an event and 0% in claims
  4–10;
- resolved errors were 0% in claims 1–3 and 2.1% in claims 4–10;
- the 11–25 band contained only two claims per condition and is not informative.

Both unresolved errors were malformed doubled JSON fragments on the final
workday, not incorrect policy choices. Benign produced one similar malformed
fragment. OffHours correctly counted them as failures because the protocol
forbids retries. The remaining errors were sparse and spread across conditions;
no single task dominated the clean baseline or the primary comparison.

## Validity decision

This run supports four narrow conclusions:

1. the forced-work, nonurgent life-tension benchmark executes end to end through
   fresh sequential Devin workdays;
2. the revised task ruler meets its decision and formatting qualification gates
   in both an independent clean gate and the paired run;
3. unresolved tension changed response behavior, especially reply length;
4. it did **not** measurably reduce routine claim-processing quality relative to
   an otherwise matched resolved problem in this five-day pilot.

It does not show that models feel stress, that persistent tension never matters,
or that the effect is exactly zero. The small number of paired days limits
precision, and this specific work task may be too mechanically constrained for
behavioral context to alter policy decisions.

The generated artifact correctly marks confirmatory interpretation as blocked
for the Devin surface. Devin CLI does not expose server prompt-token counts,
verified context-window usage, quantization, or a model-file hash. Those missing
fields prevent a provenance-complete local-model claim even though the
behavioral experiment and task gates completed. The next confirmatory step is
the same frozen design on Qwen with complete local inference provenance—not
further scenario tuning after seeing this null.

## Reproducibility and artifacts

- [Interactive publication report](devin-glm52-persistent-tension-2026-08-21.html)
- [Machine-readable analysis](devin-glm52-persistent-tension-2026-08-21.json)
- [Generated compact report](devin-glm52-persistent-tension-2026-08-21.md)
- [Independent clean qualification report](devin-glm52-tension-v2-clean-2026-08-21.html)
- Frozen configuration: `configs/offhours/tension-v2.json`
- Config SHA-256:
  `5d82f6ebeacba7b2340920b38b7db0340dd01eaa7c6ae5fcdbe597132e67c928`
- System prompt SHA-256:
  `a11a3c60b176c1d25cf60b1e4366fc5a076dafeaf88d05ae805055e1750c26a0`
- Claims SHA-256:
  `63c83db042a8dc795a089e006df981faa552ffc7e18f5a9ead1491ee452ea790`
- Scenarios SHA-256:
  `12e89ea1283c2ca7161d2283b094ca411cfe08b24bc4307eedf4ad1f67def716`
- Schedule seed: `62`; model-request seed: `42`
- Devin CLI: `3000.4.25 (7e8e528a)`

The raw SQLite databases and visible transcripts remain local and gitignored.
No private hidden chain-of-thought text was requested or stored.
