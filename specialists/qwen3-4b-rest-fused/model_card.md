---
base_model: Qwen/Qwen3-4B-Instruct-2507
language:
  - en
library_name: mlx
license: other
pipeline_tag: text-generation
tags:
  - posttrainllm
  - mlx
  - tool-calling
  - function-calling
  - agentic
  - rest
---

# Qwen3-4B ReST Fused

## Summary

This package preserves the best measured Qwen3-4B agentic candidate produced by
posttrainllm's teacher-free ReST loop. One ReST iteration recovered the
out-of-domain breadth lost by narrow distillation while retaining the saturated
file-operations gate.

It is a **research specialist package**, not the default Pace planner. The model
speaks BFCL/OpenAI-style tool calls; Pace uses a different intent envelope and
requires its own ship gate.

## Artifact

- Package id: `qwen3-4b-rest-fused`
- Public artifact: `posttrainllm/qwen3-4b-rest-fused`
- Format: fused bf16 HF/MLX safetensors directory
- Base: `Qwen/Qwen3-4B-Instruct-2507`
- Training method: teacher-free ReST iteration over checker-passing,
  interleaved trajectories plus a file-ops depth anchor

## Recorded Result

| Suite | Stock 4B | ReST 4B |
|---|---:|---:|
| File-ops hard gate | 58% | 100% |
| Out-of-domain breadth | 59.6% | 65% |

The breadth suite contains 52 held-out TradingBot, VehicleControlAPI, and
TravelAPI tasks. The depth suite contains 12 file-ops tasks. These are the
historical run results recorded on 2026-06-17; the raw timing and trace logs
were not preserved, so this package does not claim current latency, RAM, tok/s,
or exact qualitative failure counts.

## Recommended Use

Use this artifact for Mac-local tool-calling research or as a candidate behind
an explicit agentic router. Keep a product-specific baseline and ship gate in
front of any downstream promotion.

Do not wire it into Pace by model name alone. Re-distill and evaluate on Pace's
intent envelope before considering that change.

## Known Limits

- The breadth suite is directly comparable to stock but was not
  frontier-ceiling validated.
- The historical report records rounded breadth accuracy; raw predictions are
  unavailable for a new trace review.
- Latency, RAM, tok/s, and training duration were not preserved.
- The evaluated backends do not prove broad general-agent capability.
- The artifact is multi-GB and lives on Hugging Face, not in git.

## References

- `docs/sessions/2026-06-17-stepback-inventory-roi.md`
- `docs/learn/tool-calling-frontier-parity.md`
- `specialists/qwen3-4b-rest-fused/eval_report.json`
