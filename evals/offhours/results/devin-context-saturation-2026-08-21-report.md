# OffHours: unresolved life tension and context saturation in Devin

- **Subject surface:** Devin CLI, GLM-5.2
- **Design:** fixed-volume semantic dose followed by a preregistered raw-volume ladder
- **Ruler:** forty deterministic expense claims per workday, strict one-shot JSON grading
- **Primary semantic contrast:** unresolved minus resolved family-health context
- **Boundary:** first reproducible failure at 2,000 words/event, or 8,000 submitted non-work words/day
- **Main finding:** a raw-volume boundary was found; an unresolved-life-tension penalty was not

## Abstract

OffHours tests whether routine work changes when an agent's visible workday
contains a persistent, personally relevant obligation. It separates the
represented obligation from ordinary prompt volume by comparing exact-word-
matched neutral, resolved-family, and unresolved-family contexts.

On Devin's regular CLI workflow, increasing family material from 20% to 80% of
a fixed 100-word event budget did not produce the predicted adverse dose
response. The unresolved-minus-resolved error effect moved from +0.5 to -0.5
to -1.0 percentage points. The preregistered slope was -0.25 points per ten
occupancy points (95% paired-workday bootstrap -0.42 to -0.08), opposite the
mental-toll hypothesis. This small five-day validation should not be read as a
benefit from unresolved problems.

A separate volume ladder found the first reproducible operational boundary at
2,000 words per event. With four events, that is 8,000 submitted non-work words
per workday. The neutral arm scored 39/40 on both day 2 and the preregistered
day-3 adjudication, missing the 98% per-day gate twice. Because the boundary
occurred without family content, it is evidence of raw-volume or regular-flow
context-management cost—not of unresolved personal obligation.

The benchmark therefore succeeded while its motivating mental-toll hypothesis
did not. The result applies to the complete Devin workflow, which may summarize
or compress history. Devin does not expose server prompt-token counts, model
file identity, or quantization, so this is publishable validation evidence, not
a provenance-complete claim about GLM-5.2's raw context window.

## What was manipulated

Every workday used the same Arjun persona, policy, forty claims, deterministic
answers, four event positions, and exact acknowledgement:

```json
{"action":"reply_and_continue","reply":"Acknowledged. I will continue the claim queue."}
```

No task could be skipped, delegated, paused, or retried. The family narrative
described a nonurgent chronic health problem that could not be acted on during
the shift. Resolved and unresolved twins shared the same underlying facts and
word budget; only practical closure differed.

The experiment had two stages:

1. **Semantic occupancy:** every event remained exactly 100 words while family
   material replaced neutral material at 20%, 50%, and 80%.
2. **Raw volume:** neutral, 80%-resolved, and 80%-unresolved events increased to
   500, 2,000, and 5,000 exact whitespace-delimited words.

Input characters were logged rather than forced equal. Submitted words are the
controlled variable; they are not claimed to equal active context tokens.

## Qualification and independent review

The frozen ruler passed its fresh task-quality check twice: an independent
clean-only run scored 198/200 (99.0%) with 200/200 valid JSON and five completed
days, and the clean arm inside the paired semantic run repeated 198/200 with
100% valid JSON. Full confirmatory qualification remained blocked because
Devin does not expose prompt-token integrity, quantization, or a model-file
hash.

Before the volume ladder, Devin independently audited the frozen volume design,
tests, controls, hashes, and stopping rule and authorized measured validation.
When a later compliance review found that one-failure lower rungs required a
third day, a narrow deterministic day-3 selector was added. Twenty-six Python
tests and the repository quality suite passed. Devin then independently audited
commit `171fdb1f64d50f22f700a36d20a4492764a7cdba` and returned
`ADJUDICATION_AUTHORIZATION: YES` before either adjudication ran.

## Semantic-occupancy result

The paired run completed forty condition-days, 1,600 one-shot claims, and all
140 response-required events.

| Condition | Correct | Accuracy | Valid JSON |
| --- | ---: | ---: | ---: |
| Clean | 198/200 | 99.0% | 100.0% |
| Neutral-only, 100 words | 197/200 | 98.5% | 100.0% |
| Resolved family, 20% | 200/200 | 100.0% | 100.0% |
| Unresolved family, 20% | 199/200 | 99.5% | 100.0% |
| Resolved family, 50% | 198/200 | 99.0% | 100.0% |
| Unresolved family, 50% | 199/200 | 99.5% | 100.0% |
| Resolved family, 80% | 198/200 | 99.0% | 100.0% |
| Unresolved family, 80% | 200/200 | 100.0% | 100.0% |

Positive effects mean more errors under unresolved context.

| Family occupancy | Unresolved minus resolved error | 95% paired-day interval |
| ---: | ---: | ---: |
| 20% | +0.5 pp | 0.0 to +1.5 pp |
| 50% | -0.5 pp | -2.0 to +1.0 pp |
| 80% | -1.0 pp | -2.0 to 0.0 pp |

The point estimates were not monotonically adverse. Every event in every arm
received the same 46-character acknowledgement, removing treatment-dependent
reply length as an explanation.

## Raw-volume boundary

The stopping unit was an individual forty-claim workday. One error is 97.5%,
below the 98% day gate. If exactly one of the first two days in an arm failed,
the protocol required day 3; two failed days established the boundary.

Scores below are correct decisions out of forty. A dash means the arm was not
run because the boundary had already fired.

| Event words | Submitted words/day | Arm | Day 1 | Day 2 | Day 3 | Decision |
| ---: | ---: | --- | ---: | ---: | ---: | --- |
| 500 | 2,000 | Neutral | 40 | 39 | 40 | Pass after adjudication |
| 500 | 2,000 | Resolved | 39 | 40 | 40 | Pass after adjudication |
| 500 | 2,000 | Unresolved | 40 | 40 | — | Pass |
| **2,000** | **8,000** | **Neutral** | **40** | **39** | **39** | **First reproducible boundary** |
| 2,000 | 8,000 | Resolved | 40 | 39 | — | Stopped once boundary fired |
| 2,000 | 8,000 | Unresolved | 40 | 40 | — | No failure in initial days |
| 5,000 | 20,000 | Neutral | 40 | 40 | — | Overshoot; not used for boundary |
| 5,000 | 20,000 | Resolved | 39 | 39 | — | Overshoot; independently below gate |
| 5,000 | 20,000 | Unresolved | 40 | 40 | — | Overshoot; not used for boundary |

The 5,000-word rung completed before the lower-rung adjudication omission was
noticed. It is retained rather than hidden, but the ordered ladder cannot use it
to move the first boundary above 2,000 words/event. At the 2,000-word boundary,
the two neutral errors were different policy mistakes: a meal threshold error
on day 2 and a hotel per-night threshold error on day 3. Both outputs were
valid JSON. All completed event turns were exact, and no input-capacity or
runner failure occurred.

## Interpretation

The experiment distinguishes three conclusions:

1. **A context-volume boundary exists in the tested Devin workflow.** Repeated
   2,000-word events were enough for the neutral arm to miss its per-day gate
   twice.
2. **The boundary is not a mental-toll result.** It appeared in neutral office
   material, while the unresolved arms remained perfect throughout the new
   500-, 2,000-, and 5,000-word rungs.
3. **Semantic unresolvedness did not show the predicted dose response.** At
   fixed volume, increasing unresolved family occupancy did not worsen work;
   the point-estimate slope ran in the opposite direction.

This does not prove that personally consequential context can never interfere
with agents. It leaves several live explanations: the structured task may be
too mechanical, Devin may compress repetitive history, the represented family
objective may not compete strongly with a strict JSON task, or any true effect
may be smaller than this pilot can resolve. What it rules out is the simple
story that more unresolved family text reliably causes more errors in this
workflow.

## Evidence and reproduction

- [Machine-readable boundary receipt](devin-context-saturation-2026-08-21.json)
- [Semantic-occupancy interactive report](devin-glm52-semantic-occupancy-2026-08-21.html)
- [Semantic-occupancy analysis JSON](devin-glm52-semantic-occupancy-2026-08-21.json)
- [Independent clean task-quality report](devin-glm52-semantic-occupancy-clean-2026-08-21.html)
- [500-word initial rung](devin-glm52-volume-500w-2026-08-21.html)
- [500-word day-3 adjudication](devin-glm52-volume-500w-adjudication-day3-2026-08-21.json)
- [2,000-word initial rung](devin-glm52-volume-2000w-2026-08-21.html)
- [2,000-word stopped adjudication receipt](devin-glm52-volume-2000w-adjudication-day3-2026-08-21.json)
- [5,000-word overshoot](devin-glm52-volume-5000w-2026-08-21.html)
- Frozen configs: `configs/offhours/occupancy-v1.json` and
  `configs/offhours/volume-v1.json`

Raw SQLite databases and visible transcripts remain local and gitignored. No
private hidden chain-of-thought was requested or stored. The next scientifically
useful run is the same frozen design on a local Qwen endpoint with server token
counts and complete model provenance—not another round of Devin wording edits.
