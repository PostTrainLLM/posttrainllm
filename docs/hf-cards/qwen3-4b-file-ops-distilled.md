---
title: "Qwen3-4B File-Ops Distilled — model card"
---

<!-- HuggingFace model-card metadata (the YAML below is the canonical HF card
     header; kept in-body for Blume schema compatibility — paste it back into
     frontmatter when uploading to the Hub). -->

```yaml
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
  - routed-specialist
```

# Qwen3-4B File-Ops Distilled

## Model description

A **routed specialist** built by [PostTrainLLM](https://posttrainllm.com) — a
Mac-local LLM factory that post-trains small models for narrow agentic tasks.
This model is a fused Qwen3-4B-Instruct-2507 (bf16) directory distilled on
frontier/gold multi-turn file-operation trajectories (GorillaFileSystem tasks
from the BFCL hard gate). It is **not** a general-purpose planner.

The distillation matched frontier performance on the file-ops hard gate while
running entirely on one Apple Silicon Mac. The honest trade-off — breadth
regression — is disclosed below and in every public artifact page.

- **Base model:** `Qwen/Qwen3-4B-Instruct-2507`
- **Precision:** bf16
- **Format:** HF/MLX safetensors directory (8 files, ~8 GB)
- **Architecture:** Qwen3ForCausalLM
- **Compatibility:** `mlx_lm`, `posttrainllm serve --hf-dir`

## Eval results

All numbers are from the PostTrainLLM factory eval gate — frozen baselines
stamped before training, same prompt, same scorer. Source:
[`specialists/qwen3-4b-file-ops-distilled/eval_report.json`](https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled/blob/main/eval_report.json).

| Suite | Stock 4B | Distilled 4B | Frontier (Claude) | n |
|---|---:|---:|---:|---:|
| File-ops hard gate | 0.58 | **1.00** | 1.00 | 12 |
| File-ops hardgen held-out | 0.60 | **0.95** | — | 40 |
| Out-of-domain breadth | 0.596 | 0.423 | — | 52 |

The file-ops domain saturated at 4B: the distilled model matched frontier on
the hard gate. The same training caused **negative transfer** outside that
domain — breadth dropped 59.6% → 42.3% (−17.3 points). This is real
catastrophic forgetting, not noise. The model ships as a routed specialist
and must never be used as a general planner.

## Training recipe summary

1. **Target:** GorillaFileSystem multi-turn file-operation tasks (BFCL hard
   gate, 12 tasks + 40 held-out hardgen tasks).
2. **Teacher:** frontier/gold trajectory distillation — Claude produced
   correct multi-turn trajectories on the same task fixtures; trajectories
   were rendered in the student's native tool-calling chat template.
3. **Student:** Qwen3-4B-Instruct-2507 bf16, fine-tuned on the rendered
   trajectories with the plan-then-execute system prompt (see `prompt.md`).
4. **Eval gate:** frozen baseline stamped before training (stock 4B = 0.58 on
   hard gate); post-training eval ran the same 12 hard + 40 hardgen + 52
   breadth tasks with the same scorer.
5. **Decision:** ship as routed specialist — depth win is real, breadth
   regression is real, routing is the safety boundary.

Full eval report and lock file are included in this repo.

## Limitations

- **Breadth regression is real.** Out-of-domain breadth dropped 17.3 points
  vs stock. The model is unsafe as a general planner. Use only behind a
  domain router that has identified a file-operation task.
- **The breadth suite is not frontier-validated.** The 52-task breadth slice
  is directly comparable to stock but has not been ceiling-validated against
  a frontier model. Do not oversell the breadth number as a general
  capability measure.
- **Depends on correct routing.** Bad routing turns a narrow win into a broad
  regression. The router must confine this model to file-ops tasks with
  derivable arguments (paths, file names, directories, moves, creates,
  deletes, navigation).
- **Not validated as a Pace planner.** Pace uses a different intent envelope
  and ship gate. Do not wire by model name alone.
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
posttrainllm serve --hf-dir ./qwen3-4b-file-ops-distilled
```

Or load with `mlx_lm`:

```python
from mlx_lm import load, generate
model, tokenizer = load("posttrainllm/qwen3-4b-file-ops-distilled")
```

## Upload command

This model is already published. To re-upload or update metadata:

```bash
# Stage the public metadata surface (no token needed)
python3 scripts/plan_hf_artifact_upload.py \
  specialists/qwen3-4b-file-ops-distilled \
  --repo-id posttrainllm/qwen3-4b-file-ops-distilled

# Upload to Hugging Face Hub (requires HF login)
huggingface-cli upload posttrainllm/qwen3-4b-file-ops-distilled \
  dist/hf-artifacts/qwen3-4b-file-ops-distilled \
  --repo-type model
```

## Links

- **Project:** [posttrainllm.com](https://posttrainllm.com)
- **Hugging Face repo:** [posttrainllm/qwen3-4b-file-ops-distilled](https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled)
- **Public artifact page:** [posttrainllm.com/artifacts/qwen3-4b-file-ops-distilled](https://posttrainllm.com/artifacts/qwen3-4b-file-ops-distilled)
- **Eval report:** `eval_report.json` (included in this repo)
- **Lock file:** `tinygpt.lock.json` (included in this repo)
