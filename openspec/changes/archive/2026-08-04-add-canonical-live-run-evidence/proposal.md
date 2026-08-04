## Why

posttrainllm has a canonical factory-run schema, durable lifecycle metadata,
and a generic assembler, but live training and evaluation commands still leave
operators to translate their outputs into run fragments by hand. That manual
bridge is the last structural gap before benchmark and specialist work can
produce comparable evidence by default.

The integration must remain honest: commands can record what they directly
measured, but they cannot infer the owner goal, held-out identity, decision, or
publication authority. Those inputs must already be frozen in the run folder.

## What Changes

- Add an opt-in `--factory-run <directory>` integration to `sft`, `eval-gate`,
  and `eval-compare`.
- Require a valid lifecycle-managed run with matching `config.json` and
  `dataset.json` before a command writes evidence.
- Have `sft` record a bounded training summary, elapsed time, and unshipped
  adapter artifact, then advance the lifecycle only after those files validate.
- Have `eval-gate` record canonical `eval-baseline.json` and
  `eval-candidate.json` fragments from its evaluated primary suite, then
  advance the lifecycle only after both validate.
- Have `eval-compare` derive deterministic `slice-metrics.json` from the same
  E0 rows without changing lifecycle outcome state.
- Add pure, no-model tests for phase enforcement, atomic writes, repeat safety,
  and invalid evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `factory-run-lifecycle`: Live command boundaries emit and validate canonical
  evidence before advancing durable run state.

## Impact

The change touches the Swift CLI and pure `TinyGPTIO` factory-run support. The
new behavior is opt-in; existing invocations and output locations remain
unchanged. It adds no production dependency and performs no training, model
loading, network call, publication, or deployment during its tests.

GitHub issue: [#69](https://github.com/PostTrainLLM/posttrainllm/issues/69).
