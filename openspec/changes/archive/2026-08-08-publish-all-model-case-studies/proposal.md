# Proposal: Publish case studies for every public model

## Why

PostTrainLLM has six public model repositories on Hugging Face, but the website
currently gives only two of them first-class model case-study pages. The other
releases are compressed into an archive index, and the Pace intent router is
missing from the public artifact registry despite having the strongest local
runtime evidence and a later sealed-eval rejection.

Public weights without an evidence narrative are not a useful publication.
Every released model should explain what it is, what was measured, what failed,
what can be concluded, and what remains unknown. Hugging Face request counters
must not be presented as unique users or verified adoption.

## What changes

- Reconcile the public model inventory against the six live
  `posttrainllm/*` Hugging Face repositories.
- Give every published model its own `/artifacts/<slug>` case study using the
  existing static artifact system.
- Preserve the two existing Qwen case studies and add first-class entries for
  the Pace intent router, the failed multibackend distillation, the plain
  VibeThinker MLX conversion, and the unevaluated agentic distillation.
- Update the artifact registry and archive index so the public count and model
  states agree.
- Publish failure, rejection, and missing-evidence cases as plainly as wins.

## In scope

- Existing repository evidence and public Hugging Face metadata.
- Static Astro case-study content, artifact navigation, canonical docs, and
  generated sitemap/Markdown/agent-readable surfaces.
- Explicit decision states and next evidence actions for all six models.

## Out of scope

- New training, inference, benchmark runs, downloads, or heavy model loads.
- Claiming unique users, real adoption, or full-weight downloads from Hub
  request counters.
- Promoting archived or rejected models to shipped product defaults.
- Rewriting model weights or adding dependencies.

## Impact

- Content additions in `browser/src/artifacts.ts` and
  `docs/factory/public-artifacts.md`.
- Generated public-site output changes after the normal build.
- No production runtime, model, migration, dependency, or secret changes.
