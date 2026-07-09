---
name: B35 local-agent vertical PoC — code reviewer on a Mac
status: not-started
owner: unassigned
created: 2026-06-17
parent_plan: docs/PLAN.md §3 Tier B (B35 — future)
related_prds: B22-token-preserving-agent-trajectory.md, B26-deferred-tools.md,
              B28-composite-reward-framework.md, B29-trace-to-training-data.md,
              B30-prompt-reasoning-classifier.md, B31-gallery-and-project-pins.md,
              B32-eval-ci-gate.md
context: docs/sessions/2026-06-17-vercel-eve-and-local-agents.md
---

# PRD — Local-agent vertical PoC (code reviewer on a Mac)

## Goal

Prove the **local-only specialist agent** thesis on one concrete vertical:
a code reviewer that runs entirely on the user's Mac on a posttrainllm
fine-tuned 12B model, with zero cloud dependency, and beats (or matches
within ε) a frontier-cloud baseline on a fixed code-review benchmark.

If this PoC clears the gate, the wedge — *"agents Eve can't reach because
they're cloud-native"* — becomes a real product surface. If it doesn't,
we learn what the gap is before committing more roadmap area.

## Why now (post-Eve)

Vercel's Eve (June 2026) validates the agent-platform thesis at the
infra layer, but Eve and all its cloud-native peers (Cursor, Replit
Agent, Devin, Cognition) burn frontier-API tokens per invocation. None
serves the buyer who needs:

- **Zero data leaves the machine** (regulated industries: legal,
  healthcare, defense, finance, classified codebases).
- **Zero marginal cost** after training (high-volume internal use:
  large-scale code review on monorepos, batch refactor across services).
- **Offline operation** (air-gapped environments, intermittent
  connectivity).

posttrainllm already owns ~70% of the stack for this: QLoRA on 4-14B
(`posttrainllm sft`), serve (`posttrainllm serve` with B26 deferred tools), trace
recorder (B22), trace-to-training (B29), composite reward (B28), eval
gate (B32). What's missing is **one shipped vertical** that proves the
loop runs.

See [[feedback_posttrainllm_north_star]] — formula is (speed × accuracy) /
cost. Cost = 0 dominates as long as accuracy is in the ballpark. This
PoC is the experiment that measures the ballpark.

## Scope — in

### Phase 1 — baseline + benchmark (1 week)

- Pick the eval: **SWE-bench-Verified** code-review subset, or a
  derived code-review-specific harness over the same repos. Choose
  based on whether SWE-bench's review signal is actually informative
  (it's primarily a fix-the-bug task). Fallback: build a derived
  benchmark from `princeton-nlp/SWE-bench_Verified` rows where the
  task is "given diff, predict whether the PR was approved + flag the
  issues the reviewer flagged."
- **Frontier baseline**: Claude Opus 4.7 + gemini-3 + gpt-oss-120b on
  the same eval. Three frontier numbers establish the ceiling.
- **Open-baseline**: gemma-3-12b-it-qat-4bit (current champion per
  [[project_drilldown_2026_06_12]]) zero-shot. This is the lower bar
  the PoC must beat after fine-tuning.

### Phase 2 — specialist (1-2 weeks)

- Training data: PR-review pairs from public repos (the-stack-smol's
  cousin: PR + review-comment + accept/reject signal from GitHub Archive
  via `B22` style trajectory recording).
- Base: Gemma-3-12B-it-qat-4bit or Qwen3-Coder-14B (decision deferred to
  Phase 1 once we see baseline numbers).
- Approach: QLoRA + composite reward (B28 dims: identifies-bug,
  identifies-style, doesn't-hallucinate, format-compliant). Trained via
  `posttrainllm sft` then DPO on (preferred-review, dispreferred-review) pairs.
- Eval-gate (B32) blocks ship until the specialist matches the open
  baseline within ε on the held-out review eval AND beats it on the
  unhappy-path slice (PRs the reviewer rejected — the harder signal).

### Phase 3 — agent runtime (1 week)

- Thin agent harness: `posttrainllm agent` subcommand, with the verb model
  derived from B26's deferred-tools contract. Tools: `read_file`,
  `list_diff`, `comment_inline`, `summarize_review`. A 3-hop loop with
  composite-reward in-loop self-critique.
- **No new infra** — reuse `posttrainllm serve` for the runtime, B26 for the
  tool surface, B22 for trace recording (which then feeds the next
  training iteration via B29).
- Optional: VSCode extension or git-pre-push hook for distribution.

### Phase 4 — the loop closes (ongoing)

- Every real user review run → B22 trace → B29 trains the next iteration.
- B32 gate blocks regressions; B30 keeps the training-mix balanced.
- This is the **self-improving** part: the more reviews users do, the
  better the model gets, all on their Mac.

## Scope — out

- **Multi-agent orchestration** — that's Eve's pitch; we don't compete.
- **TypeScript SDK / cloud deployment** — Vercel's home turf.
- **Slack/Discord channels** — Eve has them; not a local-agent moat.
- **Other verticals** (legal review, SQL agent, refactor agent) — V2
  after this PoC validates the loop.

## Acceptance criteria

The PoC ships if **all** of these clear:

- [ ] Frontier baseline number recorded on the chosen eval (Phase 1).
- [ ] Open-baseline (zero-shot Gemma-3-12B) number recorded.
- [ ] posttrainllm-specialist beats open-baseline by ≥ 5pp on accuracy
      (matches the [[feedback_posttrainllm_north_star]] 5%/2-weeks bar).
- [ ] Specialist runs end-to-end on M5 Pro / 48 GB at ≥ 15 tok/s
      decode (informal target — the bar is "feels responsive").
- [ ] One real codebase (posttrainllm itself? Or a public OSS repo) has a
      PR review generated by the agent that a human reviewer rates ≥ 3/5
      on usefulness.
- [ ] Trace recording (B22) actually fires per agent step; the loop is
      provably closeable.

## The kill criterion (be honest about the negative result)

If, after 4 weeks of focused work, the specialist can't beat the
zero-shot open baseline by 5pp on the chosen eval **even on the
slice we picked for friendliness**, the local-only vertical thesis is
weakened enough to deprioritize. Either:

- The QLoRA-on-12B / distilled specialist loop genuinely doesn't move
  the needle vs zero-shot strong open models at our compute budget.
- We picked the wrong vertical and code review is too judgment-heavy.
- Frontier pulled too far ahead in 2026-H1 for a 12B specialist to
  matter.

In any of those cases, the answer isn't "build harder" — it's "publish
the negative result and keep posttrainllm narrow as a model factory, not an
agent company." Per [[feedback_research_first_doctrine]].

## Reference shape

| Phase | Wall-clock | Compute cost | Likely blocker |
|---|---|---|---|
| 1 — baseline + benchmark | ~1 week | $0 (local) + frontier API tokens for ceiling | eval choice |
| 2 — specialist training | ~2 weeks | M5 Pro time, sequential per [[project_parallel_training_lesson]] | training-data scarcity |
| 3 — agent runtime | ~1 week | $0 | tool-call reliability on 12B |
| 4 — self-improving loop | ongoing | $0 | real-user uptake |

## Open questions

- **Should the agent ship Pace-style as a Mac app or CLI-first?** Mac
  app gives distribution, CLI is faster to ship and matches the
  early-adopter buyer (developers).
- **License story for training data.** Hermes-FC + Apache-licensed PR
  corpora; do not let an APIGen-MT-style CC-BY-NC license through per
  [[project_specialists_research_2026_06_09]].
- **Distribution.** If the PoC succeeds, is it a public model in the
  gallery (B31), a paid Pace-style app, an OSS release with sponsorship
  arm, or all three?

## What this PRD is NOT

A commitment to ship. It's a kill-or-validate experiment. If the
4-week timebox runs out without clearing the bar, B35 is closed and
the learning is published as a session retrospective per the user's
documentation-as-first-class doctrine.
