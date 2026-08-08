# Design: Published model case studies

## Decision

Use the existing artifact-detail renderer as the case-study system. Each model
is an `ArtifactEntry`; Astro already turns those entries into static detail
pages and includes them in the public indexing pipeline.

```mermaid
flowchart LR
  H[Six public HF model repos] --> I[Verified model inventory]
  I --> E[Evidence in packages, evals, and attempt ledger]
  E --> C[One ArtifactEntry per model]
  C --> P[/artifacts/model-slug]
  P --> S[Sitemap, Markdown, and agent catalog]
```

## Evidence hierarchy

1. Committed specialist package and machine-readable eval report.
2. Frozen benchmark receipt or canonical run evidence.
3. Attempt ledger and historical session record.
4. Hugging Face repository metadata for existence and release identity only.

If a stronger layer is absent, the case study says so. Download/request counts
are time-varying aggregate Hub counters and are not used as adoption evidence.

## Model dispositions

| Model | Case-study disposition |
|---|---|
| `pace-intent-router-v8` | Public weights; strong synthetic result, rejected on sealed eval |
| `qwen3-4b-file-ops-distilled` | Shipped only behind a file-ops router |
| `qwen3-4b-rest-fused` | Research-only routed ship with missing historical performance data |
| `qwen3-4b-multibackend-distilled` | Rejected negative-transfer artifact |
| `vibethinker-3b-mlx` | Report-only upstream-to-MLX conversion |
| `vibethinker-3b-agentic-distilled` | Inconclusive weights archive; current eval missing |

## Rendering

No new component is required. The existing detail page renders headline
numbers, competitive context, attempt/eval tables, blockers, evidence, and next
action. This keeps the current visual language and makes all pages static,
linkable, and crawlable without client JavaScript.

## Publication

After source validation and a clean production build, archive the OpenSpec
change, update project truth, merge through the normal GitHub workflow, trigger
the manual Cloudflare Pages deployment, and smoke-test all six live routes.
