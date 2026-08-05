# Proposal: Specialist factory walkthrough

## Why

posttrainllm already publishes deep documentation, source code, benchmark
replays, and honest attempt records. A new visitor still has to assemble those
surfaces into a story on their own. The best part of the Qwen Chess learning
site is not its search implementation; it is the chaptered path from problem
to result, with source modules attached to the explanation.

## What changes

- Add a static `/learn` walkthrough of the Mac-local specialist factory.
- Organize the current `target -> data -> post-training -> eval -> package ->
  report` loop into readable chapters.
- Link every chapter to canonical documentation and exact source modules.
- Surface successful, failed, rejected, and still-unqualified case files.
- Add the walkthrough to primary navigation without replacing the deeper docs.
- Document the incumbent visual system so future evidence pages preserve it.

## In scope

- Editorial structure, static Astro markup, responsive styling, structured
  metadata, navigation integration, and links to existing public evidence.
- Current repository truth only; no new benchmark or model claims.
- A source index covering the smallest set of factory entrypoints needed to
  understand the complete loop.

## Out of scope

- New training, inference, cloud calls, benchmark runs, or model artifacts.
- Rewriting the canonical docs or duplicating every learning document.
- A course platform, accounts, progress tracking, or client-rendered search.
- Changing the site's established dark evidence-instrument visual language.

## Impact

- New files under `browser/src/pages/`, `openspec/changes/`, and the repository
  design register.
- Small navigation edits in the shared header and landing page.
- No production dependency, deployment, migration, or external write.
