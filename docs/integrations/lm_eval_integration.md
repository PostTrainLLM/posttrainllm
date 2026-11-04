# lm-evaluation-harness integration for PostTrainLLM

Use a compatible local server with a task its adapter can score. This reference
checks source at PostTrainLLM `73da1aa1be9293cdbd75b825e0793fe786c65a5f`
and EleutherAI lm-evaluation-harness `0.4.10`, commit
`f7d0b116146bd616b59d0b991549120f197369a4`. The commands below are
source-declared examples, not a newly executed model evaluation. The version
pin is for reproducibility, not a latest-version or safety recommendation.

For the shorter task guide and retained report-card interpretation, start at
[Evaluate a local LLM](https://posttrainllm.com/evaluate-local-llm). A fresh model run in this
repository still follows the [fresh-experiment rule](https://posttrainllm.com/docs/NEXT/).

## Match task, endpoint and tokenizer

### Generation, such as `gsm8k` (`generate_until`)

`local-chat-completions`, `/v1/chat/completions`

Pass `--apply_chat_template`; confirm the model's prompt format and context budget.

### Likelihood scoring, such as HellaSwag or ARC

A suitable completion or native scoring backend

The chat adapter raises `NotImplementedError` for `loglikelihood`. A completion backend needs matching tokenization and prompt log probabilities.

PostTrainLLM's source exposes `/v1/models`, `/v1/chat/completions` and
`/v1/completions`. Its plain completion handler has a separate `logprobs` plus
`echo` scoring path. That source surface does not establish end-to-end
HellaSwag or ARC correctness for a chosen tokenizer, model or harness release.
Changing the URL alone does not qualify a likelihood evaluation.

The chat handler renders messages as ChatML-style text. Check that format
against the model's training contract. For another prompt format, choose a
compatible text-completion or native backend and validate the formatting.

Sources: the pinned [chat and completion adapters](https://github.com/EleutherAI/lm-evaluation-harness/blob/f7d0b116146bd616b59d0b991549120f197369a4/lm_eval/models/openai_completions.py),
[API interface guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/f7d0b116146bd616b59d0b991549120f197369a4/docs/API_guide.md),
and [PostTrainLLM server](https://github.com/PostTrainLLM/posttrainllm/blob/73da1aa1be9293cdbd75b825e0793fe786c65a5f/native-mac/Sources/TinyGPTServe/Serve.swift).

## Prepare an existing local server

Use an already built `posttrainllm` binary and a model already on disk.
[CONTRIBUTING.md](https://github.com/PostTrainLLM/posttrainllm/blob/73da1aa1be9293cdbd75b825e0793fe786c65a5f/CONTRIBUTING.md)
owns build prerequisites. The main CLI already dispatches `serve`; no dispatch
edit is required. Starting it loads the selected model:

```sh
posttrainllm serve /absolute/path/to/existing-model \
  --host 127.0.0.1 --port 8765
```

`--lora /path/to/adapter.lora` selects an adapter on the existing base.
`--max-context N` only caps context below the model's native limit; it cannot
increase the trained context capacity. Record every option used, the model
and adapter identities, tokenizer, binary revision and machine. Check readiness
from another terminal:

```sh
curl --fail --silent --show-error http://127.0.0.1:8765/v1/models
```

The PostTrainLLM model ID is `posttrainllm`. Use the advertised model ID when
pointing at another compatible server. Readiness establishes an HTTP response,
not correct generation or a benchmark result.

## Pin the harness and run a bounded generation smoke

Harness `0.4.10` requires Python 3.10 or newer. Its `api` extra supplies the
HTTP dependencies; see the pinned [package metadata](https://github.com/EleutherAI/lm-evaluation-harness/blob/f7d0b116146bd616b59d0b991549120f197369a4/pyproject.toml).

```sh
python3 -m venv .venv-lm-eval
source .venv-lm-eval/bin/activate
python3 -m pip install "lm-eval[api]==0.4.10"
```

The pinned [GSM8K definition](https://github.com/EleutherAI/lm-evaluation-harness/blob/f7d0b116146bd616b59d0b991549120f197369a4/lm_eval/tasks/gsm8k/gsm8k.yaml)
uses `generate_until` and normally requests five few-shot examples. This smoke
explicitly uses zero, limits the task to five examples and caps each response
at 128 generated tokens:

```sh
lm-eval --model local-chat-completions \
  --model_args "base_url=http://127.0.0.1:8765/v1/chat/completions,model=posttrainllm,tokenizer_backend=None,tokenized_requests=False,num_concurrent=1" \
  --tasks gsm8k --apply_chat_template \
  --num_fewshot 0 --limit 5 --batch_size 1 \
  --gen_kwargs "max_gen_toks=128,temperature=0.0" \
  --log_samples --output_path runs/quality-evals/gsm8k-local-smoke
```

Check prompt lengths with the model's own tokenizer before running. Every
prompt plus the output allowance must fit the native context. If any prompt
is truncated, the run cannot support a scored comparison. The harness may
download task data, and the command performs real inference. Five capped
examples check protocol and artifact flow; they do not establish a full
GSM8K score, baseline/candidate gain or performance budget. Preserve stop
conditions, incomplete answers, timeouts and missing measurements.

## Optional repository wrapper

`python_ref/lm_eval_tinygpt.py` can spawn the server, wait for `/v1/models`,
run the harness and stop its own server on exit. With an existing server, use
an explicit generation task and pass the chat/sample flags through:

```sh
python3 python_ref/lm_eval_tinygpt.py --skip-spawn \
  --base-url http://127.0.0.1:8765/v1/chat/completions \
  --tasks gsm8k --num-fewshot 0 --limit 5 --batch-size 1 \
  --output-path runs/quality-evals/gsm8k-local-smoke \
  --lm-eval-extra "--apply_chat_template --log_samples --gen_kwargs max_gen_toks=128,temperature=0.0"
```

The wrapper always selects `local-chat-completions`. Its default tasks, and
the defaults in `evals/run_quality_evals.sh`, are HellaSwag and ARC-Easy.
Those defaults request unsupported likelihood scoring through this chat
adapter. Do not use them as a working recipe; choose the explicit generation
path above. The wrapper accepts a model path, `--posttrainllm-bin`, `--port`
and `--max-context` when spawning. Its compatibility smoke-target fallback
is not evidence about the current installed binary.

## Keep and inspect raw artifacts

For model ID `posttrainllm`, harness `0.4.10` writes beneath
`runs/quality-evals/gsm8k-local-smoke/posttrainllm/`:

- `results_<timestamp>.json` contains aggregate metrics and configuration.
- `samples_gsm8k_<timestamp>.jsonl` contains raw responses and filtered answers
  when `--log_samples` is set.

See the pinned [output writer](https://github.com/EleutherAI/lm-evaluation-harness/blob/f7d0b116146bd616b59d0b991549120f197369a4/lm_eval/loggers/evaluation_tracker.py).
The wrapper's final summary search checks only the top output directory.
Its `no results_*.json found` message can therefore miss the model subdirectory;
inspect the files and the harness exit status before concluding that no
results were written.

Raw harness JSON and JSONL are not the site's fine-tune report-card schema.
The offline `check_fine_tune_report_card.py` validator does not convert these
files, run a model or prove a score. A canonical factory report needs its own
provenance, paired target/regression gates, measurement states and decision;
see [the report-card contract](https://posttrainllm.com/docs/factory/report-card/).

## Interpret failures before interpreting scores

- Readiness or connection failure: check the process, bind host, port and URL.
- A message-list assertion: include `--apply_chat_template` and use the full
  chat-completions URL.
- `loglikelihood` not implemented: the task and adapter do not match. Choose a
  suitable scoring backend with matching tokenizer and log-probability support.
- Truncated prompts or incomplete generations: preserve the failure and the
  context/output limits. Do not compare the result with an uncapped full run.
- Missing artifacts or a nonzero harness exit: inspect server/harness logs.
  Missing scores remain missing, not zero.

Freeze the full target and regression suite, dataset revision, prompts,
decoding settings and acceptance thresholds before a paired comparison.
Record latency, RAM and throughput only when measured under that protocol.
No wall-clock estimate or expected model score is qualified by this recipe.

## Retained HTTP smoke evidence

The historical documentation retained these responses from the separate
`posttrainllm-serve-smoke` executable and a 27M checkpoint. They show the recorded
HTTP response shapes and stop behavior. They do not qualify the current main
binary, model quality or a completed lm-eval run.

```text
$ curl -s http://127.0.0.1:8765/v1/models
{"object":"list","data":[{"object":"model","id":"posttrainllm","owned_by":"posttrainllm"}]}

$ curl -s -X POST http://127.0.0.1:8765/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"posttrainllm","messages":[{"role":"user","content":"Once upon a time"}],"max_tokens":10,"temperature":0.0}'
{"id":"chatcmpl-...","object":"chat.completion",
 "choices":[{"message":{"role":"assistant","content":"The first step in the process is to make a"},
             "finish_reason":"stop","index":0}],
 "model":"posttrainllm","created":...,
 "usage":{"prompt_tokens":13,"completion_tokens":10,"total_tokens":23}}

$ curl -s -X POST http://127.0.0.1:8765/v1/completions \
    -H "Content-Type: application/json" \
    -d '{"prompt":"Once upon a time","max_tokens":15,"temperature":0.0}'
{"object":"text_completion",
 "choices":[{"text":" of time, the time of time is not always a matter of time.",
             "finish_reason":"stop","index":0}],
 "usage":{"prompt_tokens":4,"completion_tokens":15,"total_tokens":19}}

# Stop sequence smoke — generation cuts off before "time" appears.
$ curl -s -X POST http://127.0.0.1:8765/v1/completions \
    -H "Content-Type: application/json" \
    -d '{"prompt":"A","max_tokens":50,"stop":["time"],"temperature":0.0}'
{"object":"text_completion",
 "choices":[{"text":". 1998.\n- \"The first ", "finish_reason":"stop", …}], …}
```

## Source files

- `native-mac/Sources/TinyGPT/TinyGPT.swift`: main `serve` dispatch.
- `native-mac/Sources/TinyGPTServe/Serve.swift`: HTTP handlers, chat formatting
  and completion scoring.
- `python_ref/lm_eval_tinygpt.py`: spawn/reuse and argument forwarding.
- `evals/run_quality_evals.sh`: retained driver with incompatible chat-task
  defaults described above.

For the benchmark landscape and contamination discussion, use the retained
[benchmark research](https://posttrainllm.com/docs/research/quality_benchmarks_may_2026/). Historical
research claims do not substitute for qualification on a chosen runtime.
