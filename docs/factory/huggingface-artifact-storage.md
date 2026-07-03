# Hugging Face Artifact Storage

Hugging Face Hub is the default public artifact store for TinyGPT factory
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
- Prefer metadata-only releases before uploading multi-GB fused weights.

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

Only stage weights when we deliberately choose to publish them:

```bash
python3 scripts/plan_hf_artifact_upload.py \
  specialists/qwen3-4b-file-ops-distilled \
  --repo-id sarthakagrawal927/qwen3-4b-file-ops-distilled \
  --include-weights
```

## Current State

The CLI is authenticated for metadata upload, and the first metadata-only
specialist repo is live at:

```text
https://huggingface.co/sarthakagrawal927/qwen3-4b-file-ops-distilled
```

The current public release remains metadata-only until a separate weight-hosting
decision approves uploading the multi-GB fused files.
