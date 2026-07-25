# Foundry Evidence Contract — posttrainllm

This is posttrainllm's runtime-specific evidence contract for the fleet
automation closure. It defines what surfaces exist, what evidence each surface
must produce, where private data boundaries are, and what sanitized receipts
the Foundry control plane may consume.

It is the canonical home for the contract; other docs link here rather than
restating it. See `../AGENTS.md` for the project north-star and
`openspec/changes/automate-posttrainllm` (in the fleet-automation-closure
Store) for the source PRD.

## Scope and authority

- Automation MAY prepare local artifacts, reports, and PRs.
- Automation MUST NOT publish a model, release, benchmark claim, or production
  deploy without explicit approval. Production deploys remain manual via
  `scripts/manual-deploy.mjs`, which itself requires a green CI run on `main`.
- No new production dependency was added by this contract. Receipts reuse
  existing in-repo evidence (git, `specialists/registry.json`, factory-run
  folders, `docs/factory/public-artifacts.md`, GitHub Actions status via `gh`).

## Surface inventory

| Surface | Runtime | Owner artifact | Live URL / location |
|---|---|---|---|
| Public site (Astro) | Static / Cloudflare Pages | `browser/` | https://posttrainllm.com/ |
| WebGPU playground | Static / browser | `browser/src/pages/playground.astro`, `browser/public/tinygpt*.{js,wasm}` | https://posttrainllm.com/playground |
| Public artifact index | Static | `browser/src/pages/artifacts/`, `specialists/registry.json` | https://posttrainllm.com/artifacts |
| Agent indexing | Static | `browser/public/{llms.txt,llms-full.txt,api-ai.json,robots.txt,sitemap.xml}` | https://posttrainllm.com/llms.txt |
| Specialist packages | Repo + Hugging Face Hub | `specialists/<id>/`, `specialists/registry.json` | `hf://models/posttrainllm/<id>` |
| Factory CLI | Native (Swift/MLX) | `native-mac/Sources/TinyGPT/` | local binary `posttrainllm` |
| Factory run artifacts | Local filesystem (gitignored) | `runs/<id>/` per `run-schema.md` | local only |
| Local training/eval | Native + Python | `native-mac/`, `python_ref/`, `evals/`, `scripts/` | local only |
| Nightly dataset jobs | Local cron / manual | `scripts/nightly.sh`, `scripts/nightly/N*.sh` | `~/.cache/posttrainllm/nightly/` |
| Releases / deploys | GitHub Actions + Cloudflare Pages | `.github/workflows/{ci,deploy}.yml`, `scripts/manual-deploy.mjs` | manual dispatch |
| CI | GitHub Actions | `.github/workflows/ci.yml` | per-commit on `main` and PRs |

## Per-surface evidence contracts

Each contract resolves to one of: `pass`, `fail`, `stale`, `blocked`,
`accepted-exception`, or `not-applicable`, with an observation time, freshness
window, evidence reference, and next action. The Foundry receipt emitted by
`scripts/foundry_receipt.py` carries the machine-readable form.

### Public site (Astro)

- **Build**: `pnpm --dir browser run build` succeeds (tsc + astro build +
  docs). Source: CI `browser` job.
- **Live**: `https://posttrainllm.com/` returns 200 and matches the deployed
  git revision. Source: `scripts/manual-deploy.mjs` records the deployed SHA;
  Foundry receipt records the latest `main` SHA and the CF Pages deployment
  alias when `gh` is available.
- **Indexing**: `llms.txt`, `llms-full.txt`, `api-ai.json`, `robots.txt`,
  `sitemap.xml` are present in `browser/public/` and built into `dist/`.
  Source: `evals/foundry-receipt-smoke.sh` asserts presence.
- **Source revision**: every Foundry receipt records `git rev-parse HEAD`,
  branch, and dirty flag.
- **Freshness window**: 14 days for the live site; older than that is `stale`.

### WebGPU playground

- **Bundle**: `browser/public/tinygpt{,64}.{js,wasm}` committed and matches a
  pinned emsdk rebuild. Source: CI `wasm-drift` job.
- **Activation**: `playground_loaded` analytics event exists with
  privacy-safe fields only (browser, has_webgpu, has_memory64, has_wasm_simd,
  cores, device_memory_gb, cpu_probe_ms). Activation is independent of the
  landing: a healthy landing with a broken playground bundle fails playground
  activation separately.
- **Client failure**: `foundry_page_crash` PostHog event captures uncaught
  errors and unhandled rejections with route, source, and message only — no
  prompt, corpus, or generated text. See `browser/src/analytics.ts`.
- **Download/run intent**: the playground page exposes a "run in browser"
  intent; acquisition is captured via `playground_loaded`. No separate
  download artifact for the playground itself.

### Specialist packages and public artifacts

- **Registry**: `specialists/registry.json` is the canonical list. Every
  package entry MUST have `id`, `kind`, `storage`, `base`, `status`,
  `model_card`, `eval_report`, `prompt`, `lock`.
- **Provenance**: every public quality claim (e.g. "file-ops hard gate
  58% → 100%") MUST link the exact source revision, model id, eval config,
  dataset/version, time, result, and artifact location or retention status.
  `scripts/check_foundry_receipt.py` enforces this on any receipt that
  carries a `quality_claim`.
- **Release state**: each artifact declares one of `release-ready-metadata`,
  `release-ready-weights`, `candidate-current-best`, `report-only`,
  `blocked`, `parked`. See `docs/factory/public-artifacts.md`.
- **Ownership / retention / size-cost**: each registry entry's `storage`
  block records `primary`, `repo_id`, and `status`. The Foundry receipt
  surfaces these without copying weights. Size/cost guards remain manual
  (no automatic budget enforcement); the receipt records `not-applicable`
  for any package without a declared size guard.
- **Rollback / reproducibility**: HF Hub preserves every pushed revision;
  `tinygpt.lock.json` pins the base model revision. The receipt records
  `reproducibility: lockfile-present` when the lock exists, otherwise `fail`.

### Local training / evaluation

- **Local workflow completion receipt**: when a factory run completes, the
  run folder (`runs/<id>/`) contains the fragments defined in
  `run-schema.md`. `scripts/assemble_factory_run.py` derives
  `provenance.json` and `report.md`. The Foundry receipt carries only:
  run_id, target slug, method, decision, baseline/candidate scores, delta,
  git revision, dataset sha256 + row count, the publish-check verdict, and
  bounded lifecycle fields (schema version, phase, revision, update time,
  imported/stale flags, and optional sanitized failure code/summary).
  It MUST NOT carry prompts, completions, raw predictions, training logs
  beyond the file path, or any checkpoint bytes.
- **Active-run discovery**: lifecycle-managed partial folders may appear in a
  receipt before `decision.json` or `provenance.json` exists. Their lifecycle
  state is read-only operational evidence, `publish_check` is
  `not-applicable`, source revision may be absent, and publication remains
  `pending-approval`. The receipt never transitions or reconciles a run.
- **Lifecycle authority**: `phase=decided` does not assert ship/reject/retry and
  never grants publication. `decision.json`, the publish checks, and explicit
  human approval retain their existing authority.
- **Eval evidence**: any automated benchmark or quality claim MUST identify
  source revision, model, configuration, dataset/version, time, result, and
  artifact location or retention status. Receipts that omit any of these
  cannot update a public quality claim; `check_foundry_receipt.py` reports
  the missing field as a blocking gap.
- **Heavy-work gate**: training and full GPU evals remain operator-dependent
  and respect `~/.cache/posttrainllm/gpu.lock` and the AGENTS.md heavy-work
  rules. The Foundry receipt records `not-applicable` for live training
  evidence when no run folder is present.

### Scheduled data / feed freshness

- **Nightly jobs**: `scripts/nightly.sh` runs `scripts/nightly/N*.sh` in lex
  order under `caffeinate -di`, logging to
  `~/.cache/posttrainllm/nightly/logs/` and touching
  `~/.cache/posttrainllm/nightly/done/<job>.done` on success.
- **Bounds**: each `N*.sh` is single-shot and idempotent; the runner picks
  the lowest-numbered pending job and stops.
- **Freshness**: a job is `stale` when its `.done` marker is older than the
  declared window (default 7 days) OR absent. The Foundry receipt records
  `pass` / `stale` / `fail` per job by inspecting the `.done` markers.
- **Failure / retry**: a failed job leaves no `.done` marker so the next run
  picks it up again. The receipt records `fail` with the log path (not
  contents) when a log file exists but no `.done` marker does.
- **Unresolved state**: jobs with neither `.done` nor a log file are
  `not-applicable` (never run on this host).
- **Note**: nightly jobs are local-only and not fleet-hosted. The receipt
  records `not-applicable` when the nightly cache directory is absent.

### Releases and deploys

- **CI gate**: `.github/workflows/ci.yml` runs on every push to `main` and
  every PR. The Foundry receipt queries `gh run list --workflow=ci.yml
  --branch=main` for the latest run and records status, conclusion, head SHA,
  and URL.
- **Deploy gate**: `.github/workflows/deploy.yml` is `workflow_dispatch`
  only. `scripts/manual-deploy.mjs` refuses to dispatch unless the working
  tree is clean, the branch is `main`, and the latest CI run on `main` is
  green at the current HEAD.
- **Manual publication authority**: no automated receipt or script publishes
  a model, release, benchmark claim, or production deploy. The receipt
  records `pending-approval` for any candidate artifact that passes
  validation.

## Private data boundaries

The following MUST NOT appear in any Foundry receipt, evidence matrix, or
fleet report:

- Private dataset contents (rows, prompts, completions, golds).
- Private training logs beyond the file path.
- Checkpoint bytes, adapter weights, optimizer state.
- Raw model outputs / predictions.
- API keys, HF tokens, Cloudflare credentials, PostHog project keys (the
  PostHog public ingest key is the only exception, and only in build-time
  `VITE_*` env, never in receipts).
- Local filesystem paths under `$HOME/.cache/` beyond the canonical
  `~/.cache/posttrainllm/nightly/{logs,done}/` markers used for freshness.
- Anything covered by `~/.gitignore` or this repo's `.gitignore` that is not
  a committed metadata file.

`scripts/check_foundry_receipt.py` enforces this with a denylist of field
names and a payload-bytes ceiling. `tests/test_foundry_receipt.py` proves
private fixtures cannot leak through the sanitizer.

## Receipt shape

Emitted by `scripts/foundry_receipt.py`:

```json
{
  "schema_version": 1,
  "project": "posttrainllm",
  "generated_at": "<ISO8601>",
  "source_revision": { "commit": "<sha>", "branch": "main", "dirty": false },
  "ci": { "status": "completed", "conclusion": "success", "head_sha": "<sha>", "url": "<url>" },
  "public_site": { "build": "pass", "live": "pass", "indexing": "pass", "freshness_window_days": 14 },
  "playground": { "bundle": "pass", "activation_event": "playground_loaded", "failure_event": "foundry_page_crash" },
  "artifacts": [
    {
      "id": "<id>",
      "state": "release-ready-weights",
      "storage": { "primary": "huggingface_hub", "repo_id": "<repo>", "status": "weights-published" },
      "reproducibility": "lockfile-present",
      "size_cost_guard": "not-applicable",
      "quality_claims": [
        { "metric": "file-ops hard gate", "baseline": 0.58, "candidate": 1.00,
          "source_revision": "<sha>", "model": "<id>", "eval_config": "<ref>",
          "dataset_version": "<sha256 or ref>", "observed_at": "<ISO8601>",
          "artifact_location": "hf://models/<repo>", "retention": "hf-preserved" }
      ]
    }
  ],
  "local_runs": [
    { "run_id": "<id>", "target": "<slug>", "method": "<method>", "decision": "<decision>",
      "baseline_score": 0.58, "candidate_score": 1.00, "delta": 0.42,
      "source_revision": "<sha>", "dataset_sha256": "<sha>", "dataset_rows": 10,
      "publish_check": "pass",
      "lifecycle": { "schema_version": 1, "phase": "decided", "revision": 4,
        "updated_at": "<ISO8601>", "imported": false, "stale_active": false,
        "failure": null },
      "publication": "pending-approval" }
  ],
  "nightly": [
    { "job": "N01-pull-datasets", "state": "pass|stale|fail|not-applicable",
      "last_done_at": "<ISO8601 or null>", "freshness_window_days": 7,
      "log_path": "<path or null>" }
  ],
  "publication_authority": "manual",
  "accepted_exceptions": [],
  "blocked": []
}
```

Every field is either derived from committed repo metadata, the local
nightly cache markers, or `gh` read-only queries. No field copies a private
payload.
