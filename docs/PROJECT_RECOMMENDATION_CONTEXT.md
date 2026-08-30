# Project Recommendation Context

Generated: 2026-07-02T00:00:00.000Z

This file is a CodeVetter Repo Unpacked-inspired audit written for Starboard recommendations. It is intentionally local, evidence-oriented, and safe to commit: it records product context, feature areas, stack inventory, and recommendation guidance without secrets or environment values.

## Project Identity

- Slug: `posttrainllm`
- Registry description: posttrainllm.
- Product grouping: `internal-first`
- Source path: `posttrainllm`

## Product Context

posttrainllm is now framed as a **Mac-local specialist factory**. The active product
loop is target -> data -> post-training -> eval -> package -> report. The
browser GPT-from-scratch playground remains a successful public demo and
learning artifact, but the active work center is the native Swift/MLX factory
CLI, run artifacts, eval gates, and specialist package reports.

The current wedge is not a coding-agent product, a browser/WebGPU polish push,
or broad research expansion. It is proving that posttrainllm can repeatedly turn a
local base model plus task data into a measured specialist on a Mac, with
before/after evals, regressions, cost/latency/RAM/tok-s, packaging metadata, and
a ship/reject decision.

## Feature Map

- **AI agents**: Agents, tool use, workflows, orchestration, RAG, evals, and model integration. Keywords: ai, agent, agents, llm, rag, embedding, eval, model.
- **UI workflows**: Dashboards, tables, forms, component systems, charts, and user workflows. Keywords: ui, ux, dashboard, table, component, react, next, tailwind.
- **Testing and quality**: Unit tests, browser tests, evals, CI quality gates, and regression checks. Keywords: test, testing, quality, vitest, playwright, ci, eval, benchmark.
- **Content and media**: Content production, video, reels, documents, markdown, and publishing workflows. Keywords: content, media, video, reel, markdown, document, publish, editor.
- **Browser and extensions**: Browser extensions, page capture, annotation, automation, and client-side integrations. Keywords: browser, extension, chrome, annotation, capture, webpage, reader.
- **Search and discovery**: Search, ranking, recommendations, feeds, semantic retrieval, and discovery UX. Keywords: search, discovery, recommend, ranking, semantic, feed, index, retrieval.
- **Analytics and intelligence**: Signal analysis, forecasting, monitoring, trends, metrics, and decision support. Keywords: analytics, intelligence, signal, forecast, monitoring, metric, trend, insight.

## Runtime Surfaces and Entrypoints

- `PROJECT_STATUS.md`
- `docs/NEXT.md`
- `docs/factory/overview.md`
- `docs/factory/run-schema.md`
- `docs/factory/eval-protocol.md`
- `docs/factory/packaging.md`
- `docs/factory/reports.md`
- `browser/src/pages/eval-leaderboard.astro`
- `browser/src/pages/index.astro`
- `browser/src/pages/leaderboard.astro`
- `browser/src/pages/playground.astro`
- `browser/src/pages/roadmap.astro`
- `browser/src/pages/sae-timeline.astro`
- `browser/src/pages/speedup.astro`
- `browser/src/pages/training-dashboard.astro`
- `browser/src/pages/webgpu-test.astro`
- `native-mac/Sources/TinyGPT/Agent.swift`
- `native-mac/Sources/TinyGPT/AgentLoop.swift`
- `native-mac/Sources/TinyGPT/Bench.swift`
- `native-mac/Sources/TinyGPT/BestOfN.swift`
- `native-mac/Sources/TinyGPT/CausalTrace.swift`
- `native-mac/Sources/TinyGPT/CloudList.swift`
- `native-mac/Sources/TinyGPT/CloudPull.swift`
- `native-mac/Sources/TinyGPT/CloudPush.swift`
- `native-mac/Sources/TinyGPT/ColdStart.swift`
- `native-mac/Sources/TinyGPT/Compare.swift`
- `native-mac/Sources/TinyGPT/DPO.swift`
- `native-mac/Sources/TinyGPT/Debug.swift`
- `native-mac/Sources/TinyGPT/Dedupe.swift`
- `native-mac/Sources/TinyGPT/Distill.swift`
- `native-mac/Sources/TinyGPT/DownloadDataset.swift`
- `native-mac/Sources/TinyGPT/ES.swift`
- `native-mac/Sources/TinyGPT/Escalate.swift`
- `native-mac/Sources/TinyGPT/Eval.swift`
- `native-mac/Sources/TinyGPT/EvalBFCL.swift`
- `native-mac/Sources/TinyGPT/EvalCompare.swift`
- `native-mac/Sources/TinyGPT/EvalHarnessSupport.swift`
- `native-mac/Sources/TinyGPT/EvalHumanEval.swift`
- `native-mac/Sources/TinyGPT/EvalIndic.swift`
- `native-mac/Sources/TinyGPT/EvalMTEB.swift`
- `native-mac/Sources/TinyGPT/EvalTauBench.swift`
- `native-mac/Sources/TinyGPT/Extract.swift`
- `native-mac/Sources/TinyGPT/ExtractorData.swift`
- `native-mac/Sources/TinyGPT/FetchGitHub.swift`
- `native-mac/Sources/TinyGPT/Filter.swift`
- `native-mac/Sources/TinyGPT/Finetune.swift`

## Current Stack

- Languages: `Astro`, `Python`, `Rust`, `Swift`, `TypeScript`
- Frameworks/tools: `Astro`, `Cargo`, `Swift Package Manager`
- Config files:
- `browser/_legacy_html/vite.config.ts.bak`
- `browser/astro.config.mjs`
- `native-mac/Package.swift`
- `scripts/data-prep/pyproject.toml`
- `scripts/hf-downloader/Cargo.toml`
- `scripts/humaneval-sandbox/Cargo.toml`
- `scripts/parquet-decoder/Cargo.toml`
- `scripts/tokenizer-trainer/Cargo.toml`

## OSS Already In Use

Direct dependencies:
- `@floating-ui/dom`
- `posthog-js`

Development dependencies:
- `@astrojs/mdx`
- `@fontsource-variable/geist`
- `@fontsource-variable/geist-mono`
- `@types/node`
- `@webgpu/types`
- `astro`
- `lightningcss`
- `playwright`
- `sharp`
- `typescript`

Package scripts:
- `build`
- `dev`
- `e2e`
- `preview`
- `typecheck`
- `typecheck:tools`
- `webgpu-test`

## Testing and Quality Signals

- `tests/README.md`
- `tests/bench_wasm.mjs`
- `tests/smoke_wasm64_node.mjs`
- `tests/smoke_wasm_node.mjs`
- `tests/test_f16_packer.mjs`
- `tests/test_fa2_backward_parity.mjs`
- `tests/test_fa2_compile.mjs`
- `tests/test_fa2_parity.mjs`
- `tests/test_lora.py`
- `tests/test_phase1.py`
- `tests/test_wasm64_xl_node.mjs`
- `tests/test_wasm_kernels.cpp`
- `tests/test_wasm_model.cpp`
- `tests/train_demo.mjs`

## Recommendation Guidance

Good matches:
- Repos that strengthen local model post-training, PEFT, preference tuning, eval
  gates, dataset curation, trace conversion, specialist packaging, or before/after
  reporting.
- Tools that help implement the factory loop without replacing the existing
  Swift/MLX, Astro, or eval infrastructure.
- Focused benchmark/report utilities that can attach cost, latency, RAM, tok-s,
  and regression data to a run artifact.
- Tools with concrete support for posttrainllm's native factory path:
  `native-mac`, `evals`, `scripts`, `docs/factory`, `specialists`.
- Implementation repos, SDKs, CLIs, testing utilities, adapters, and focused libraries are higher value than generic awesome lists.

Avoid recommending:
- Do not recommend packages already listed under direct or development dependencies unless the task is migration research.
- Do not recommend broad framework replacements unless the project context explicitly calls for a rewrite.
- Downrank curated lists, archived repos, stale demos, and generic UI kits that do not map to the feature catalog.
- Downrank browser/WebGPU polish, VLM, ANE/CoreML, or Tier 5 research tooling
  unless the current factory run explicitly needs it.

## Evidence Read

Primary docs and handoff files:
- `AGENTS.md`
- `PROJECT_STATUS.md`
- `README.md`
- `docs/NEXT.md`
- `docs/factory/overview.md`
- `docs/factory/run-schema.md`
- `docs/factory/eval-protocol.md`
- `docs/CITATIONS.md`
- `docs/MAP.md`
- `docs/PLAN.md`
- `docs/agent_runtime.md`
- `docs/async_tool_dispatch.md`
- `docs/audits/audit_2026.md`
- `docs/backlog.md`
- `docs/performance/benchmark_first_run.md`
- `docs/performance/benchmark_harness_design.md`
- `docs/bpe_browser_scoring.md`
- `docs/browser_notes.md`
- `docs/capability_matrix.md`
- `docs/performance/cold_start_results.md`
- `docs/techniques/constrained_generation.md`
- `docs/integrations/continue_provider.md`
- `docs/performance/cpu_speedup_results.md`
- `docs/performance/cpu_utilization_research.md`
- `docs/data_inventory.md`
- `docs/performance/data_perf.md`
- `docs/dataset-inventory.md`
- `docs/decision_log.md`
- `docs/integrations/deploy.md`
- `docs/performance/determinism.md`
- `docs/techniques/distillation.md`

Package manifests:
- `browser/package.json`

Inventory notes:
- Files scanned: 724
- This pass uses deterministic repo inventory plus local documentation/source-path evidence. It does not claim a full manual line-by-line review of every source file.

## Confidence

Confidence: **high**

Why:
- PROJECT_STATUS.md present
- README.md present
- 42 entrypoint/runtime files identified
- package dependencies inventoried
- 14 test/quality files identified

Refresh command:

```bash
cd /Users/sarthak/Desktop/fleet/starboard
pnpm fleet:audit-recommendation-context
pnpm fleet:extract-projects
```
