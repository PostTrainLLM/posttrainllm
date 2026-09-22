# Artifact Lifecycle Contract

Weight files encode tensors. The schema-v1 sidecar records what the artifact
is, which base and tokenizer it belongs to, and what is safe to do next.
`TinyGPTIO` owns this small JSON contract.

## Sidecar discovery

The sidecar always travels with the artifact:

```text
model.tinygpt
model.tinygpt.artifact-manifest.json

adapter.lora
adapter.lora.artifact-manifest.json

mlx-package/
  artifact-manifest.json
  config.json
  ...
```

File manifests use the artifact filename in `artifact_path`. Directory
manifests use `"."`. All receipt paths are relative. Copying the artifact and
its sidecar together is therefore sufficient for discovery in a new location.

## Schema v1

```json
{
  "schema_version": 1,
  "artifact": {
    "id": "pace-planner-sft-v1",
    "revision": "recipe-v1"
  },
  "kind": "adapter",
  "artifact_path": "pace-planner-sft-v1.lora",
  "base": {
    "id": "Qwen/Qwen3-4B-Instruct-2507",
    "revision": "cdbee75f17c01a7cc42f958dc650907174af0554"
  },
  "tokenizer": {
    "id": "Qwen/Qwen3-4B-Instruct-2507",
    "revision": "cdbee75f17c01a7cc42f958dc650907174af0554",
    "chat_template": "chatml"
  },
  "history": [
    {
      "action": "sft",
      "tool": "posttrainllm",
      "detail": "method=sft-lora; steps=400; rank=16"
    }
  ],
  "runtimes": ["native-hf-load"],
  "next": ["merge", "convert", "eval", "serve"],
  "receipts": [
    { "kind": "eval", "path": "receipts/eval.json" }
  ],
  "created_at": "2026-09-23T00:00:00Z"
}
```

Allowed kinds are `base-model`, `adapter`, `training-checkpoint`, and
`deploy-package`. Legal next actions are `resume-exactly`, `warm-restart`,
`merge`, `convert`, `eval`, and `serve`.

`resume-exactly` is a strict claim. It requires a pinned checkpoint identity
and persisted optimizer, scheduler, and RNG state. A weight checkpoint without
all four advertises `warm-restart`, never exact resume.

## Producer and consumer rules

Producers write weights or package contents first, then atomically write the
manifest. Native checkpoints, factory SFT adapters, manifest-aware finetuning,
and MLX exports follow this ordering.

Consumers validate before loading model bytes:

- `sample` and `hf-load --sample` require `eval` plus a compatible runtime.
- `serve` requires `serve` plus a compatible runtime.
- adapter consumers compare the pinned adapter base with the selected base and
  refuse a proven mismatch before applying adapter weights.
- factory training evidence requires `artifact.json.lifecycle_manifest` to
  name the adjacent sidecar. `publish-check` validates the same sidecar and its
  artifact/base identities.

Malformed manifests, unsafe paths, unsupported runtimes, and illegal actions
fail closed. A valid adapter whose selected base lacks enough identity to prove
the binding emits an explicit warning rather than pretending it was verified.

## Privacy boundary

The manifest contains bounded metadata, not training content. History is
limited to 64 single-line steps; receipts are limited to 64 relative paths.
Absolute/traversing paths, credential-like values, prompt/completion payloads,
multiline logs, and oversized fields are rejected. Store evaluation detail in
the referenced receipt, subject to that receipt's own privacy contract.

## Legacy migration

Artifacts without a sidecar remain loadable and produce a `lifecycle/base
verification is unavailable` warning. The runtime does not infer a revision,
template, recipe, or receipt for them.

To migrate an artifact, create a sidecar only from known evidence and copy it
beside the artifact. If any identity is unknown, keep the artifact legacy. A
plausible but invented revision is more dangerous than an explicit warning.
