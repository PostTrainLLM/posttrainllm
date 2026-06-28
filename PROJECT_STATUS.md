# tinygpt — PROJECT STATUS

Last updated: 2026-06-28

## Why/What

TinyGPT is a Mac-first platform for building and upgrading local specialist models: from-scratch GPT-2 research in the browser (WASM/WebGPU), native Swift/MLX CLI (~30 subcommands), SwiftUI Mac app, and Hugging Face model support. For **Pace**, TinyGPT is the development-time factory and eval lab (planner LoRA artifacts, grammar/eval assets, dataset scripts, porting helpers). Pace owns production runtime integration; shipped Pace must not depend on `tinygpt serve` or a localhost daemon.

Live browser playground: [tinygpt.sarthakagrawal.dev](https://tinygpt.sarthakagrawal.dev)

**Specialist north star:** Qwen3-4B-Instruct-2507 bf16 default general Pace planner (lock 2026-06-19). First registered specialist package: `specialists/qwen3-4b-file-ops-distilled` (model card, eval report, artifact lock, MLX validation helper).

## Dependencies

| Surface | Location | Entry |
|---------|----------|-------|
| Native CLI | `native-mac/Sources/TinyGPT/` | `xcrun swift build -c release` → `.build/release/tinygpt` |
| Mac app | `native-mac/Sources/TinyGPTApp/` | SwiftUI shell over CLI |
| Browser site | `browser/` (Astro) | `cd browser && npm run dev` / Cloudflare Pages deploy |
| WASM/WebGPU | `wasm/`, `browser/src/` | `bash wasm/build_wasm.sh` |
| Eval scripts | `scripts/`, `evals/` | `scripts/eval-planners.py`, `scripts/fake_pace.py`, `evals/*-smoke.sh` |
| PRD backlog | `docs/prds/` | 65 active briefs indexed in `docs/prds/README.md` |
| Master plan | `docs/PLAN.md` | Shipped/skipped/TODO canonical reference |

**Key checks:** Swift unit tests · `evals/eval-gate-smoke.sh` (no-GPU path) · `evals/quickstart-smoke.sh` · `browser/scripts/check_gallery_drift.mjs` · CI workflow on push

**Headline subcommands:** `train` · `sft` · `dpo` · `distill` · `serve` · `agent` · `export-mlx` · `eval-gate` · `eval-bfcl` · `eval-tau-bench` · `run-lm-eval` · `eval-humaneval` · `judge` · `traces-to-data` · `reasoning-classify` · `quickstart`

```
                    ┌─────────────────────────────────────┐
                    │  Browser playground (Astro + WebGPU) │
                    │  GPT-2 from scratch · gallery · docs │
                    └──────────────────┬──────────────────┘
                                       │
┌──────────────────────────────────────┴──────────────────────────────────────┐
│  native-mac: MLX-Swift CLI + TinyGPTApp                                      │
│  train → sft/dpo/distill → eval-gate → serve/agent → export-mlx             │
│  Eval moat: E0 schema · BFCL · τ-bench · lm-eval · HumanEval sandbox        │
│  Agent: OpenAI/Ollama serve · FSM JSON · cloud-escalate · .atraj traces     │
│  Interp: SAE · ROME · MEMIT · tuned lens · activation patching              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ factory outputs (grammar, LoRA, eval assets)
                                       ▼
                              Pace production runtime
                              (must NOT call tinygpt serve)
```

| Concern | Detail |
|---------|--------|
| Build | Xcode 27+ Metal toolchain; `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift build -c release` |
| GPU lock | `~/.cache/tinygpt/gpu.lock` — respect cross-process lock before long trains |
| Datasets | `~/.cache/tinygpt/datasets/` — inventory in `docs/dataset-inventory.md` |
| R2 | `tinygpt` CF R2 push/pull for checkpoint sharing (zero egress) |
| Eval smoke | `evals/eval-gate-smoke.sh`, `evals/quickstart-smoke.sh`, `evals/traces-to-data-smoke.sh` |
| CI | `.github/workflows/ci.yml` — Swift tests, browser drift check, eval-gate no-GPU |
| Browser deploy | Cloudflare Pages from `browser/dist` |
| PRD protocol | Agents must not touch `TinyGPT.swift` dispatch table — submit diff line for maintainer merge |
| Pace boundary | Never wire production Pace to `localhost:8090` or `tinygpt serve` |

## Timeline

| Phase | Milestone | Status |
|-------|-----------|--------|
| **Phases 1–4** — ML foundations → transformer → training/debug | PyTorch reference baseline, training loop, eval suite, TinyGPT from scratch | Complete |
| **Phase 5** — LoRA & PEFT | LoRA/adapter paths in factory; full PEFT bundle in Swift | Complete |
| **Phase 6** — Data engineering | Dataset manifests, HF integration, GitHub fetcher, Magpie synthesis | Complete |
| **Phase 7** — Browser systems | WASM SIMD path, OPFS persistence, Worker training shell, gallery model loader | Complete |
| **Phase 8** — WebGPU | WebGPU training pipeline, FA2 forward in WGSL, f16/coop-matrix gated fast paths; 2.6× → 12.1× speedup vs WASM SIMD | Complete |
| **Phase 9** — Evaluation & safety | Browser BPE scorer, benchmark runner, numerics-gate framework, eval methodology docs | Complete |
| **Phase 10** — Public readiness | Landing, playground, roadmap, devlog, inference, training-dashboard, doc consolidation | Complete |
| **Mac runtime Wave 2.6** (2026-05-31) | 30+ MLX subcommands, serve/agent, Ollama-compat, screen AX tree, Continue.dev provider | Shipped |
| **Mac specialist platform reframe** (2026-06-06) | Product thesis: Mac factory for building/upgrading specialists; Tier 1–4 backlog in `docs/sessions/2026-06-06-mac-specialist-platform.md` | Active north star |
| **Eval methodology gate** (2026-06-08) | `scripts/fake_pace.py`, `docs/learn/eval-methodology-2026-06-08.md`; baseline re-stamping, `--passes`, uncertainty reporting | Shipped |
| **Planner lock** (2026-06-19) | Qwen3-4B-Instruct-2507 bf16 default Pace planner; `docs/planner-lock-2026-06-19.md` | Shipped |
| **Factory/eval PRD wave** (2026-06-20) | 46 shipped PRD themes; 51 completed briefs removed from `docs/prds/`; first specialist package registered | Shipped |
| **Active research backlog** | 65 PRDs in `docs/prds/` — north-star specialists, agent protocol, Pace factory, interpretability, RL loop, Tier 5 frontier | In flight |

## Products

| Surface | Role |
|---------|------|
| Browser playground | [tinygpt.sarthakagrawal.dev](https://tinygpt.sarthakagrawal.dev) — GPT-2 from scratch, gallery, docs, eval leaderboard, SAE timeline |
| Native CLI | ~30 subcommands — train, sft, dpo, distill, serve, agent, eval-gate, export-mlx |
| Mac app (TinyGPTApp) | SwiftUI tabs: Sample, Train, Eval, Trace, Interp, Serve |
| Specialist packages | `specialists/qwen3-4b-file-ops-distilled` — first registered factory output |
| Pace factory outputs | Grammar assets, planner LoRA artifacts, dataset scripts, eval assets (dev-time only) |

## Features (shipped)

### Original browser/research roadmap (Phases 1–10) — complete
- PyTorch reference baseline, training loop, LoRA, eval suite, WASM SIMD path, WebGPU training pipeline, checkpointing, metrics dashboard, public repo readiness.
- WebGPU speedup curve 2.6× → 12.1× vs WASM SIMD as `d_model` grows; loss drift vs WASM reference 1.1–2.5%.
- Landing, playground, roadmap, devlog, inference, training-dashboard, doc consolidation at `/docs/[slug]`.
- Gallery model loader, browser BPE scorer, benchmark runner, OPFS persistence, FA2 forward in WGSL, f16/coop-matrix gated fast paths with numerics-gate framework.

### Mac runtime + CLI (30+ subcommands, MLX-Swift)
- Pretrain, finetune, SFT (LoRA/DoRA/QLoRA/PEFT bundle: VeRA, LoftQ, AdaLoRA, RsLoRA, PISSA, LoRA-FA, LayerDrop), DPO/SimPO/KTO/ORPO, distill, ES, Magpie synthesis, sequence packing, NEFTune, gradient clipping, z-loss, embedding tying, gradient checkpointing, QAT, persistent tokenized cache.
- KV cache (GQA, in-place, persistent), flash-attention forward, speculative decoding (vanilla + Medusa + EAGLE-2), prefix/prompt caching, Streaming-LLM sink, KIVI KV quant, MTP inference, sliding window, ALiBi, differential attention, YOCO cross-layer KV sharing.
- Quantization: HQQ, GPTQ, AWQ/GPTQ safetensors readers, GGUF inspect, SmoothQuant, unstructured/structured prune, LASER.
- Optimizers: AdamW, Lion, Sophia, Muon, Adafactor, GaLore.
- Architecture variants: standard transformer, MoE (soft routing), Mixture-of-Depths (soft gate), MQA/GQA.
- Training stability: embedding RMSNorm, DeepNorm, layer-wise LR decay, cosine warmup, BPE-dropout, WSD schedule (B11), loss-spike recovery (B12).
- Cold-start bundle, GPU lock, CF R2 save/load, `tinygpt serve` (OpenAI + Ollama-compat), `tinygpt agent` (multi-turn, tools, cloud-escalate), JSON-mode FSM constrained generation, cloud API client + `tinygpt escalate`.
- Screen tree (AX accessibility), Continue.dev provider surface, tool-call extractor trainer scaffold, datasets (`list-datasets`, `download-dataset`, HF integration, GitHub fetcher, extractor-data, Indic eval).
- Interpretability CLI: linear probes, ROME, MEMIT, tuned-lens trainer, SAE tooling paths documented in `docs/interpretability.md`.
- ANE M8 layer-chunked Core ML chain (~17 tok/s on Qwen3 28-block path per PLAN.md).

### 46 factory/eval PRD themes shipped (2026-06-20 cleanup)
Summarized by theme — 51 completed briefs removed from `docs/prds/`; 46 themes retained in status record:

> ⚠️ This is a cleanup-summary of *removed* briefs and **overstates a few still-active PRDs** (e.g. B11/B12/B14 are partial, B15 is unstarted, C3 is done — none were removed). For the code-verified status of every **active** PRD, see **[docs/prds/STATUS.md](docs/prds/STATUS.md)** — it is canonical.

1. **E0 shared eval schema** — `tinygpt eval-compare`, Codable JSONL rows, by-step/by-model/by-task views.
2. **E1 BFCL harness** — `eval-bfcl` boots serve, runs gorilla BFCL subprocess, 10 default categories.
3. **E2 τ-bench harness** — `eval-tau-bench`, retail + airline envs, configurable user simulator.
4. **E3 lm-eval MLX routing** — `run-lm-eval` HF and tinygpt-serve local-completions paths; `scoreLogprobs` for echo+logprobs.
5. **E5 HumanEval + sandbox** — `eval-humaneval` + Rust `humaneval-sandbox` (macOS sandbox-exec).
6. **E7 judge shim** — `judge` pairwise and rate modes for JSONL preference/rating workflows.
7. **E8 train-time eval hook** — `--eval-every` / `--eval-tasks` in train; background lm-eval per checkpoint → `*-evals.jsonl`.
8. **Eval runbook scripts** — `score-checkpoint.sh`, `score-run.sh`, `score-baselines.sh`, `sae-run.sh`.
9. **Browser eval leaderboard** — `/eval-leaderboard.astro` drag-drop E0 JSONL comparison UI.
10. **Browser SAE timeline** — `/sae-timeline.astro` drag-drop B13 timeline charts.
11. **Rust parquet decoder** — replaces Python parquet_to_txt for dataset ingestion.
12. **Rust HF downloader** — parallel shard fetch with resume/retry.
13. **HumanEval sandbox crate** — E5 execution isolation on macOS.
14. **B11 WSD LR schedule** — warmup-stable-decay replaces cosine default in train path.
15. **B12 loss-spike recovery** — grad-norm spike detector, auto-rollback + LR drop (on by default).
16. **B14 speculative decoding training** — `train-heads` Medusa/EAGLE paths + inference byte-equality gate at T=0.
17. **B15 layerwise LR decay** — `--llrd γ` depth decay on sft/dpo/finetune paths.
18. **B22 trajectory recorder** — `agent --trajectory-dir` writes `.atraj` per rollout with token IDs; unblocks trace loop.
19. **B23 agent eval protocol (partial)** — `eval-gate --passes K`, budget metadata JSON, mean±CI95 in gate-result; sandbox enforcement remaining.
20. **B26 deferred tools (partial)** — `serve --tool-mode {full,deferred}`, `get_tool_info` meta-tool, hop metrics, parity runner script; BFCL parity gate pending.
21. **B28 composite reward (partial)** — `CompositeReward` typed multi-dim framework + unit tests; DPO/ES/GRPO integrations pending.
22. **B29 trace→training-data v1** — `traces-to-data` SFT mode, tool-echo drop, dedup, MinHash near-dedup; DPO mode pending.
23. **B30 reasoning classifier** — `reasoning-classify` bag-of-trigram 4-class; macro-F1 1.0 on fixture heldout.
24. **B31 gallery + project pins (partial)** — `gallery-schema.js` kind discriminator, `tinygpt.project.json`, Swift mirrors, first specialist package registered.
25. **B32 eval CI gate (partial)** — `eval-gate` non-zero exit on regression, GitHub Action recipe, no-GPU `--candidate` path; live GPU multi-suite run pending.
26. **B33 quickstart (partial)** — `quickstart` RecipeResolver + dry-run + smoke; live train→sample GPU path wired.
27. **C3 DoRA on-disk format** — TGLA v2 magnitude vectors in adapter roundtrip.
28. **Factory grammar + prompt cache** — pace grammar assets, v9 serve precomputes tokenizer byte tables for faster first-token grammar latency.
29. **LoRA/QLoRA/DoRA completeness** — full PEFT bundle in `PeftVariants.swift` gated through `sft`.
30. **Mini-router / tool-extractor trainer** — `train-extractor` pipeline for BFCL query→tool pairs.
31. **Tokenizer trainer path** — BPE training integrated in factory toolchain.
32. **MTEB / embedding eval hooks** — embedding evaluation paths in factory eval matrix.
33. **Domain adapt + synthesis** — Magpie synthetic instructions, domain-adapt helpers in dataset/manifest docs.
34. **Quant inference paths** — int4/int8 via MLXNN.quantize, HQQ/GPTQ CLI, serve quantize experiments documented.
35. **Reranker scaffolding** — reranker training/inference hooks in factory completeness wave.
36. **App polish batches** — Mac SwiftUI app tabs (Sample, Train, Eval, Trace, Interp, Serve) wired to CLI.
37. **Cloud-escalate in AgentLoop** — regex replaced by trained defer signal path scaffolding (B5 PRD tracks full training).
38. **Planner lock artifact** — Qwen3-4B-Instruct-2507 bf16 default; `docs/planner-lock-2026-06-19.md`.
39. **Pace factory v9/v10 inputs** — grammar helpers, dataset scripts, v9 tokenizer byte-table precompute for serve.
40. **Eval methodology gate** — `scripts/fake_pace.py`, `docs/learn/eval-methodology-2026-06-08.md`; baseline re-stamping, `--passes`, uncertainty reporting.
41. **Eval-gate no-GPU path** — `--candidate` for CI without Metal; optional B23 budget metadata attachment.
42. **Adam state persist** — checkpoint state for determinism harness dependency (C9 precursor).
43. **CI hardening** — gallery drift check, committed WASM artifact guards, eval smoke scripts in `evals/`.
44. **First specialist registration** — `specialists/qwen3-4b-file-ops-distilled` model card + eval report + artifact lock.
45. **Multi-turn eval executor** — agentic multi-turn eval plumbing (merged 2026-06 refactor pass).
46. **Wave 2.6 product surfaces** — Ollama-compat provider, screen AX tree, extractor scaffold, cloud-escalate wiring.

### Partial ships on still-active PRDs (not counted in 46 removal set)
- B26 BFCL parity gate — mechanical runner exists; live specialist gate pending.
- B28 reward integrations into training loops pending.
- B31 `pull`/`validate` CLI extensions + browser filter UI pending.
- B32/B33 — live GPU verification runs pending self-hosted runner.

## Todo / Planned / Deferred / Blocked

Active backlog: **60 on-disk PRDs** in `docs/prds/`. Code-verified breakdown (2026-06-20 audit, see **[docs/prds/STATUS.md](docs/prds/STATUS.md)** — canonical): **4 done · 26 partial · 24 not-started · 6 non-task**. So ~50 carry real remaining work. The thematic buckets below are a planning narrative; trust STATUS.md for per-PRD truth (frontmatter is stale in ~17 files). Do not reopen the shipped Phase 1–10 browser roadmap.

### Planned — 1. North-star specialists (8 PRDs)
Train and ship specialists that prove the Mac-first factory thesis end-to-end. **A1** first tool-calling specialist (qwen3-4b + LoRA, +3pp BFCL ship gate) is the gating item; consumes E1/E8 + B23 protocol. Follow-ons: **B1** second domain shell (cookie-cut A1), **B6** Mac app Factory tab (drop data → train → eval → deploy), **B8** Indic/multilingual specialist (blocked on A7 MILU baseline), **B25** ScaleDown compression specialist (needs E6), **B35** local-agent vertical PoC (code reviewer kill-or-validate experiment). **Capability-retention** measures breadth erosion when specializing (§8.4–8.5 gates).

### Planned — 2. Agent protocol & eval discipline (9 PRDs)
Router family **B2–B7** (mini-router on BFCL, bake-off vs FSM-only, FSM injection, cloud-escalate training **B5**, specialist routing **B7**). **B23** completes sandbox/resource enforcement and SWE-mini rows. **B26** closes BFCL deferred-tools parity gate. **B32** live GPU eval-gate on self-hosted runner. **B33** live quickstart GPU run + eval-vs-base delta. **B34** batched eval runtime for overnight sweeps. **multi-turn-agentic-eval** extends harness for multi-hop agentic scenarios. Near-term chain: live GPU eval-gate → B23 completion → B26 BFCL parity → B29 trace loop once scores are auditable.

### Planned — 3. Factory / Pace integration (12 PRDs)
Pace-facing factory work: **factory-vision-specialist** + **factory-vision-m4-impl-plan** + **factory-vision-m4-architecture-decision**; **factory-planner-v7-tools-in-prompt**; **pace-planner-v11-training-data** + **pace-planner-v11-ship-gate**; **pace-task-loop-v1**; **specialist-pace-planner**; **factory-completeness-tracker**; **gepa-prompt-evolution**; **qlora-large-model-finetune**. Goal: planner artifacts and grammar ship through Pace without localhost `tinygpt serve` dependency.

### Planned — 4. Training quality & optimizers (8 PRDs)
**B10** FineWeb-Edu-style quality classifier + corpus filter. **B11** WSD schedule (partial — curve + `--lr-schedule wsd` ship; configurable decay-shape + default-flip pending). **B12** loss-spike recovery (partial — observe-only detector ships; auto-rollback controller pending). **B14** speculative decoding (partial — offline `sample --draft` ships; serve integration + T=0 numerics gate pending). **B15** LLRD on sft/dpo/finetune (not-started — only pretrain-side `--lr-layer-decay` exists). **B16** M5 NA prefill bench (Apple claimed speedup verification). **B18** nanochat `--depth N` auto-HP derivation. **B21** micro-automixer Dirichlet+EI ratio search before specialist training.

### Planned — 5. Interpretability (3 PRDs)
**B13** `interp-replay` across checkpoint history → timeline JSONL (save-every shipped; batch driver pending). **B17** SAELens/Neuronpedia one-way `.sae` exporter. **B19** group SAE (~4× cheaper per-layer training). Pairs with eval-gate emergence curves (E0/E8).

### Planned — 6. RL / trace-improvement loop (5 PRDs)
**B28** wire composite reward into DPO/ES/GRPO training. **B29** v2: judge subprocess (E7), `--mode dpo`, external observability ingest. **self-improving-agents** closed loop (act→score→learn→curriculum; teacher-free ReST on file-ops env). **game-rl-environment-poc** in-fleet game NPC GRPO. **local-model-arena-selfplay** TextArena-style self-play RL. Depends on auditable B22/B29 traces and B23 budgets.

### Planned — 7. Distribution & onboarding (2 PRDs)
**B31** gallery CLI extensions (`pull`, `validate`), browser UI filter, per-project pin adoption across fleet repos. **B33** laptop finetune onboarding polish (from-scratch raw-text path, auto-pull gallery ids, quantitative eval-vs-base in quickstart output).

### Planned — 8. Harness, polish & measurement (7 PRDs)
**C3** DoRA on-disk roundtrip gaps if any remain vs LoRA. **C4** BPE path for mini-router trainer. **C5** 30-min sustained decode bench + powermetrics thermal sidecar. **C9** bit-exact step-N replay harness (Adam-state persist). **C10** `/train-viewer.astro` drag-drop live training charts. **B9** J/token energy leaderboard column. **E6** `eval-scaledown` ScaleBench wrapper (unblocks B25).

### Planned — 9. Platform / inference research (6 PRDs)
**macos26-int8-ane-handoff-port** ANE int8 handoff. **quantized-inference-swift** production quant serve path (done — both phases ship). **vlm-ab-uivenus-vs-qwen3vl** VLM A/B (runner built; port decision not yet recorded). **tinygpt-product-thesis** positioning alignment. **multi-turn-agentic-eval** cross-cutting harness hardening.

### Planned — 10. Tier 5 research frontier (7 PRDs)
Ordered exploratory work: **5.1** reasoning on 22M (GRPO/DAPO negative-result artifact). **5.2** test-time compute scaling (Snell curve). **5.3** vision-language toy (LLaVA-style). **5.4** diffusion LM micro. **5.5** sparse MoE Metal kernels (blocked upstream). **5.6** TTS toy (post-5.3). **5.7** explainer-video model (post A1–B8 + 5.3).

### Deferred
- Original Phases 1–10 browser roadmap — complete; do not reopen.
- WebNN full transformer graph, alternate attention experiments until measured need exists.
- Hosted model service, commercial API, auth/SSO/team workspace scope.
- Pace runtime over TinyGPT HTTP/localhost — `serve` stays dev/eval only.
- New LoRA/specialist training without baseline-aware eval-gate result.
- Public HN/HF launch until ≥1 specialist beats fair baseline on declared gate.
- Tier 5 frontier items until north-star specialist (A1) and eval discipline (B23/B32) are green.

### Blocked / Known gaps
- No shipped vertical specialist has cleared the full BFCL + unhappy-path gate chain yet (A1 in flight).
- B26/B32/B33 partial ships need live GPU verification — CI no-GPU path is green, Metal path is operator-dependent.
- Specialist track measured depth tax: out-of-domain breadth regressed 60% → 42% on catastrophic-forgetting gate (v11→v12); tracked, not papered over.
- QLoRA real-quantized autograd blocked in MLX-Swift — fake-quant pedagogical path only, no memory win.
- Sparse MoE / MoD hard routing blocked upstream (`scatter_add`); soft routing shipped as workaround.
- 51 removed PRD briefs are recoverable from git history only — active index is `docs/prds/README.md`.
