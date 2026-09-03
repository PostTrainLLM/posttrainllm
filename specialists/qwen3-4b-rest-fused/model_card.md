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

## Fresh Requalification Result

| Suite | Stock 4B | ReST 4B |
|---|---:|---:|
| File-ops hard gate | 9/12 | 12/12 |
| Frontier-qualified breadth | 30/45 | 25/45 |
| Unexpected depth side effects | 8 | 0 |
| Depth wall time | 360.50s | 148.91s |
| Depth decode | 12.10 tok/s | 13.40 tok/s |
| Depth peak RSS | 6.77GB | 8.13GB |

The 2026-09-03 paired run used a 12-case file-ops depth gate and a 45-case BFCL
breadth gate whose frontier ceiling scored 44/45. The candidate won depth,
safety, and wall-clock speed, but lost breadth by 11.1 percentage points. The
frozen general-successor decision is therefore reject; the package remains a
file-ops-only routed specialist. Raw traces remain local and gitignored, while
their hashes are preserved in the tracked result.

## Recommended Use

Use this artifact for Mac-local tool-calling research or as a candidate behind
an explicit agentic router. Keep a product-specific baseline and ship gate in
front of any downstream promotion.

Do not wire it into Pace by model name alone. Re-distill and evaluate on Pace's
intent envelope before considering that change.

## Known Limits

- The fresh breadth suite passed frontier-ceiling calibration but the candidate
  regressed against stock, so it must not be presented as breadth recovery.
- Raw prediction traces are local and gitignored; the tracked result preserves
  their SHA-256 receipts.
- Training duration and normalized per-request latency were not measured.
- The evaluated backends do not prove broad general-agent capability.
- The artifact is multi-GB and lives on Hugging Face, not in git.

## References

- `docs/sessions/2026-06-17-stepback-inventory-roi.md`
- `docs/learn/tool-calling-frontier-parity.md`
- `evals/verified-wins/rest-requalification-result-v1.json`
- `specialists/qwen3-4b-rest-fused/eval_report.json`
