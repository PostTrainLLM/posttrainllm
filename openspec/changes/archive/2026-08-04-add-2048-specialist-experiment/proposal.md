## Why

2048 is a compact long-horizon environment with an exact transition function,
automatic rewards, cheap synthetic trajectories, and no judge-model ambiguity.
It is therefore a strong first game-policy factory target for testing whether a
small Mac-local language-model specialist can beat a frozen larger general
language model under the same observation, action, and no-tools contract. The
specialist is intentionally tiny: 30–50 million parameters, with 50 million as
the hard eligibility ceiling.

The existing game-RL PRD has only an abstract environment skeleton. Starting
with deterministic 2048 supplies the missing reset/step/reward boundary and a
reproducible baseline before any owner-approved training or RL run.

## What Changes

- Add a dependency-free, deterministic 2048 environment with canonical move,
  merge, spawn, terminal-state, score, and seeded-reset behavior.
- Add reproducible random, greedy, and bounded-search diagnostics for engine
  validation and context; none is the learned-policy opponent or label source.
- Add a frozen larger-LLM opponent contract with identical board observations,
  legal actions, decoding constraints, and no search, tools, or code execution.
- Separate a strict raw-action track from a disclosed legal-action-constrained
  diagnostic so instruction compliance and game planning are not conflated.
- Add reproducible cloud-opponent adapters for pinned Codex, Claude Sonnet, and
  Claude Opus development anchors without silently treating mutable aliases as
  frozen identities.
- Use a compact character-serialized board for both models; add no visual model,
  screenshots, image encoder, or OCR path.
- Add a trajectory/data contract for serializing larger-LLM decisions into a
  four-action policy dataset without train/eval seed leakage.
- Add a paired-seed evaluation contract reporting score, maximum tile, 2048
  reach rate, invalid moves, decision latency, throughput, and uncertainty.
- Add a benchmark catalog and detail replay that publish prerecorded decisions,
  exact protocol limitations, and a local reproduction command while keeping
  development pilots distinct from frozen evidence.
- Add a candidate adapter boundary so a future 30–50M policy can be evaluated
  by the same harness without changing the environment or scorer.
- Keep training, long benchmark sweeps, GRPO, packaging, and public claims
  behind later owner approval and frozen-gate evidence.

## Capabilities

### New Capabilities

- `deterministic-2048-environment`: Canonical seeded 2048 state transitions,
  legal-action handling, trajectory recording, and verifiable rewards.
- `2048-policy-evaluation`: Same-seed larger-LLM and specialist evaluation with
  quality, reliability, latency, and capability-compression measurements.

### Modified Capabilities

None.

## Impact

- Adds a small Python reference environment and no-model tests under the
  repository's existing script/test surfaces.
- Adds local run artifacts and generated trajectories only under ignored
  `runs/` or `data/*.jsonl` paths; tracked fixtures stay small.
- Adds a compact, path-scrubbed replay artifact and two static benchmark pages
  to the existing browser site; deployment remains a separate action.
- Reuses the Mac-local specialist factory sequence
  `target -> data -> post-training -> eval -> package -> report` and the
  existing game-RL direction without modifying its archived skeleton first.
- Adds no production dependency, network requirement, Pace integration, or
  deployment behavior.
