---
title: "SEO depth plan — flagship"
description: "Mac-local post-training authority plan for posttrainllm.com: artifact datasheets, train-on-Mac runbooks, benchmark leaderboards."
---

# posttrainllm SEO depth plan — flagship

Source of truth: `~/.fleet` ledgers via `seo-scoreboard.mjs` (28-day window
ending 2026-09-18): **2,172 imp · 3 clicks · avg pos 23** — indexed and
visible, parked deep on queries where we mostly can't win.

## What the queries say

| Query shape | Imp | Pos | Verdict |
|---|---:|---:|---|
| "apple foundation models" variants | ~20 | 62–89 | Apple's turf — ignore |
| "13b ppo lora" / "aider polyglot benchmark" | 4 | 71–89 | Our real niche, ranked deep |

We surface for generic Apple/model queries we can't win. The winnable niche
is **Mac-local post-training**: LoRA, GRPO, distillation, and running/
evaluating small specialists on Apple Silicon — which is literally the
product (AGENTS.md north-star: "win on the Mac").

## The play: own the Mac-local post-training niche with artifact receipts

The site already has the structure — `/artifacts/*` (366 URLs cataloged),
`/benchmarks/{arena,chess,game-2048}`, `/articles/*`. Depth = every artifact
page becoming a real datasheet.

### Phase 1 — artifact pages into datasheets (highest leverage)

- Each `/artifacts/<name>` page gets: base model, method (LoRA/GRPO/distill),
  dataset, eval scores vs. base, size/VRAM, "run it on your Mac" commands,
  license. Today's pages mostly describe; datasheets get cited and linked.
- Prioritize the ones that already exist for real runs: `qwen3-4b-*`,
  `vibethinker-3b-*`, `pace-intent-router-v8`, `qwen06-sql-routed-v1`.

### Phase 2 — the "train on Mac" how-to series

- Real runbooks from `benchmark-runs/` + `evals/`: "fine-tune a 4B model on
  an M-series Mac", "LoRA vs full fine-tune on Apple Silicon — real numbers",
  "evaluate two runs without moving the target" (article exists — expand the
  series). Each grounded in an actual run with logs linked.

### Phase 3 — benchmark leaderboards as linkable assets

- `/benchmarks/*` exists — surface per-model results as sortable tables with
  raw data downloadable. "Mac-local LLM benchmark" queries are the ones where
  a hobbyist-built leaderboard can beat corporate docs.

### Phase 4 — indexing follow-through

- 341 queued URLs churning via the daily agent. Check
  `pnpm --dir site-health indexing status --project posttrainllm` — artifact
  pages landing `Discovered — currently not indexed` need the datasheet
  treatment (thin catalog entries don't index).

## Rules

- Never publish a benchmark number that isn't in `benchmark-runs/` or
  `evals/` — the whole positioning is receipts.
- Learning-project honesty is the brand: "here's what worked on one Mac" is
  more credible than pretending to be a lab.
- Register shipped pages: `seo-scoreboard.mjs register --project posttrainllm
  --lane editorial|programmatic --summary "…" --target <url>`.
