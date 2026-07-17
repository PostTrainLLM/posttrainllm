---
title: "PRD — Unify the gallery (browser + Mac) + project-level model pins"
---

# PRD — Unify the gallery (browser + Mac) + project-level model pins

## Goal

Two surfaces:

1. **Unified gallery manifest** — extend the existing
   `browser/public/gallery/manifest.json` so it lists not just the
   browser-loadable from-scratch `.bin` models but also the
  *Mac-side* specialists (LoRA + DoRA adapters, GGUF base bundles,
  .tinygpt full models, Hugging Face-hosted artifacts). One published JSON,
   two clients (browser playground + `posttrainllm` CLI), no parallel
   registries.

2. **Project-level model pins** — a `posttrainllm.project.json` per-
   project manifest declaring which models the project depends on
   (analogous to `package.json` / `requirements.txt`). Running
   `posttrainllm pull` from a project dir fetches everything; `posttrainllm
   validate` checks every pin resolves; the Mac app's Factory tab
   (B6) reads pins to populate its model picker.

Together these make the "ship a specialist, ship a project" story
real. Without them, A1/B1/B25/B8 each ship as bespoke download
URLs in the docs — doesn't scale past 3 specialists.

## Why now

- A1 lands a Mac-runnable specialist that users will want to
  pull. Without a gallery entry, the shipping story is "URL in
  the PR description."
- Browser gallery (`gallery-schema.ts`) + Mac CloudPush/Pull
  already exist and overlap in concept but not in schema. Now
  is the cheap moment to unify.
- B6 Mac app (Factory tab) needs a populated model picker.
  The gallery manifest is its data source.

### The trace-loop dividend (added 2026-06-13)

The thing Castform has that we don't is *extensive production
traces* — they observe their customers' agent traffic at the SaaS
boundary, which feeds their dataset-synthesis loop (filtered into
training data → better next iteration). We don't have a SaaS;
we've been on the wrong end of that asymmetry.

Project-level pins flip it: when a project pins models from this
gallery AND runs them through our serve, **we (or the project
owner) own the trace stream by construction**. B22 already
ships per-rollout `.atraj` files at the serve layer; B29 turns
those into training data. The missing piece was *which model the
project is running* — and the project file gives us exactly that
in machine-readable form.

That makes B31 the architectural pivot: it's the file that ties
together gallery (substrate distribution) + traces (B22 substrate
capture) + trace-to-data (B29 substrate refinement) + composite
reward (B28 substrate scoring). The trace dividend isn't a
hypothetical future "if users adopt"; it's free the first time a
project file ships with a non-trivial `models` list.

## Scope — in

### Unified manifest (extends the browser schema)

- Browser-side `browser/src/gallery-schema.ts` gains an optional
  `kind` discriminator: `"browser-bin" | "mac-posttrainllm" |
  "mac-adapter" | "mac-gguf" | "mac-safetensors-hf"`. Existing
  rows default to `"browser-bin"` so nothing breaks.
- New optional fields on `GalleryModel`:
  - `kind: GalleryModelKind`
  - `parent`: for adapters, the gallery id of the base model
    (e.g. `a1-tool-caller` has `parent: "qwen3-4b-instruct-2507"`)
  - `hf_repo`: Hugging Face repo id for Mac artifacts that don't live in
    `browser/public/gallery/`
  - `hf_revision`: optional pinned revision/commit
  - `tags`: `["tool-call", "english", "lora-adapter", ...]`
  - `benchmarks_extended`: composite-reward block per B28 +
    per-suite breakdowns (already partially covered by
    `benchmarks: Record<string, number>` — we extend with named
    dimensions when present)
- Swift mirror: `native-mac/Sources/TinyGPTModel/GalleryManifest.swift` —
  the same Codable shape, single source of truth for parsing.
  Generated from `gallery-schema.ts` by hand on schema edits
  (no codegen tooling for V1).

### Project pins

- New file format: `posttrainllm.project.json` at repo root of a
  consumer project. JSON (not TOML — TS-first codebase, no
  TOML readers shipped). Schema:
  ```json
  {
    "name": "my-pace",
    "posttrainllm_version": ">=2026.06",
    "models": [
      {"id": "qwen3-4b-instruct-2507", "role": "base"},
      {"id": "a1-tool-caller", "role": "adapter",
       "applies_to": "qwen3-4b-instruct-2507"}
    ],
    "datasets": [
      {"id": "hermes-function-calling-v1", "optional": false}
    ]
  }
  ```
- New CLI: `posttrainllm pull` resolves the project file + the gallery
  manifest + Hugging Face Hub, fetches everything to
  `~/.cache/posttrainllm/`, prints what's missing.
- New CLI: `posttrainllm validate` checks every pin in
  `posttrainllm.project.json` exists in the published gallery; flags
  unknown ids before you ship.

### What ships in *this* PR (the scaffolding)

| File | Content |
|---|---|
| `native-mac/Sources/TinyGPTModel/GalleryManifest.swift` | new — Codable types matching gallery-schema.ts; reader for a manifest JSON file. |
| `native-mac/Sources/TinyGPTModel/ProjectManifest.swift` | new — Codable types for `posttrainllm.project.json`. |
| `native-mac/Tests/TinyGPTModelTests/GalleryManifestTests.swift` | new — parse the shipped browser gallery manifest; round-trip; reject malformed shapes. |
| `native-mac/Tests/TinyGPTModelTests/ProjectManifestTests.swift` | new — parse a fixture project file; reject schema violations. |
| `examples/posttrainllm.project.json` | new — fixture example a consumer project can copy. |
| `docs/prds/B31-gallery-and-project-pins.md` | this file. |

### What's deferred (PRD captures, not shipped this PR)

- Browser-side gallery UI changes (filter by `kind`, show
  adapters alongside bases). Browser team consumes the schema
  extension when ready.
- `posttrainllm pull` CLI extension — should resolve `hf_repo`/`hf_revision`
  through Hugging Face Hub first; R2 remains a legacy mirror only.
- `posttrainllm validate` CLI — same.
- Publishing `a1-tool-caller` as the first new gallery row — gated
  on A1 actually shipping.

## Scope — out

- **R2 as the source of truth.** It remains useful as a private cache, but
  public artifacts should live on Hugging Face Hub.
- **Multi-version pinning** with semver resolution. V1 is
  exact-id pinning. Versions come later if churn becomes a problem.
- **Lockfile** (`posttrainllm.project.lock.json`). Defer; until we
  have versioning, lockfile content is the same as the pins.
- **OCI registry-style content addressing.** Big design surface;
  defer.

## Acceptance criteria

### Scaffolding (this PR)

- [x] `GalleryManifest.swift` parses
  `browser/public/gallery/manifest.json` without error (existing
  rows; new `kind` field defaults to `browser-bin`).
- [x] `ProjectManifest.swift` parses `examples/posttrainllm.project.json`
  and rejects a malformed fixture.
- [x] Both Swift modules ship with passing unit tests.

### Full B31 ship (remaining)

- [x] One Mac-side specialist package registered:
  `specialists/qwen3-4b-file-ops-distilled` with model card, prompt,
  eval report, artifact lock, and MLX validation helper. It is tracked in
  `specialists/registry.json` rather than the browser manifest because its
  7.5 GB HF/MLX safetensors artifact is not browser-loadable.
- [ ] Publish Mac-side specialist entries into the unified gallery manifest
  once the browser filters out `kind != "browser-bin"` rows and HF repo ids are
  assigned.
- [ ] `posttrainllm pull` reads `./posttrainllm.project.json`, fetches every
  pin from Hugging Face Hub, validates checksums (the `fileBytes` field from
  the manifest), reports skipped + failed.
- [ ] `posttrainllm validate` flags unknown ids.
- [ ] Browser playground filters out `kind != browser-bin` rows
  from its dropdown (so it stays focused on the in-browser
  models).
- [ ] B6 Mac app Factory tab reads the gallery + project files
  for its model picker.

## Reference patterns

- `browser/src/gallery-schema.ts` — the existing schema; extend,
  don't fork.
- `scripts/plan_hf_artifact_upload.py` — stages specialist metadata for
  Hugging Face upload without requiring secrets.
- `docs/gallery_v2_plan.md` — the v1.5 + v2 roadmap; this PRD now
  supersedes its old R2-first hosting stance for public Mac artifacts.

## Open questions

- Whether the project file lives in `./posttrainllm.project.json` (at
  project root) or `./.tinygpt/project.json` (hidden, package-
  manager convention). **Recommendation:** visible — users should
  be able to read it without `ls -la`. Convention follows
  `package.json`.
- Whether to mirror the schema in YAML for friendlier diffs.
  **Recommendation:** no — keep one format; JSON is what
  `gallery-schema.ts` already speaks.

## Sibling note: mascot

Castform's brand-ambassador cartoon prompted a related question:
should posttrainllm have one? **Yes** — pace-the-companion is the
natural Pace caricature; "posttrainllm-the-trainer" is the distinct
character for the platform/toolkit side. Filed in
`docs/decision_log.md` as a marketing/identity item (not a feature
PRD).
