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

The no-model pilot artifact is implemented. It includes frozen contracts, a
40-claim policy-checked bank, deterministic paired schedules, a local
OpenAI-compatible runner, transactional SQLite resumption, strict one-shot
grading, JSONL export, workday-clustered analysis, hermetic tests, and a
self-contained publication report.

Open the committed [synthetic method preview](report-preview.html) to inspect
the complete report without loading a model. It is prominently labeled as
fixture evidence and must not be cited as an experimental result.

No Qwen 27B run or research result is committed. The bounded model workload is
a separately approved step after the artifact passes its no-model checks and a
local endpoint is ready.

## Control design

The passive filler arm deliberately receives no model response. Its note enters
the transcript as an incoming user message, then the next claim follows. This
is the token-volume control.

Neutral, benign, moderate, and crisis events all require the same two-field
action response and share paired event positions, scenario-variant indices,
and approximate word budgets. Those are the response-required controls.

This resolves an otherwise impossible requirement: filler cannot both isolate
passive context volume and add the same generated response turn as an
interruption. Accordingly, `neutral - filler` is labeled descriptive rather
than perfectly isolated. The primary matched family comparisons are:

```text
benign - neutral
moderate - benign
crisis - benign
```

## Artifact layout

| Path | Purpose |
| --- | --- |
| `configs/offhours/pilot-v1.json` | Fixed employee prompt, policy, model defaults, conditions, gates, and analysis plan |
| `configs/offhours/claims-pilot-v1.json` | Forty deterministic claims and reviewed expected answers |
| `configs/offhours/scenarios-pilot-v1.json` | Three four-event wording arcs for every non-clean condition |
| `scripts/offhours.py` | `validate`, `plan`, `run`, `status`, `analyze`, and `export` CLI |
| `scripts/offhours_core.py` | Policy oracle, validators, paired scheduler, strict parsers, and local endpoint client |
| `scripts/offhours_store.py` | SQLite schema, per-turn transactions, fail-closed context checks, resume, and JSONL export |
| `scripts/offhours_analysis.py` | Paired workday bootstrap, recovery bands, behavior metrics, task fragility, and reports |
| `scripts/offhours_report.py` | Self-contained accessible HTML report with inline SVG charts and print styles |
| `scripts/render_offhours_fixture_report.py` | Deterministically regenerates or checks the committed synthetic method preview |
| `tests/test_offhours.py` | Hermetic contract, runner, interruption, context-limit, export, and null-report tests |
| `benchmark-runs/offhours/` | Ignored local databases, transcripts, exports, and reports |

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
python3 scripts/offhours.py plan --days 5 --tasks-per-day 40 --seed 42
```

## Run the pilot

Start an OpenAI-compatible local endpoint first. Then record the real model and
server identity rather than relying on the placeholder configuration:

```bash
python3 scripts/offhours.py run \
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
python3 scripts/offhours.py run --api-key-env OFFHOURS_API_KEY ...
```

The key value is sent only in the request header. It is not written to SQLite,
JSONL, provenance, or reports.

### Resume

Supply the same database and run identifier. Completed turns are never called
again:

```bash
python3 scripts/offhours.py status \
  --db benchmark-runs/offhours/offhours.sqlite \
  --run-id '<run-id>'

python3 scripts/offhours.py run \
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
python3 scripts/offhours.py analyze \
  --run-id '<run-id>' \
  --json-out benchmark-runs/offhours/report.json \
  --markdown-out benchmark-runs/offhours/report.md \
  --html-out benchmark-runs/offhours/report.html

python3 scripts/offhours.py export \
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

Before publishing a smaller-model comparison, run the same frozen ruler with
Devin as the ceiling calibrator and retain its report. Attach that receipt when
analyzing the candidate:

```bash
python3 scripts/offhours.py analyze \
  --run-id '<candidate-run-id>' \
  --ceiling-report benchmark-runs/offhours/devin-ceiling.json \
  --json-out benchmark-runs/offhours/candidate-report.json \
  --markdown-out benchmark-runs/offhours/candidate-report.md \
  --html-out benchmark-runs/offhours/candidate-report.html
```

The ceiling report must share the frozen config, identify Devin in its model
provenance, be a measured rather than fixture run, pass baseline qualification,
and reach at least 99% clean decision accuracy. Until then, the report remains
visually and structurally blocked from claiming a public model comparison.

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

The current `pilot-v1` bank is the executable starting ruler, not a claim that
maximum reliable Devin difficulty has already been reached. Ceiling calibration
may produce `pilot-v2`; the report always states the exact task-bank hash.

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
