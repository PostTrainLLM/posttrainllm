---
title: "Qwen3-4B ReST Fused — model card"
---

<!-- HuggingFace model-card metadata (the YAML below is the canonical HF card
     header; kept in-body for Blume schema compatibility — paste it back into
     frontmatter when uploading to the Hub). -->

```yaml
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
  - research-specialist
```

# Qwen3-4B ReST Fused

## Model description

A **research specialist** built by [PostTrainLLM](https://posttrainllm.com) —
a Mac-local LLM factory that post-trains small models for narrow agentic tasks.
This model preserves the best measured Qwen3-4B agentic candidate produced by
a teacher-free ReST (Reinforced Self-Training) loop. One ReST iteration
recovered the out-of-domain breadth lost by narrow distillation while
retaining the saturated file-operations gate.

It is a **research specialist package**, not the default Pace planner. The
model speaks BFCL/OpenAI-style tool calls; Pace uses a different intent
envelope and requires its own ship gate.

- **Base model:** `Qwen/Qwen3-4B-Instruct-2507`
- **Precision:** bf16
- **Format:** fused HF/MLX safetensors directory (8 files, ~8 GB)
- **Architecture:** Qwen3ForCausalLM
- **Compatibility:** `mlx_lm`, `posttrainllm serve --hf-dir`

## Eval results

All numbers are historical results recorded on 2026-06-17. Source:
[`qwen3-4b-rest-fused.json`](/report-cards/qwen3-4b-rest-fused.json).

| Suite                 | Stock 4B |  ReST 4B |  Delta |   n |
| --------------------- | -------: | -------: | -----: | --: |
| File-ops hard gate    |     0.58 | **1.00** |  +0.42 |  12 |
| Out-of-domain breadth |    0.596 | **0.65** | +0.054 |  52 |

The breadth suite contains 52 held-out TradingBot, VehicleControlAPI, and
TravelAPI tasks. The depth suite contains 12 file-ops tasks. ReST recovered
breadth (65% vs stock 59.6%) while keeping the file-ops hard gate at 100% —
the negative transfer that plagued the distilled-only variant was reversed.

**Evidence quality caveat:** the raw timing, memory, throughput, and trace
artifacts from the historical run were not preserved. This package does not
claim current latency, RAM, tok/s, or exact qualitative failure counts. A
rerun is intentionally not implied by this metadata promotion.

## Training recipe summary

1. **Target:** same GorillaFileSystem file-ops depth anchor as the distilled
   specialist, plus breadth recovery across TradingBot, VehicleControlAPI,
   and TravelAPI backends.
2. **Method:** teacher-free ReST — one iteration over checker-passing
   interleaved trajectories. No paid model API was used (training cost: $0).
   The checker validated tool-call correctness; passing trajectories were
   folded back into the training set.
3. **Depth anchor:** file-ops gold depth was preserved as an anchor so ReST
   could not regress the saturated 100% hard gate while recovering breadth.
4. **Student:** Qwen3-4B-Instruct-2507 bf16, fused into a single HF/MLX
   safetensors directory.
5. **Decision:** ship as a research specialist — do not use as the Pace
   default planner without re-distillation and a product-specific ship gate.

## Limitations

- **Breadth suite not frontier-validated.** The 65% breadth score is the
  rounded historical result. The 52-task slice was directly compared with
  stock but has not been ceiling-validated against a frontier model.
- **Raw predictions unavailable.** Historical trace artifacts were not
  preserved, so a current qualitative failure review is not possible from
  this package alone.
- **No performance numbers.** Latency, RAM, tok/s, and training duration
  were not recorded. Do not infer Mac-runtime performance from this artifact.
- **Not a Pace planner.** Pace requires a different intent envelope and
  product-specific ship gate. Re-distill and evaluate on Pace's intent
  envelope before considering any downstream promotion.
- **Multi-GB artifact.** Weights are ~8 GB and live on Hugging Face Hub, not
  in git.

## How to use

```python
# Metadata check (no weights loaded)
python mlx_load.py

# Load weights into MLX arrays
python mlx_load.py --load
```

Serve with the PostTrainLLM CLI:

```bash
posttrainllm serve --hf-dir ./qwen3-4b-rest-fused
```

Or load with `mlx_lm`:

```python
from mlx_lm import load, generate
model, tokenizer = load("posttrainllm/qwen3-4b-rest-fused")
```

## Upload command

This model is already published. To re-upload or update metadata:

```bash
# Stage the public metadata surface (no token needed)
python3 scripts/plan_hf_artifact_upload.py \
  specialists/qwen3-4b-rest-fused \
  --repo-id posttrainllm/qwen3-4b-rest-fused

# Upload to Hugging Face Hub (requires HF login)
huggingface-cli upload posttrainllm/qwen3-4b-rest-fused \
  dist/hf-artifacts/qwen3-4b-rest-fused \
  --repo-type model
```

## Links

- **Project:** [posttrainllm.com](https://posttrainllm.com)
- **Hugging Face repo:** [posttrainllm/qwen3-4b-rest-fused](https://huggingface.co/posttrainllm/qwen3-4b-rest-fused)
- **Public artifact page:** [posttrainllm.com/artifacts/qwen3-4b-rest-fused](https://posttrainllm.com/artifacts/qwen3-4b-rest-fused)
- **Eval report:** `eval_report.json` (included in this repo)
- **Lock file:** `tinygpt.lock.json` (included in this repo)
