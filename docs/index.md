---
title: "posttrainllm docs"
description: "Mac-local LLM specialist factory — training, inference, evals, systems notes, and learning paths."
---

# posttrainllm documentation

posttrainllm is a **Mac-local specialist factory**: target → data →
post-training → eval → package → report. These docs are the committed source
of truth; this site is the presentation + search layer over them.

Prefer the markdown mirrors (append `.md` to any URL) and `llms.txt` for
agents. The full corpus is also at `/llms-full.txt` after build.

## Start here

- [How it works](/architecture/how-it-works) — learning-first end-to-end walkthrough of the factory loop, runtime, and design decisions
- [Project status](https://github.com/PostTrainLLM/posttrainllm/blob/main/PROJECT_STATUS.md) — current state, active scope, shipped vs parked surfaces
- [Active queue](/NEXT) — what to do next and what not to touch
- [Factory contract](/factory/README) — run schema, eval protocol, packaging, reports
- [Capability matrix](/capability_matrix) — what the factory CLI actually does
- [Learn path](/learn) — ground-up curriculum and concept references
- [Data inventory](/data_inventory) — datasets and provenance
- [Frontier-parity result](/learn/tool-calling-frontier-parity) — the strongest measured claim

## Navigation

| Surface | Use it for |
|---|---|
| [`/factory`](/factory/README) | Run schema, eval protocol, packaging, public artifacts, enforcement |
| [`/techniques`](/techniques/README) | Method-vs-recipe registry and target-specific technique backlogs |
| [`/attempt-ledger`](/attempt-ledger) | What worked, failed, regressed, or remains untried |
| [`/external-products-reviewed`](/external-products-reviewed) | Products, papers, startups reviewed and what we stole or rejected |
| [`/recipes`](/recipes/README) | Closed-loop recipes (traces → SFT → specialist, distillation, eval-gate) |
| [`/parked`](/parked/README) | Paused lanes and why they are paused |
| [`/doc-status`](/doc-status) | Status label (active/evidence/reference/learning/parked/superseded/archive) for every major doc |

For the maintainer golden path through the docs (the order a new reader should
read them in), see [`README.md`](/README). When docs disagree, the conflict
rule lives in [`doc-status.md`](/doc-status).
