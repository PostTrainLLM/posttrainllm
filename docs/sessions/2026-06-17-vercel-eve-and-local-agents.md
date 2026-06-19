# Vercel Eve and the local-agent wedge

Date: 2026-06-17 (afternoon).
Companion to [the morning's step-back](./2026-06-17-stepback-inventory-roi.md).
Captures the strategic decision triggered by Vercel's Eve launch
([blog](https://vercel.com/blog/introducing-eve), public preview June 2026).

## What changed today

Vercel shipped **Eve** — an open-source agent orchestration framework
on top of frontier models (Claude primary). Filesystem + TypeScript +
markdown config, Workflow SDK for durability, sandboxed exec,
OpenTelemetry traces, multi-channel (Slack/Discord/Teams), eval-based
CI/CD, multi-agent governance for orgs. Not a model — an
infrastructure layer.

Vercel doesn't ship things at this scale unless they believe a
category is forming. The agent-platform thesis is **validated** at
the cloud-infrastructure layer.

## The question

User asked: *"what about we expand into building ai agents? or too far?"*

## The answer (and why)

**Don't compete with Eve.** From a Mac-first Swift+Python stack, we
lose every comparison to the cloud-native incumbent with edge
infrastructure and the TypeScript ecosystem. Same lesson as
[[feedback_library_api_deferred]] — don't pitch packaging around
nothing.

**Do lean into the wedge Eve can't reach.** Eve and every peer
(Cursor, Replit Agent, Devin, Cognition) burns frontier-API tokens
per invocation. None serves the buyer who needs:

1. **Zero data leaves the machine** — regulated industries (legal,
   healthcare, defense, finance, classified codebases).
2. **Zero marginal cost after training** — high-volume internal use
   on monorepos, batch refactor across services.
3. **Offline operation** — air-gapped environments, intermittent
   connectivity.

tinygpt already owns ~70% of the stack for this wedge:

| Piece | Status |
|---|---|
| QLoRA on 4-14B (`tinygpt sft`) | shipped |
| Distillation from 30B teacher | shipped |
| Trace recorder (B22) | **PRD only, not yet implemented** (corrected 2026-06-17) |
| Deferred tools in `serve` (B26) | scaffolding shipped, BFCL gate pending |
| Composite reward framework (B28) | scaffolding shipped |
| Trace-to-training-data (B29) | PRD only — blocked on B22 |
| Reasoning-depth classifier (B30) | ✅ shipped + verified 2026-06-17 |
| Eval CI/CD gate (B32) | scaffolding shipped, multi-suite pending |
| Gallery + project pins (B31) | scaffolding shipped |

What's missing is **one shipped vertical** that proves the loop runs.

## The decision

Open [[B35-local-agent-vertical-poc]] as a future kill-or-validate
experiment. Code reviewer on a Mac, on a tinygpt-fine-tuned 12B, no
cloud. Four-week timebox, explicit kill criterion: if the loop can't
beat zero-shot open baseline by ≥5pp, publish the negative result and
keep tinygpt narrow as a model factory.

## What this is NOT

A pivot. The decision is to **not** pivot tinygpt into being an agent
company in the Eve sense. The model-factory north star
([[feedback_tinygpt_north_star]]) is unchanged. B35 is one
experiment on top of that factory — the factory ships either way.

## What's NOT in B35 scope

- **TypeScript SDK / cloud deployment.** Vercel's home turf.
- **Slack/Discord/Teams integrations.** Eve has them; not our moat.
- **Multi-agent governance.** Eve's pitch; not the wedge.
- **A generic agent framework.** B35 is one vertical, end-to-end. The
  framework falls out only if multiple verticals demand it.

## Connection to today's commits

- `05124f3` (data pulls + B30): the infra arc that makes B35
  feasible. D3 + D5 pulls give us MS-MARCO and MATH-500 (eval
  diversity); B30 reasoning classifier balances the training mix
  that a future code-review specialist will SFT on.
- `2d931ef` (B35 PRD): the experiment itself, parked for future.

## What changes for tinygpt's day-to-day

Nothing immediate. The factory keeps shipping. B35 sits in §3 Tier
B as an explicit option that future sessions can pick up. When the
training-data side for code review is ready (PR-review corpus
collection), B35 unparks.

## Related notes

- [[project_competitive_teardown_2026_06_09]] — Dottie threat
  analysis; Eve confirms the same "platform-becomes-the-category"
  pattern in the *agent* layer.
- [[feedback_research_first_doctrine]] — research current state
  before committing. The Eve post is current-state research that
  changed our view.
- See sibling files in `docs/sessions/` for chronological context.
