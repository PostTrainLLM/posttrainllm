# SEO sprint — PostTrainLLM

Initialized 2026-09-22 from the Fleet scoreboard (`seo-scoreboard.mjs
--project posttrainllm`): **2,172 impressions, 3 clicks, mean position ~23**
over 28 days — the strongest organic base in the Fleet. The site already has
demand; the work is converting impressions into clicks with pages that answer
the exact queries being served.

## Demand evidence (Search Console, 28d)

| Cluster | Queries seen | Impressions | Position |
| --- | --- | --- | --- |
| Apple Foundation Models | `apple foundation model(s)` + ~10 variants (`framework`, `benchmarks`, `context window`, `supported devices`, `on device`) | ~40+ | 58–89 |
| Mac fine-tuning / LoRA | `13b ppo lora` and existing `fine-tune-llm-on-mac`/`mlx-lora` coverage | small, well-covered | — |
| Benchmarks | `aider polyglot benchmark leaderboard official 2026` | ~1 | 71 |

## Phases

- [x] **Phase 1 — Apple Foundation Models page.** `/apple-foundation-models`
  publishes the measured verdict from `docs/learn/apple-on-device-foundation-models.md`
  (BFCL agentic 25%/~0%, planner 13%, OOS-refusal ~95%, 4096-token context
  catch-22). This is the highest-demand cluster and we hold genuinely unique
  measured evidence — nobody else publishes these numbers.
- [ ] **Phase 2 — per-model eval pages.** `eval-leaderboard` data →
  `evals/[model].astro` pages (Qwen3-4B variants, Gemma, distilled 1.7B,
  30B-A3B) with per-model scores, tok/s, RAM. The corpus already exists in
  `browser/src/data/benchmarks/`.
- [ ] **Phase 3 — per-recipe pages.** The 18 recipe contracts →
  `recipes/[slug].astro` so each recipe is independently indexable.
- [ ] **Phase 4 — experiment archive depth.** `experiments.astro` exists as
  an index; per-experiment pages from `experimentArchive.ts` give each of
  the ~76 runs a canonical URL.

## Measurement

- Site Health `search` family: apple-foundation-models cluster position
  (currently 58–89; target <30 within ~6 weeks of indexing).
- Indexing: `pnpm --dir site-health indexing submit --project posttrainllm
  --sitemap` after deploy.
