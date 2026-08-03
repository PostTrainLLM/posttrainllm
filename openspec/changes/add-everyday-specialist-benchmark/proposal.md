## Why

posttrainllm can train, package, and report narrow specialists, and it already
has a deterministic tiny-model leaderboard. It does not yet have one fair
system-level benchmark where task-trained local specialists, general-purpose
models, and routed cascades solve the same everyday tasks under the same scorer
and resource accounting.

That gap makes the strongest existing proof—`pace-intent-router-v8`—harder to
communicate honestly: its specialist, Qwen, and Apple comparisons use synthetic
data and different sample counts. A versioned, frontier-calibrated,
execution-scored benchmark is needed before those comparisons become a public
headline or before a specialist capability graph can claim a system win.

## What Changes

- Define versioned suite, task, entry, run, result, routing, resource, and
  privacy-safe receipt contracts for an Everyday Specialist Benchmark.
- Establish three explicit tracks: zero/few-shot generalists, task-adapted
  models, and routed systems.
- Qualify tasks with deterministic or executable scorers, a frontier-ceiling
  gate, leakage checks, public development fixtures, and sealed official tests.
- Measure repeated-run reliability, primary and regression slices, false
  accepts, escalation behavior, route regret, warm/cold latency, RAM, energy,
  active parameters, and installed artifact bytes.
- Add a no-model runner/scorer path and deterministic static report so the
  benchmark infrastructure can be verified without training or loading models.
- Launch only after at least three everyday task families qualify and the Pace
  intent comparison is rerun on one shared sealed set.

## Capabilities

### New Capabilities

- `everyday-specialist-benchmark`: Fair, versioned, execution-scored comparison
  of generalists, adapted specialists, and routed systems on everyday tasks.

### Modified Capabilities

None. Existing factory evals, report cards, the browser tiny-model leaderboard,
and `decision.json` remain authoritative for their current scopes.

## Impact

The change adds benchmark schemas/configs, fixture scorers, a CLI or script
runner, privacy-safe result receipts, focused no-model tests, and a deterministic
report/publication input. It may read specialist package and capability-graph
metadata but does not train a model, call a paid provider automatically, load a
heavy checkpoint during infrastructure tests, change Pace production routing,
deploy the website, or replace factory-run decisions.

Planning detail: `docs/prds/everyday-specialist-benchmark.md`.
GitHub issue: [#77](https://github.com/PostTrainLLM/posttrainllm/issues/77).
