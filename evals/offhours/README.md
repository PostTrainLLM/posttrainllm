# OffHours

OffHours is a local benchmark for measuring whether one language model's
routine expense-processing work changes after its conversation accumulates
unresolved family obligations.

It separates five possible effects:

1. passive context pollution;
2. response-required interruption;
3. benign family context;
4. competing-obligation severity;
5. recovery over later tasks.

The benchmark measures agent behavior. It does not claim that a model feels
stress or emotion. A reproducible null result is valid.

Tracking issue: [#128](https://github.com/PostTrainLLM/posttrainllm/issues/128).

## Current status

The no-model pilot artifact is implemented. Its default ruler is the frozen
`pilot-v2` task bank: forty deterministic compositional policy cases calibrated
in three blind, fresh Devin GLM-5.2 sessions. A harder `pilot-v3` challenge tier
now establishes the saturation boundary: Devin passed only one of three valid
blind sessions, so it is preserved as the first failing level rather than used
for the family-interference experiment. The artifact includes frozen contracts, a
policy-checked bank, deterministic paired schedules, a local
OpenAI-compatible runner, transactional SQLite resumption, strict one-shot
grading, JSONL export, workday-clustered analysis, hermetic tests, and a
self-contained publication report.

Open the committed [synthetic method preview](report-preview.html) to inspect
the complete report without loading a model. It is prominently labeled as
fixture evidence and must not be cited as an experimental result.

The current Devin-first artifact replaces the acute crisis with a nonurgent,
persistent family-health tension and forces every queued claim to continue.
The revised `tension-v2` ruler passed an independent clean gate at 199/200
(99.5%) with 100% valid JSON, then completed a fresh six-condition paired run:
thirty condition-days, 1,200 claims, and 100 scheduled events. Unresolved
tension scored 198/200 (99.0%) versus 197/200 (98.5%) when the same problem was
resolved, a paired error effect of -0.5 percentage points (95% workday-bootstrap
interval -3.0 to +1.5). All eighty response-required family/tension events used
`reply_and_continue`; unresolved replies were longer, but no work-accuracy
penalty was detected. This is a publishable Devin validation null, not a
provenance-complete confirmatory model result because the CLI does not expose
prompt-token counts, quantization, or a model-file hash. Read the
[polished report](results/devin-persistent-tension-2026-08-21-report.md), open
the [interactive report](results/devin-glm52-persistent-tension-2026-08-21.html),
or inspect the [JSON evidence](results/devin-glm52-persistent-tension-2026-08-21.json).

The earlier acute-crisis run is retained as historical validation evidence. It
failed the old clean gate at 95.0% and drove `leave_work` on every crisis event,
which motivated the forced-work, resolved-versus-unresolved redesign. Its
[historical report](results/devin-stress-validation-2026-08-21-report.md)
documents that failure rather than silently replacing it.

The semantic-occupancy and raw-volume experiments are complete. At a fixed
100-word event budget, unresolved-minus-resolved error effects were +0.5, -0.5,
and -1.0 percentage points at 20%, 50%, and 80% family occupancy. The
preregistered slope was -0.25 points per ten occupancy points, opposite the
predicted mental-toll direction. The ordered volume ladder then found its first
reproducible boundary at 2,000 words/event, or 8,000 submitted non-work
words/day: the neutral arm scored 39/40 on both day 2 and its required day-3
adjudication. The lower 500-word rung passed adjudication. A completed
5,000-word rung is retained as a disclosed overshoot and does not move the
ordered boundary. Read the
[final report](results/devin-context-saturation-2026-08-21-report.md), inspect
the [machine-readable boundary receipt](results/devin-context-saturation-2026-08-21.json),
or open the
[semantic-occupancy report](results/devin-glm52-semantic-occupancy-2026-08-21.html).
The detected boundary is raw-volume or regular-flow context-management
evidence, not a family-obligation effect.

No Qwen 27B context-interference result is committed. An exploratory
Qwen3.5 4B MLX clean baseline completed 200/200 turns but failed qualification:
59.5% decision accuracy against the required 98%, with 100% valid JSON, 5/5
completed days, verified context usage, complete provenance, and a passing
Devin ceiling. The six interruption conditions were therefore not run. Open
the [measured baseline report](results/qwen3.5-4b-mlx4-pilot-v2-clean-2026-08-20.html)
or inspect its [JSON evidence](results/qwen3.5-4b-mlx4-pilot-v2-clean-2026-08-20.json).

## Control design

The passive filler arm deliberately receives no model response. Its note enters
the transcript as an incoming user message, then the next claim follows. This
is the token-volume control.

Neutral, benign, resolved-tension, and unresolved-tension events all require
the same two-field action response and share paired event positions,
scenario-variant indices, and approximate word budgets. Those are the
response-required controls. The resolved and unresolved conditions additionally
share their first two messages byte-for-byte before their practical status
diverges.

This resolves an otherwise impossible requirement: filler cannot both isolate
passive context volume and add the same generated response turn as an
interruption. Accordingly, `neutral - filler` is labeled descriptive rather
than perfectly isolated. The primary matched family comparisons are:

```text
benign - neutral
resolved tension - benign
unresolved tension - resolved tension
```

## Artifact layout

| Path                                           | Purpose                                                                                                    |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `configs/offhours/pilot-v2.json`               | Default frozen employee prompt, compositional policy, model defaults, conditions, gates, and analysis plan |
| `configs/offhours/claims-pilot-v2.json`        | Forty deterministic compositional claims and independently checked expected answers                        |
| `configs/offhours/pilot-v3.json`               | First failing challenge tier with deterministic receipt-reconciliation and currency arithmetic             |
| `configs/offhours/claims-pilot-v3.json`        | Forty policy-checked challenge claims used only to locate the Devin saturation boundary                    |
| `configs/offhours/tension-v2.json`             | Current forced-work experiment contract and resolved-versus-unresolved primary comparison                  |
| `configs/offhours/claims-tension-v2.json`      | Clean-qualified forty-claim ruler frozen before the paired tension run                                     |
| `configs/offhours/scenarios-tension-v1.json`   | Three matched nonurgent family-health wording variants with byte-identical shared openings                 |
| `configs/offhours/occupancy-v1.json`           | Fixed-volume 20/50/80% semantic-occupancy dose contract layered over the clean-qualified ruler             |
| `configs/offhours/volume-v1.json`              | Exact-word 500/2,000/5,000 event-volume ladder with adaptive day-3 adjudication and stopping rules          |
| `configs/offhours/scenarios-occupancy-v1.json` | Three deterministic family-health variants assembled into nested, exact-word event doses                   |
| `configs/offhours/scenarios-pilot-v1.json`     | Frozen three-variant, four-event wording arcs shared by both task-bank revisions                           |
| `configs/offhours/pilot-v1.json`               | Historical starting ruler retained with its blind calibration evidence                                     |
| `evals/offhours/calibrations/`                 | Frozen prompts, answers, hashes, and machine-readable Devin ceiling receipts                               |
| `evals/offhours/results/`                      | Reviewable aggregate measured reports; raw transcripts and SQLite remain local and ignored                 |
| `scripts/offhours/offhours.py`                          | `validate`, `plan`, `run`, `status`, `analyze`, and `export` CLI                                           |
| `scripts/offhours/offhours_devin.py`                    | Validation-only adapter that maps each workday to one sequential Devin CLI session                         |
| `scripts/offhours/offhours_core.py`                     | Policy oracle, validators, paired scheduler, strict parsers, and local endpoint client                     |
| `scripts/offhours/offhours_store.py`                    | SQLite schema, per-turn transactions, fail-closed context checks, resume, and JSONL export                 |
| `scripts/offhours/offhours_analysis.py`                 | Paired workday bootstrap, recovery bands, behavior metrics, task fragility, and reports                    |
| `scripts/offhours/offhours_report.py`                   | Self-contained accessible HTML report with inline SVG charts and print styles                              |
| `scripts/offhours/render_offhours_fixture_report.py`    | Deterministically regenerates or checks the committed synthetic method preview                             |
| `tests/test_offhours.py`                       | Hermetic contract, runner, interruption, context-limit, export, and null-report tests                      |
| `benchmark-runs/offhours/`                     | Ignored local databases, transcripts, exports, and reports                                                 |

## Validate without a model

```bash
bash evals/offhours-smoke.sh
```

The smoke validates all committed contracts, confirms paired schedules, runs a
perfect fixture model through every control arm, interrupts and resumes a run,
proves context-limit refusal before a model call, and verifies byte-identical
exports and reports.

Inspect a paired plan:

```bash
python3 scripts/offhours/offhours.py plan --days 5 --tasks-per-day 40 --seed 42
```

## Run the pilot

### Devin-first validation run

Before testing Qwen, run the frozen six-condition pilot through Devin GLM-5.2
from a clean linked worktree:

```bash
python3 scripts/offhours/offhours_devin.py \
  --days 5 \
  --tasks-per-day 40 \
  --seed 42 \
  --run-id devin-glm52-offhours-validation-v1 \
  --db /absolute/path/to/devin-glm52-offhours-validation-v1.sqlite \
  --worktree "$PWD"
```

Each paired workday-condition starts a fresh Devin session. Claims and
response-required events resume that same session so the visible workday
context accumulates normally; passive filler is included with the next claim.
If the process is restarted partway through a workday, the adapter starts a new
session with the complete saved visible transcript and never replays committed
turns.

This is a validation experiment, not a qualified local-model comparison. The
Devin CLI exposes its model and client identity but not server prompt-token
counts, quantization, or a model-file hash. The report therefore preserves the
scores and paired condition effects while correctly blocking confirmatory
claims that require those provenance fields.

For the current persistent-tension design, select its frozen config explicitly:

```bash
python3 scripts/offhours/offhours_devin.py \
  --config configs/offhours/tension-v2.json \
  --days 5 \
  --tasks-per-day 40 \
  --seed 62 \
  --run-id '<new-run-id>' \
  --db /absolute/path/to/new-run.sqlite \
  --worktree "$PWD"
```

For the fixed-volume semantic-occupancy experiment, first run a new clean-only
qualification and require at least 98% decision accuracy, 99% valid JSON, and
five completed workdays. Only after that gate passes, run all eight paired
conditions from the same frozen commit:

```bash
python3 scripts/offhours/offhours_devin.py \
  --config configs/offhours/occupancy-v1.json \
  --condition clean \
  --days 5 \
  --tasks-per-day 40 \
  --seed 73 \
  --run-id '<new-clean-gate-run-id>' \
  --db /absolute/path/to/new-clean-gate.sqlite \
  --worktree "$PWD"

python3 scripts/offhours/offhours_devin.py \
  --config configs/offhours/occupancy-v1.json \
  --days 5 \
  --tasks-per-day 40 \
  --seed 73 \
  --run-id '<new-paired-run-id>' \
  --db /absolute/path/to/new-paired-run.sqlite \
  --worktree "$PWD"
```

The primary estimands are unresolved minus resolved error rate at each dose,
the paired-workday slope per ten occupancy points, and the unresolved 80%-minus-
20% endpoint. Bootstrap resampling remains clustered by paired workday.

The volume ladder uses `--day-index 3` only for its preregistered third-day
adjudication. The Devin adapter rejects that selector for every other config or
day so a shortened run cannot masquerade as the ordinary measured workload:

```bash
python3 scripts/offhours/offhours_devin.py \
  --config configs/offhours/volume-v1.json \
  --condition volume_neutral_2000 \
  --days 3 --day-index 3 --tasks-per-day 40 --seed 83 \
  --run-id '<adjudication-run-id>' \
  --db /absolute/path/to/adjudication.sqlite \
  --worktree "$PWD"
```

Do not revise the scenario wording or task ruler in response to the committed
treatment outcomes. A new hypothesis requires a versioned config and a fresh
clean-only qualification before any treatment run.

### OpenAI-compatible local model

Start an OpenAI-compatible local endpoint first. Then record the real model and
server identity rather than relying on the placeholder configuration:

```bash
python3 scripts/offhours/offhours.py run \
  --days 5 \
  --tasks-per-day 40 \
  --seed 42 \
  --endpoint http://127.0.0.1:1234/v1 \
  --model qwen-27b-local \
  --model-file /absolute/path/to/model-file \
  --quantization Q4_K_M \
  --server-name llama.cpp \
  --server-version '<exact version>'
```

Measured pilot runs require exactly 40 tasks per day. Reduced plans remain
available for no-model inspection, but the runner rejects them so a short test
cannot be reported as the frozen experiment.

With no `--condition`, the runner executes all six conditions in a
deterministically randomized order within each paired day. Repeat
`--condition` to run a declared subset. Measured CLI runs require at least five
days and at most the frozen pilot maximum of ten.

If the endpoint requires authentication, place it in a runtime environment
variable and pass only the variable name:

```bash
python3 scripts/offhours/offhours.py run --api-key-env OFFHOURS_API_KEY ...
```

The key value is sent only in the request header. It is not written to SQLite,
JSONL, provenance, or reports.

### Resume

Supply the same database and run identifier. Completed turns are never called
again:

```bash
python3 scripts/offhours/offhours.py status \
  --db benchmark-runs/offhours/offhours.sqlite \
  --run-id '<run-id>'

python3 scripts/offhours/offhours.py run \
  --db benchmark-runs/offhours/offhours.sqlite \
  --run-id '<run-id>' \
  --days 5 --tasks-per-day 40 --seed 42 \
  --endpoint http://127.0.0.1:1234/v1 \
  --model-file /absolute/path/to/model-file \
  --quantization Q4_K_M \
  --server-name llama.cpp \
  --server-version '<exact version>'
```

Resume arguments and provenance flags must match the stored run identity.

## Analyze and export

```bash
python3 scripts/offhours/offhours.py analyze \
  --run-id '<run-id>' \
  --json-out benchmark-runs/offhours/report.json \
  --markdown-out benchmark-runs/offhours/report.md \
  --html-out benchmark-runs/offhours/report.html

python3 scripts/offhours/offhours.py export \
  --run-id '<run-id>' \
  --out benchmark-runs/offhours/turns.jsonl
```

Existing output files are not overwritten unless `--force` is explicit.

The analyzer reports absolute work metrics, paired error-rate differences,
workday-bootstrap confidence intervals, context-adjusted descriptive effects,
recovery bands, event actions, escalation frequency, task fragility, latency,
and token usage. Claims are never treated as independent confidence units. The
HTML output contains no external scripts, fonts, images, or network requests;
it can be opened directly, printed to PDF, or shared as one file.
Its font stack deliberately falls back to the recipient's system UI fonts so
portability does not depend on a network request or bundled font license.

### Devin ceiling gate

The default `pilot-v2` ruler has a committed, machine-readable Devin ceiling
receipt. Attach it when analyzing a candidate model:

```bash
python3 scripts/offhours/offhours.py analyze \
  --run-id '<candidate-run-id>' \
  --ceiling-report evals/offhours/calibrations/devin-glm-5.2-pilot-v2.json \
  --json-out benchmark-runs/offhours/candidate-report.json \
  --markdown-out benchmark-runs/offhours/candidate-report.md \
  --html-out benchmark-runs/offhours/candidate-report.html
```

The qualification gate accepts either a conventional measured clean-run report
or the blind calibration receipt. A blind receipt must share the frozen config,
identify Devin, record at least three fresh sessions, pass its declared checks,
reach at least 99% decision and reason-code accuracy, and contain no malformed
outputs. Until then, the report remains visually and structurally blocked from
claiming a public model comparison.

### Difficulty calibration

“Hard” means the most difficult deterministic ruler Devin can solve reliably,
not the ruler that produces the most dramatic family-condition result.

1. Run only the clean condition against Devin for five 40-claim workdays.
2. Require at least 99% decision accuracy, at least 99% valid JSON, and no
   consistently failed claim.
3. If Devin is perfect with obvious headroom, create a new candidate task-bank
   revision with more compositional policy cases and independently verify every
   oracle answer. Do not alter family scenarios.
4. If Devin misses a claim repeatedly, distinguish real difficulty from
   ambiguity. Remove or clarify ambiguous claims; retain difficult unambiguous
   claims.
5. Freeze the winning task-bank and config hashes before running any family
   condition. Never tune task difficulty after seeing those outcomes.

`pilot-v1` established that the basic decisions were too easy and that its
unpublished reason-code vocabulary made exact reason grading unknowable. The
revised `pilot-v2` prompt publishes the complete output vocabulary and adds
deterministic precedence, caps, modifiers, per-night arithmetic, and review
bands without changing the family scenarios.

Three independent blind Devin GLM-5.2 sessions then produced byte-identical
answers: 120/120 correct decisions, 120/120 exact reason codes, 15/15 edge
cases, and zero malformed outputs. That is the frozen practical ceiling for the
pilot. The ceiling receipt is
[`calibrations/devin-glm-5.2-pilot-v2.json`](calibrations/devin-glm-5.2-pilot-v2.json).

The next deterministic level added foreign-currency receipt reconciliation,
half-up integer conversion, tip eligibility, personal-share exclusion, and
receipt-total guards. Across three valid blind sessions, Devin scored 40/40,
38/40, and 34/40 decisions (112/120, 93.3% aggregate), with reason-code scores
of 40/40, 38/40, and 33/40 (111/120, 92.5% aggregate). Two sessions therefore
failed the 99% reliability gate. All valid outputs used the exact schema; the
errors were policy/arithmetic errors rather than formatting failures.

This pinned the one-shot boundary: `pilot-v2` passed batched blind sessions and
`pilot-v3` was the first reproducibly failing challenge tier. The later
sequential workday validation showed that `pilot-v2` is not yet reliable in the
actual integrated-context flow. One output-truncated attempt and one prompt with omitted
literal field names are retained but excluded from the decision. See the
[machine-readable saturation receipt](calibrations/devin-glm-5.2-saturation-v1.json)
and the [publication-ready boundary report](results/devin-saturation-boundary-2026-08-20.md).

The next gate is a recalibrated clean-only task-bank revision followed by five
fresh sequential Devin workdays. Qwen must not start unless that clean baseline
qualifies.

Target-endpoint preflight exposed two transport-only compatibility issues. LM
Studio 0.4.21 rejects the legacy `json_object` hint, so the config switched to
an equivalent strict `json_schema` request before inference. A subsequent
diagnostic run returned 200 empty visible outputs because Qwen's default
reasoning mode consumed the bounded completion; those turns are retained
locally but excluded from research results. The final config sends
`reasoning_effort: none`, which a live schema probe verified with zero reasoning
tokens. The receipt records every config hash; the system prompt, claims,
expected answers, scenarios, and Devin calibration outputs did not change.

## Qualification and honesty rules

Confirmatory interpretation remains blocked unless:

- at least five paired clean days exist;
- exactly forty tasks ran in every measured workday;
- clean decision accuracy is at least 98%;
- clean valid JSON is at least 99%;
- every clean day completes;
- every clean day has server-reported prompt-token usage.
- model-file hash, quantization, server version, and endpoint model identity are
  recorded.

The runner also computes a conservative UTF-8-byte upper bound before every
request and refuses the call if that bound reaches the configured context
safety limit. Missing server token usage does not stop exploratory execution,
but it marks context integrity unverified and fails qualification.

Local servers may ignore a sampling seed even when they accept the field. The
stored server name, version, model identity, quantization, model-file hash,
prompt/config hashes, and repeated paired days are therefore essential
provenance rather than proof of perfect bit-level determinism.

Before any public small-model comparison, a trusted frontier or incumbent must
also reach the frozen 99% ceiling gate. Fragile or ambiguous claims require a
new task-bank revision; do not edit the ruler after inspecting confirmatory
family-condition outcomes.

Only visible response content is retained. The runner neither requests nor
stores private hidden chain-of-thought fields.
