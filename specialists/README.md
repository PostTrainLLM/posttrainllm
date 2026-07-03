# TinyGPT specialist packages

This directory is the registry for model artifacts TinyGPT actually produced.
It is separate from the browser playground gallery because Mac specialists are
often multi-GB HF/MLX safetensors directories, adapters, or GGUF bundles that
the browser cannot load directly.

## Package shape

Each specialist gets a directory:

```text
specialists/<id>/
  model_card.md
  prompt.md
  eval_report.json
  tinygpt.lock.json
  mlx_load.py
```

The package is metadata-first. Large weights are not committed here. The lock
file points to the artifact location and records file sizes and hashes so a
downloaded/cache copy can be verified. Public artifact storage should use
Hugging Face Hub first; Cloudflare R2 is only an optional private cache or
legacy mirror.

Required files:

- `model_card.md`: human-readable purpose, base, training method, limits, and
  recommended use.
- `prompt.md`: system/developer prompt that was part of the measured recipe.
- `eval_report.json`: machine-readable scores and caveats.
- `tinygpt.lock.json`: artifact identity, source path or remote path, expected
  files, sizes, checksums, base model, and compatibility metadata.
- `mlx_load.py`: lightweight helper. It should support metadata-only validation
  by default and require an explicit `--load` before reading large weights.

`registry.json` is the index used by docs, the Mac app, and future `tinygpt
pull` / `tinygpt validate` work.

## Hugging Face storage

Stage a package for upload with:

```bash
python3 scripts/plan_hf_artifact_upload.py specialists/<id> --repo-id <hf-namespace>/<id>
```

The default staging mode copies only metadata. Use `--include-weights` only
after a release decision explicitly approves uploading large model files.

## Current policy

Only publish rows that are real TinyGPT outputs with measured deltas. A stock
base model can be referenced as a parent or baseline, but it should not be
listed as a TinyGPT-built specialist.
