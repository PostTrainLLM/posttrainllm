---
title: "PRD — Wire ScaleBench (extractive-compression eval) into a `posttrainllm eval-*` subcommand"
---

# PRD — Wire ScaleBench (extractive-compression eval) into a `posttrainllm eval-*` subcommand

## Goal

Ship `posttrainllm eval-scaledown <model>` that runs the official
ScaleBench harness against a posttrainllm-loaded model and emits results
in the shared E0 `EvalCompare.Row` schema. B25 specialist needs
this for its ship gate; this PRD unblocks B25.

Half-day. Subprocess-via-serve pattern is established by E1/E2.

## Why now

- B25 is filed (`B25-scaledown-specialist.md`). Its ship gate is
  "ScaleBench downstream F1/EM"; without E6 there's no way to
  measure.
- ScaleBench source is public on the
  [challenge GitHub](https://github.com/scaledown-ai/scaledown).
  Their harness already accepts an OpenAI-compatible endpoint —
  most of the work is reformatting their output JSON into our E0
  schema.

## Scope — in

- `Sources/TinyGPT/EvalScaledown.swift` — boots `posttrainllm serve`,
  invokes the ScaleBench harness via subprocess with the
  OpenAI-compatible base URL, parses the score JSON, emits
  E0 `Row`s.
- `posttrainllm eval-scaledown <model.tinygpt> [--lora <a.lora>]
  --out scaledown.jsonl`
- Default test set: ScaleBench's main split. Override via
  `--split <name>`.
- Row schema: `task=scaledown`, `subtask=<config-name>`, `metric=f1`
  / `metric=em`, plus the auxiliary metrics (compression-ratio,
  preserved-rouge) in `extra`.

## Scope — out

- **In-house scoring** that bypasses their harness. We use theirs
  to keep the comparison apples-to-apples with the public
  leaderboard.
- **Streaming inference** — V1 calls non-streaming chat completions
  for simplicity.

## Files to touch

| File | Change |
|---|---|
| `Sources/TinyGPT/EvalScaledown.swift` | new — wrapper |
| `Sources/TinyGPT/TinyGPT.swift` | `case "eval-scaledown"` |
| `scripts/install-scalebench.sh` | new — one-time installer for the ScaleBench Python harness into the standard `_external/` location |
| `docs/PLAN.md` | E6 ⬜ → ✅ on ship |

## Acceptance criteria

- [ ] `posttrainllm eval-scaledown qwen3-4b-instruct-2507 --limit 100
  --out /tmp/sd.jsonl` runs end-to-end against a serve subprocess.
- [ ] Output JSONL conforms to `EvalCompare.Row`; `posttrainllm
  eval-compare /tmp/sd.jsonl` renders cleanly.
- [ ] Returns within 5% of the published leaderboard score on
  qwen3-4b 0-shot (sanity).

## Reference patterns

- `Sources/TinyGPT/EvalBFCL.swift` — the closest template (subprocess
  + JSON parse + E0 row emit).
- `docs/recipes/b25-scaledown.md` — the training-side companion
  recipe; both reference this harness.

## Open questions

- ScaleBench's repo layout vs our `_external/` convention.
  **Recommendation:** install at
  `~/.cache/posttrainllm/datasets/_external/scalebench` mirroring
  BFCL/τ-bench.
