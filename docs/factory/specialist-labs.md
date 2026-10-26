# Decision, forecasting and terminal specialist modes

These modes extend the existing `/playground` and share one local runtime.
Implementation and remaining work are tracked in
[Issue #210](https://github.com/PostTrainLLM/posttrainllm/issues/210).
All three have Python references and browser controls. Exported small terminal
models run entirely in this tab through WASM or WebGPU. Fixed-shape Timestral
artifacts have a separate browser WASM path.

## Install and start

Use the isolated environment; the root Python reference remains unchanged.

```sh
uv sync --project scripts/specialists --all-extras --frozen
pnpm --dir browser run build
```

Download public model files once. The runtime itself loads offline:

```sh
uv run --project scripts/specialists hf download mlx-community/Qwen3-1.7B-4bit --revision 3b1b1768f8f8cf8351c712464f906e86c2b8269e
uv run --project scripts/specialists hf download mistralai/Timestral-5M --revision bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f config.json model.safetensors LICENSE
uv run --project scripts/specialists python scripts/specialists/lab.py serve
```

Open `http://127.0.0.1:8765/playground#specialists` and select **Connect runtime**.
The hosted page does not silently contact a service on your computer. Private
inputs on the playground do not load the site's third-party telemetry.

Use **Decision**, **Forecast**, or **Terminal world**, choose an operation,
edit its example JSON, and run it. Outputs can be inspected and exported.
**Use trained artifact** loads a newly trained candidate for subsequent
predictions. It does not qualify that candidate or replace a frozen baseline.

### Guided workflow and saved runs

After connecting, **Base model** lists pinned Qwen3 MLX models and all four
Timestral sizes. Readiness checks installed packages, Apple Silicon compatibility
and cached files without loading a model or accessing the network. **Download
selected model** explicitly downloads its pinned public files from Hugging Face.
There are no automatic model downloads or paid API calls.

Open **Bring your own data** to import up to 800 KB of CSV, JSON or JSONL.
The preview shows five records. Decision CSV maps question, answer and option
columns; assigned labels are A, B, C, etc. Answers may name a column, assigned
label or unique option value. Canonical question/options/answer JSONL works too.
At least twenty distinct questions are required. Train, calibration, primary
and regression splits are deterministic and disjoint.

Forecast CSV maps an optional timestamp and numeric target columns. Timestamps
must increase strictly; otherwise supplied row order is chronological. Empty
cells mean missing observations. The last two horizons are held out for primary
and regression evaluation; training ends before either window. Guided imports
support numeric targets; covariates remain available in advanced JSON. Terminal
imports accept recorded episode JSON and remain experimental.

Choose **Train**, set 1–200 steps, and follow real loss/progress observations.
One owned subprocess runs at a time. **Cancel run** terminates that process group;
a parent watchdog enforces 180 seconds. This is not a hard RAM sandbox. Browser
reload does not cancel a job; reconnect to follow it. Stopping the runtime
cancels its owned process. Abandoned running records become interrupted on the
next startup; recorded stale PIDs are never signalled. Partial jobs cannot
activate their artifacts.

**Saved runs** retains recipes, source hashes, pinned base identities, losses,
results and artifacts under `runs/specialist-labs/web/`. Completed artifacts can
be selected after restarting. Restore setup starts no work until Run is clicked.
Use `serve --state-root <directory>` for an isolated workspace; one runtime may
own a workspace at a time.

After training, choose **Use trained artifact**, then **Compare trained model
with baseline**. Decision comparisons require **Validate benchmark with Codex**,
which explicitly sends held-out questions/choices through the free subscription
CLI; gold labels stay local. Receipts bind source and gold. Forecast comparisons
use two disjoint chronological windows and also report seasonal-naive error.
Both paths verify training-data/base identities and emit existing factory
report-card JSON/HTML. Missing measurements remain missing; comparisons are
report-only and cannot automatically ship a model.

Issue #210 records earlier pilots; neither candidate qualified for shipment.
The runtime accepts same-origin JSON only on `127.0.0.1`, serializes operations
and never executes generated commands. Models are operator-selected; it keeps
eight terminal sessions. No E2B/Tinker service is installed.

## Operator entry point

Every command below uses this prefix:

```sh
uv run --project scripts/specialists python scripts/specialists/lab.py
```

Append `decision`, `forecast`, `terminal`, or `serve`, followed by `--help`.
Outputs refuse existing destinations so earlier evidence is preserved.
Large weights and raw run output stay in ignored `checkpoints/` and `runs/`.

## Decision mode

The model performs one forward pass, takes the final-position logits for
allowed label tokens, and normalizes only those logits. Every label must map
to exactly one distinct token. Multi-token labels fail instead of being
silently truncated. Qwen thinking is disabled in the chat template.

Labeled rows use `id`, `question`, `options` and `answer`; see
`scripts/specialists/examples/decision.jsonl`.

Omit `answer` for prediction. Raw restricted softmax values are explicitly
uncalibrated; they are not probabilities that the answer is correct.

```sh
# Use a local model directory or a cached Hub id with its immutable revision.
uv run --project scripts/specialists python scripts/specialists/lab.py decision score --backend mlx --model mlx-community/Qwen3-1.7B-4bit --revision 3b1b1768f8f8cf8351c712464f906e86c2b8269e --data scripts/specialists/examples/decision.jsonl --out runs/decision/scores.jsonl
uv run --project scripts/specialists python scripts/specialists/lab.py decision predict --scores runs/decision/scores.jsonl --out runs/decision/predictions.jsonl
```

`prepare --data source.jsonl --out runs/decision/splits` freezes train,
calibration, test and regression sets. It requires at least twenty distinct
questions. Permuting option labels cannot disguise an identical question.

`train` supports PyTorch LoRA and MLX QLoRA. Select `--backend mlx` to reuse
the quantized Mac model. PyTorch training exports merged safetensors and a
tokenizer; MLX training exports standard adapters and an exact base identity.
Both record training identities, losses, step count and resource observations.

```sh
uv run --project scripts/specialists python scripts/specialists/lab.py decision train --backend mlx --model mlx-community/Qwen3-1.7B-4bit --revision 3b1b1768f8f8cf8351c712464f906e86c2b8269e --data runs/decision/splits/train.jsonl --steps 1 --out checkpoints/decision-candidate
```

Pass `--adapter checkpoints/decision-candidate` when scoring an MLX candidate.
An adapter's weights, configuration and base/tokenizer identity must match.
Changing the base or adapter invalidates an earlier temperature fit.

`calibrate --scores calibration-scores.jsonl --exclude train-scores.jsonl
test-scores.jsonl regression-scores.jsonl --out temperature.json` fits a
positive temperature by NLL, without modifying model weights or answer rank.
Training examples and overlapping calibration/test examples are rejected.

`eval --scores test-scores.jsonl --ceiling ceiling.json --calibration
temperature.json --baseline baseline-scores.jsonl --out report.json` reports
accuracy, NLL, multiclass Brier score, ten-bin ECE, coverage, selective accuracy,
and the paired baseline delta. An empty accepted set has null selective accuracy.

First run `ceiling --data test.jsonl --out runs/decision/ceiling` through the
free subscription Codex CLI. Gold answers stay out of its prompt. The receipt
must pass every frozen question and match question/gold and validator hashes.
A failed or stale ceiling blocks local accuracy reporting. A report alone is
not a ship decision; primary and regression gates must be frozen for a run.

## Forecast mode

This uses the actual upstream Timestral package, pinned in
`scripts/specialists/pyproject.toml` and its lockfile. The default is 5M;
`--model` can select the 28M, 123M or 209M checkpoint or a local adapted model.
Upstream code is Apache-2.0; model weights have a separate Modified MIT license.

Input rows use variates × time matrices. JSON null means missing. The optional
boolean `observation_mask` must match context. Every target needs an observation.

For example, `context: [[1, 2, null, 4, 5, 6]]` has one target and six steps;
`known_covariates: [[0,1,0,1,0,1,0,1,0,1]]` supplies ten known steps.

For a horizon of four, known covariates cover the six context steps plus all
four future steps. Past covariates cover only history. Both numeric and
categorical versions are supported: `past_covariates`, `known_covariates`,
`categorical_past_covariates`, and `categorical_known_covariates`.
Categorical codes retain float64 precision before upstream encoding.

```sh
uv run --project scripts/specialists python scripts/specialists/lab.py forecast predict --data input.jsonl --horizon 4 --out runs/forecast/predictions.jsonl
uv run --project scripts/specialists python scripts/specialists/lab.py forecast synthetic --seed 7 --length 128 --out runs/forecast/series.jsonl
uv run --project scripts/specialists python scripts/specialists/lab.py forecast backtest --data runs/forecast/series.jsonl --origins 80 104 --horizon 24 --season 24 --out runs/forecast/backtest.json
```

Outputs contain ordered finite quantiles, their levels, the median and input/
model identities. Backtests slice targets strictly at each chronological origin,
compare seasonal naive MAE, and report pinball loss. This numeric backtest is not
a frontier-capability accuracy benchmark or a public leaderboard reproduction.

For adaptation, add `target` with variates × horizon labels and run `train
--data training.jsonl --steps 1 --out checkpoints/forecast-candidate`.
Training uses upstream inference preprocessing and a differentiable single
forecast block with masked pinball loss. Future target labels never enter the
model context. The result reloads through the standard Timestral loader.
This implements local adaptation, not Mistral's proprietary Forge pipeline.

## Terminal world mode

The independent terminal reference uses 333 tokens: byte values, row ids, and
screen/input/output/copy/cursor delimiters. Screens are monochrome printable
ASCII, at most 64 rows × 255 columns. A checkpoint's context may impose a much
smaller practical size. Custom starting screens and raw key sequences work.

`COPY` reads the previous frame atomically. Grammar-constrained decoding cannot
write outside a row, repeat a row, or return an incomplete cursor update.
Wait events carry milliseconds, allowing learned time-dependent updates.

```sh
uv run --project scripts/specialists python scripts/specialists/lab.py terminal recipe --seed 7 --memory --out runs/terminal/recipe.json
uv run --project scripts/specialists python scripts/specialists/lab.py terminal record --recipe runs/terminal/recipe.json --image YOUR_LOCAL_SHELL_IMAGE --out runs/terminal/train.jsonl
uv run --project scripts/specialists python scripts/specialists/lab.py terminal train --data runs/terminal/train.jsonl --steps 1 --out checkpoints/terminal-candidate
```

Recording executes supplied recipes in a disposable local image with `/bin/sh`,
without network, mounts, pulls or privileges. Raw keys can drive installed
programs. Quiescence is a sampling policy, not a completion oracle.

The model has no shell or filesystem. Only the recorder invokes real programs.
Training is output-masked causal SFT with alternating independent-row attention.
Recoverable-error examples can be added with `--corrections predictions.jsonl`;
repairs introducing words absent from earlier real screens or typing are rejected.

Prediction supports `--parallel`: batch one draft per row, then verify against
the same model's full causal distribution. The verifier corrects disagreements;
its output matches sequential greedy decoding. No Mac speedup is claimed yet.
Context overflow explicitly rebases to the current screen and reports a reset,
which may lose off-screen memory. No hidden filesystem fills that memory gap.

`ceiling` and `eval` bind real-oracle episodes to the frontier-ceiling gate.
Closed-loop evaluation reports screen/cursor/cell agreement, exact memory
readbacks, latency and token throughput. It never feeds later oracle screens
back into the model. Repeated typing overfit is a separate correctness gate.

The tiny architecture is `configs/model.terminal-tiny-v1.json`, independently
trained; tiny overfit does not establish vim, tmux, snake or file competence.

## Verification and remaining work

```sh
uv run --project scripts/specialists pytest tests/test_specialist_labs.py tests/test_specialist_workflow.py tests/test_specialist_terminal_portability.py tests/test_specialist_native_export.py -q
uv run --project scripts/specialists ruff check scripts/specialists tests/test_specialist_labs.py tests/test_specialist_workflow.py
pnpm --dir browser run typecheck
```

Defaults cap PyTorch CPU threads at two. CLI work has a cooperative wall-time
budget; it is not a hard process/RAM sandbox. Browser training is limited to
1–200 steps; background jobs have a 180-second parent watchdog. Peak RSS is process-wide, not isolated model RAM;
MLX GPU memory is recorded separately when training. There is no paid API use.

Decision MLX adapters can be converted to native TGLA packages with the command
below. Forecast checkpoints can be exported for fixed-shape browser WASM
inference. Useful terminal quality, broader capability/regression runs,
Qwen has a separate portable float32 WASM path below; Timestral WebGPU remains unfinished. These references do not establish upstream feature/quality
parity.

## Portable terminal inference

Export a local terminal checkpoint without changing it:

```sh
uv run --project scripts/specialists python scripts/specialists/terminal.py export --model <checkpoint-directory> --dtype f32 --out <new-browser-artifact.json>
```

`--dtype f16` halves the stored weight payload; runtimes expand it to f32.
In **Terminal world**, open **Terminal execution**, choose WASM or WebGPU,
select the artifact and click **Load & verify**. Three source-bound Python
logit probes must pass before prediction becomes available. The artifact stays
local; this path makes no specialist API request. **Stop browser terminal**
terminates the owned worker. Provider, artifact and session changes invalidate
queued inputs and stale responses.

The export uses the existing pre-LayerNorm/GELU GPT kernels, preserving all 333
codec token IDs, including values above 255. COPY reads the previous screen
atomically. Sequential constrained decoding supports custom screens, raw keys
and waits; training, evaluation and verified parallel drafting use Python.
Parameter and activation estimates are checked before runtime allocation:
maximum five million parameters, 128 MiB for one attention matrix and 256 MiB
estimated tensor allocations. These are admission bounds, not a total process
RAM measurement; encoded files, import buffers, browser and WASM heap overhead
are additional. No browser RAM or general speedup claim is made.

A tiny typing model passed f32/f16 probes and one matching screen in actual
WASM and Apple Metal WebGPU: maximum errors 0.000010 and 0.00831, respectively.
This establishes bounded portability, not all-input equivalence or capability.
Unknown training provenance blocks qualification; changing episode IDs/metadata
cannot disguise training replays. Recorder episodes bind immutable image IDs
and public initial conditions. Eval reports whole-world/per-family successes.

## Portable forecast inference

Install the optional browser export dependencies, then compile one example's
input shape. No model is downloaded unless `--download` is explicitly passed.

```sh
uv sync --project scripts/specialists --all-extras --frozen
uv run --project scripts/specialists python scripts/specialists/lab.py forecast export-browser --model mistralai/Timestral-5M --revision bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f --data example.jsonl --horizon 24 --out checkpoints/forecast-browser
```

The one-row JSONL uses the existing forecast input schema. Targets, history
length, horizon and each covariate count become an explicit artifact contract;
export another shape when they change. Missing observations, numeric/categorical
past and known-future covariates, reflected averaging, clipping, quantile caps
and advancing-block refinement retain the pinned Python semantics. Category
means use observed history only; category identities retain float64 precision.

In **Forecast**, open **Forecast execution**, select WASM, and load the exported
`manifest.json` and `model.onnx`. The worker checks the model checksum and three
Python numerical probes before activation. **Use artifact example** loads the
matching input without contacting the local API. Prediction inputs must match
the artifact shape. **Stop browser forecast**, replacing files, or changing the
provider terminates the owned worker and invalidates pending replies.

Models are limited to 1 GiB and manifests to 64 MiB. Each worker operation has a
45-second cancellation deadline; these are admission limits, not measured peak
browser RAM. Runtime assets load from the site's own origin only when requested.
Exports refuse an existing output directory. Failed exports may retain partial
files, but do not write an activation manifest. Keep manifests private if the
example contains private data. Numerical portability does not qualify a model.
Timestral WebGPU execution remains unfinished. Qwen WASM uses the separate arithmetic identity described below.

## Native decision adapter bridge

```sh
uv run --project scripts/specialists python scripts/specialists/decision.py export-native --base <matching-local-mlx-base> --adapter <trained-decision-directory> --out <new-adapter.lora>
posttrainllm debug-logits --hf <matching-local-mlx-base> --lora <new-adapter.lora> --probe <exact-token-probe.json>
```

The converter admits ordinary Q/V LoRA on the declared last layers, verifies
base/tokenizer and adapter/config hashes, preserves MLX scaling and writes a
provenance sidecar. The probe JSON contains `tokens` (1–256 token IDs) and
`labels` (up to 26 token IDs). This diagnostic verifies the sidecar against the
actual base before one forward pass. Other existing native adapter commands
check architecture, not the sidecar; keep the exact matching base.

Native import now uses named projections, supports subset layers, rejects
malformed adapters before mutation and preserves packed quantized base kernels.
HF RMS/QK norm epsilon follows the source config. From-scratch checkpoint norm
defaults remain unchanged. Dense effective-weight snapshots increase memory
for adapted projections. Stacked/baked packed adapters are outside this bridge.

The actual Qwen3-1.7B adapter loaded and selected the same option on one
44-token probe. Source bf16 and native fp32 selected logits differed by 0.643;
a Python fp32 comparison reduced that to 0.0678. This is execution compatibility,
not numerical or calibration parity. Refit temperature and rerun primary and
regression gates before using native confidence. No model is promoted by this
conversion.

## Portable Qwen decisions

Use a local tied-embedding Qwen3 MLX affine q4/group64 base and, optionally,
an identity-checked ordinary q/v LoRA adapter. Export with the existing decision,
forecast and browser extras installed; this command never downloads models:

```sh
uv run --project scripts/specialists python scripts/specialists/lab.py decision export-browser --base <local-base> --adapter <adapter-directory> --data example.jsonl --out <new-directory>
```

The JSONL contains one decision example. The exporter uses the maintained
Transformers Qwen3 body, retains packed affine weights through ONNX Runtime's
MatMulNBits plus a group-sum bias correction, and verifies three selected-logit
probes against its Python float32 reference. No full-vocabulary generation or
sampling substitutes for option scoring. Unknown adapters/keys, wrong base or
configuration hashes, and failed parity cannot produce an admitted manifest.

In **Decision execution**, choose WASM and select all five exported files.
Checksums, a distinct portable model identity, tokenizer/template vectors and
three full-model probes gate activation. All files and prompts stay in the tab.
The maintained tokenizer package loads only in the owned worker. Stop, file or
provider changes, mode changes and page teardown terminate that worker; requests
have a 45-second deadline. The default limit is 256 prompt tokens; export may
set 64–512. Inputs above that explicit limit are rejected without truncation.
Labels must encode as distinct single tokens. Integer-index labels are rejected
because JavaScript would reorder them; use A, B, C. Only prediction is enabled;
training and qualification remain local Python workflows.

Portable float32 arithmetic is **not original MLX BF16 arithmetic**. The model
identity is separate and original calibration is rejected. Probabilities and
threshold abstention are uncalibrated; no quality or confidence qualification is
implied. Export preserves source identity and adapter checksums, but same option
selection alone never establishes calibration equivalence. WebGPU is not exposed.
A retained 1.7B model/adapter ran in Chrome WASM with roughly 5 GiB process-tree
RSS in the bounded wiring probe; this is not a general memory/latency guarantee.
