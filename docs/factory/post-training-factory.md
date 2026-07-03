# Post-Training Factory Positioning

TinyGPT's active center is a Mac-local specialist factory, not a generic
fine-tuning notebook.

The loop is:

```text
target -> data -> post-training -> eval -> package -> report
```

This doc defines what "post-training" means for this project and how it relates
to learning work.

External positioning reference: Baseten's
[`Post-training`](https://www.baseten.co/about-us/#post-training) framing
emphasizes custom training pipelines, RL, reward shaping, model performance,
infrastructure, and applied engineering around a customer's data. TinyGPT should
use the same shape, but scaled down to one Mac and public artifacts.

## Project Pillars

| Pillar | TinyGPT version | Required proof |
|---|---|---|
| Data | traces, failures, public datasets, synthetic examples, preference pairs | manifest, provenance, heldout split, filter/dedupe stats |
| Post-training | SFT, distillation, DPO/SimPO/ORPO/KTO, ReST/RLVR-style loops when reward is verifiable | train config, logs, artifact path, baseline/candidate comparison |
| Eval | frozen task gate plus breadth/regression gate | pass/fail threshold, row traces, failure taxonomy, skipped-check notes |
| Model performance | latency, RAM/peak RSS, tok/s, eval time, train time | measured numbers on the same machine/config |
| Packaging | specialist metadata plus external weights/adapters where appropriate | model card, lockfile, eval report, prompt, HF link if public |
| Public artifact | public report with numbers and blockers | website artifact page, evidence links, next release action |

## What Belongs In The Active Project

Active project work must produce or improve one of these:

- a better dataset or preference set for the selected target
- a post-trained candidate
- a frozen baseline/candidate eval
- a failure taxonomy or trace-to-data loop
- a packaged specialist artifact
- a public before/after report

If work does not improve one of those, it belongs in learning, parked docs, or
research notes.

## What Belongs In Learning

Learning docs are still first-class, but they answer a different question:
"What do we understand now that helps us build the factory better?"

Good learning artifacts:

- explain SFT/DPO/RLVR/ReST mechanics in a reusable way
- map prior art to TinyGPT choices
- document failed experiments and why they failed
- explain the single-Mac vs distributed boundary
- preserve session retrospectives that changed the strategy

Learning docs should not present themselves as the active build queue. Link back
to `PROJECT_STATUS.md`, `docs/NEXT.md`, or this folder when they mention next
actions.

## Release Discipline

Do not call a model a shipped specialist just because weights exist.

A shipped specialist needs:

- target and baseline locked
- eval run before and after training
- regression/breadth check
- performance numbers when feasible
- artifact metadata
- public report or model card
- explicit `ship` decision

Archive weights can be public without being product-ready. Public archive pages
must say why the artifact exists and what would be required to promote it.
