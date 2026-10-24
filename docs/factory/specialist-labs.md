# Decision, forecasting and terminal specialist modes

These modes extend the existing `/playground` and share one local runtime.
Implementation and remaining work are tracked in
[Issue #210](https://github.com/PostTrainLLM/posttrainllm/issues/210).
They are Python references with browser controls, not browser-only models.

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

The finishing check used four optimizer steps per model. Decision primary
changed from 6/6 to 5/6, with regression unchanged at 5/6. Timestral primary MAE
improved from 0.01742 to 0.01214 while regression MAE worsened from 0.03609 to
0.03626 (eight observations per slice). These are tiny synthetic results,
not general quality claims; neither candidate qualified for shipment.

Workflow patterns were reviewed against Transformer Lab, Silicon Studio,
LLaMA-Factory, AutoGluon, Orange and Ludwig. Feather's resolved experiment
conditions inspired source/config identity capture; its E2B/Tinker integration
is not installed. Existing MLX/Timestral trainers and factory report contracts
remain the implementation base; no new production dependency is added.

There are no bundled terminal weights. In Terminal world, select training and
run the repeated tiny typing example, then use its trained artifact. This
establishes the learning/checkpoint path, not useful shell competence.

The server binds only to `127.0.0.1`, accepts same-origin JSON, serves built
public assets, and serializes model operations. It never executes a generated
command. Model locations are selected by the operator; HTTP requests cannot
select arbitrary local files. Eight terminal sessions are retained in memory.

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

Example labeled dataset row:

```json
{
  "id": "even-1",
  "question": "Which integer is even?",
  "options": { "A": "3", "B": "8" },
  "answer": "B"
}
```

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

```json
{
  "id": "series-1",
  "context": [[1, 2, null, 4, 5, 6]],
  "known_covariates": [[0, 1, 0, 1, 0, 1, 0, 1, 0, 1]]
}
```

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

Recording executes the explicitly supplied recipe in a disposable container:
no network, host mounts, image pulls or privilege capabilities. The image must
already exist and contain `/bin/sh`. Recipes can drive installed vim, tmux,
Python or games through raw keys; the default recipe exercises file operations.
Output quiescence is a sampling policy, not an application-completion oracle.

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

The tiny architecture lives in `configs/model.terminal-tiny-v1.json`. These
weights and protocol are not WorldTUI weights. WorldTUI's article currently
describes downloadable training weights as forthcoming. A good tiny overfit
result does not establish vim, tmux, snake or persistent-file competence.

## Verification and remaining work

```sh
uv run --project scripts/specialists pytest tests/test_specialist_labs.py tests/test_specialist_workflow.py -q
uv run --project scripts/specialists ruff check scripts/specialists tests/test_specialist_labs.py tests/test_specialist_workflow.py
pnpm --dir browser run typecheck
```

Checks cover numerical calibration, split leakage, forecasting preprocessing,
pinball gradients, checkpoint reload, row-copy semantics, grammar bounds,
correction visibility and exact speculative verification. Focused browser
checks cover the unified modes, actual local inference and responsive layouts.

Defaults cap PyTorch CPU threads at two. CLI work has a cooperative wall-time
budget; it is not a hard process/RAM sandbox. Browser training is limited to
1–200 steps; background jobs have a 180-second parent watchdog. Peak RSS is process-wide, not isolated model RAM;
MLX GPU memory is recorded separately when training. There is no paid API use.

Python-only artifact formats are not yet native TinyGPT packages. Full terminal
training quality, broader frozen capability/regression runs, model compression,
and browser-only WASM/WebGPU execution remain unverified or unbuilt. Do not
present these references as feature/quality parity with the cited systems.
