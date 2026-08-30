---
base_model: Qwen/Qwen3-4B-Instruct-2507
language:
  - en
library_name: transformers
license: other
pipeline_tag: text-generation
tags:
  - posttrainllm
  - mlx
  - tool-calling
  - function-calling
  - agentic
  - file-ops
---

# Qwen3-4B File-Ops Distilled

## Summary

This is the first posttrainllm specialist package for a model we actually built:
a fused Qwen3-4B-Instruct-2507 bf16 HF/MLX safetensors directory distilled for
GorillaFileSystem multi-turn file-operation tasks.

It is a **routed specialist**, not the general Pace planner.

## Artifact

- Package id: `qwen3-4b-file-ops-distilled`
- Public artifact: `posttrainllm/qwen3-4b-file-ops-distilled`
- Public storage target: Hugging Face Hub model repo
- Format: HF/MLX safetensors directory
- Base: `Qwen/Qwen3-4B-Instruct-2507`
- Precision: bf16
- Training method: frontier/gold trajectory distillation rendered in the
  student's native tool-calling chat template

## Measured Result

| Suite | Stock 4B | Distilled 4B |
|---|---:|---:|
| File-ops hard gate | 58% | 100% |
| File-ops hardgen held-out | - | 95% |
| Out-of-domain breadth | 59.6% | 42.3% |

The file-ops domain saturated at 4B: the distilled model matched frontier on
the hard and veryhard file-ops gates. The same training caused negative
transfer outside that domain, so this package is only correct behind a router.

## Recommended Use

Use this model when the router has already identified a file-operation task
with derivable arguments: paths, file names, directories, moves, creates,
deletes, and navigation through a file-system backend.

Do not use it as a general planner. For general multi-domain planning, use the
planner lock in `docs/sessions/planner-lock-2026-06-19.md`: stock
Qwen3-4B-Instruct-2507 bf16 with the plan-then-execute prompt.

## Known Limits

- The specialist regresses on non-filesystem BFCL multi-turn backends.
- It was not validated as a broad Pace planner.
- It depends on correct routing. Bad routing turns a narrow win into a broad
  regression.
- The artifact is multi-GB and is published on Hugging Face Hub, not committed
  to this repository or required to remain in local cache.

## References

- `docs/learn/tool-calling-frontier-parity.md` sections 8.1-8.5
- `docs/sessions/planner-lock-2026-06-19.md`
