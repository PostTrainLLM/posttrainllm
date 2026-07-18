---
title: "Hugging Face Artifact Storage"
description: "Hugging Face Hub is the default public artifact store for posttrainllm factory"
---

# Hugging Face Artifact Storage

Hugging Face Hub is the default public artifact store for posttrainllm factory
outputs.

Cloudflare R2 is no longer the source of truth for public model artifacts. Keep
R2 only as an optional private cache or legacy mirror.

## Policy

- Public reports, model cards, eval JSON, prompts, lockfiles, and small dataset
  manifests go to public Hugging Face repos first.
- Large weights/adapters go to Hugging Face only after the artifact has a
  `ship` or explicit public-release decision.
- Do not upload secrets, raw private traces, private local paths, or unreviewed run
  folders.
- Do not commit HF tokens. Use `hf auth login` or `HF_TOKEN` from the
  shell environment.
- Prefer metadata-only releases first; upload large weights after an explicit
  release decision and remote verification plan.

## Repo Shape

Use one HF model repo per shipped specialist:

```text
<namespace>/<artifact-id>
  README.md
  artifact_manifest.json
  tinygpt.lock.json
  eval_report.json
  prompt.md
  weights/                 # optional, only after ship decision
```

Use an HF dataset repo for eval fixtures or report-only data that is not a
model package:

```text
<namespace>/<artifact-id>-evals
  README.md
  manifest.json
  *.jsonl
```

## First Command

Stage the current file-ops specialist metadata without copying weights:

```bash
python3 scripts/plan_hf_artifact_upload.py \
  specialists/qwen3-4b-file-ops-distilled \
  --repo-id sarthakagrawal927/qwen3-4b-file-ops-distilled
```

Then authenticate and upload:

```bash
hf auth login
hf repos create sarthakagrawal927/qwen3-4b-file-ops-distilled \
  --repo-type model \
  --public \
  --exist-ok
hf upload sarthakagrawal927/qwen3-4b-file-ops-distilled \
  dist/hf-artifacts/qwen3-4b-file-ops-distilled . \
  --repo-type model
```

Only stage weights when we deliberately choose to publish them. If the package
lock no longer points to a local cache, pass `--weights-source`:

```bash
python3 scripts/plan_hf_artifact_upload.py \
  specialists/qwen3-4b-file-ops-distilled \
  --repo-id sarthakagrawal927/qwen3-4b-file-ops-distilled \
  --weights-source ~/.cache/posttrainllm/models/mt4b_fused \
  --include-weights
```

## Current State

The CLI is authenticated, and the first specialist repo is live at:

```text
https://huggingface.co/sarthakagrawal927/qwen3-4b-file-ops-distilled
```

The fused model files were uploaded in commit
`33a7244854f797e35b34ce05a6d5184f0949ada7` and verified against the lock by
remote file size. Local cache copies are optional after that verification.
