# Doc map — where things moved

This restructure split, merged, and archived a few docs. Use this table
to find where the content of any old path now lives.

If you came here looking for a doc that used to exist, find the old path
in the left column → click the new path.

## Split

The 1,400-line master roadmap was broken into a folder. Every section of
the original lives at exactly one of the new paths:

| Old path                                                   | New path                                                                                                                |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `docs/single_machine_roadmap.md` (Part 1, Tier 1)          | [`docs/roadmap/tier1.md`](roadmap/tier1.md)                                                                             |
| `docs/single_machine_roadmap.md` (Part 1, Tier 2)          | [`docs/roadmap/tier2.md`](roadmap/tier2.md)                                                                             |
| `docs/single_machine_roadmap.md` (Part 1, Tier 3)          | [`docs/roadmap/tier3.md`](roadmap/tier3.md)                                                                             |
| `docs/single_machine_roadmap.md` (Part 1, Tier 4)          | [`docs/roadmap/tier4_skip.md`](roadmap/tier4_skip.md)                                                                   |
| `docs/single_machine_roadmap.md` (Part 2, categories)      | [`docs/roadmap/categories.md`](roadmap/categories.md)                                                                   |
| `docs/single_machine_roadmap.md` (Part 3, top-10 order)    | [`docs/roadmap/recommended_order.md`](roadmap/recommended_order.md)                                                     |
| `docs/single_machine_roadmap.md` (Part 4, datasets)        | [`docs/roadmap/datasets.md`](roadmap/datasets.md)                                                                       |
| `docs/single_machine_roadmap.md` (Part 5, recent research) | absorbed into [`docs/PLAN.md`](PLAN.md) §4; archived at [`docs/archive/recent_research.md`](archive/recent_research.md) |
| `docs/single_machine_roadmap.md` (Part 6, phased plan)     | [`docs/roadmap/phased_plan.md`](roadmap/phased_plan.md)                                                                 |
| `docs/single_machine_roadmap.md` (Part 7, blockers)        | [`docs/roadmap/blockers.md`](roadmap/blockers.md)                                                                       |
| `docs/single_machine_roadmap.md` (honest summary)          | [`docs/roadmap/honest_summary.md`](roadmap/honest_summary.md)                                                           |
| `docs/single_machine_roadmap.md` (index / TOC)             | [`docs/roadmap/index.md`](roadmap/index.md)                                                                             |

The training-pipeline doc was split by phase:

| Old path                                         | New path                                            |
| ------------------------------------------------ | --------------------------------------------------- |
| `docs/training_phases.md` (Phase 1: Pretrain)    | [`docs/training/pretrain.md`](training/pretrain.md) |
| `docs/training_phases.md` (Phase 2: SFT)         | [`docs/training/sft.md`](training/sft.md)           |
| `docs/training_phases.md` (Phase 3: DPO)         | [`docs/training/dpo.md`](training/dpo.md)           |
| `docs/training_phases.md` (end-to-end + reading) | [`docs/training/index.md`](training/index.md)       |

## Merged (lossless)

Content of these docs now lives as appendices of the canonical home; the
original moved to `docs/archive/`.

| Old path                        | New home                                                                           | Archived at                                                                 |
| ------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `docs/evaluation.md`            | [`docs/audits/validation_report.md`](audits/validation_report.md) (appendix)       | [`docs/archive/evaluation.md`](archive/evaluation.md)                       |
| `docs/watch_the_model_think.md` | [`docs/techniques/interpretability.md`](techniques/interpretability.md) (appendix) | [`docs/archive/watch_the_model_think.md`](archive/watch_the_model_think.md) |
| `docs/phase_9_10_status.md`     | [`docs/roadmap/blockers.md`](roadmap/blockers.md) (appendix)                       | [`docs/archive/phase_9_10_status.md`](archive/phase_9_10_status.md)         |

## Archived

Moved as-is to `docs/archive/`:

| Old path                       | New path                                                                  |
| ------------------------------ | ------------------------------------------------------------------------- |
| `docs/annotated_transcript.md` | [`docs/archive/annotated_transcript.md`](archive/annotated_transcript.md) |
| `docs/parked_multi_model.md`   | [`docs/archive/parked_multi_model.md`](archive/parked_multi_model.md)     |
| `docs/shared_vs_native.md`     | [`docs/archive/shared_vs_native.md`](archive/shared_vs_native.md)         |

Root-level status and narrative docs, moved out of the repo root. None had
been meaningfully updated since June; each is a historical record rather than
current state, so they now sit with the other archived material:

| Old path             | New path                                                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `HANDOFF.md`         | [`docs/archive/HANDOFF.md`](archive/HANDOFF.md)                                                                                                  |
| `WHILE_YOU_SLEPT.md` | [`docs/archive/WHILE_YOU_SLEPT.md`](archive/WHILE_YOU_SLEPT.md)                                                                                  |
| `MILESTONES.md`      | [`docs/archive/MILESTONES.md`](archive/MILESTONES.md)                                                                                            |
| `BLOG.md`            | [`docs/archive/BLOG.md`](archive/BLOG.md)                                                                                                        |
| `NIGHTLY.md`         | [`docs/training/nightly.md`](training/nightly.md) — a runner contract, not a status doc                                                          |
| `STATUS.md`          | deleted; it was a pointer stub. Current state is [`PROJECT_STATUS.md`](https://github.com/PostTrainLLM/posttrainllm/blob/main/PROJECT_STATUS.md) |

## Grouped (flat top level → topic folders)

The `docs/` top level had grown to 94 loose files. Files that group
unambiguously moved into topic folders; anything genuinely cross-cutting
stayed at the top level. Old web URLs keep working — see below.

| Moved into                                        | What went there                                                                                                                                                                                      |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`docs/performance/`](performance/performance.md) | FA2 notes, online softmax, KV-cache, memory tradeoffs, CPU/cold-start/checkpointing/YOCO results, perf audits and research, benchmark harness design, determinism contract                           |
| [`docs/techniques/`](techniques/README.md)        | distillation, MoE, MTP, evolution strategies, pruning, quantization, precision, PEFT, LoRA guide, optimizers, GaLore, constrained generation, interpretability, speculative heads, StreamingLLM+KIVI |
| [`docs/audits/`](audits/docs-quality-audit.md)    | `audit_2026`, docs-quality, exactness-completion, feature audit, history-coverage, test-coverage, validation report                                                                                  |
| [`docs/sessions/`](sessions/RETROSPECTIVE.md)     | dated session notes, Q&A log, Pace handoff, planner lock, v11 baselines, retrospective, drilldown, WWDC impact, first specialist findings                                                            |
| [`docs/integrations/`](integrations/deploy.md)    | HuggingFace datasets, GitHub data, lm-eval-harness, Continue.dev provider, deploy                                                                                                                    |
| [`docs/guides/`](guides/study_guide.md)           | model guide, training guide, study guide                                                                                                                                                             |

`docs/learning/` (one file) merged into [`docs/learn/`](learn/README.md).

## URL redirects

Old web URLs (`/docs/<old_slug>`) keep working via static redirects in
`browser/astro.config.mjs`. So a link to `/docs/single_machine_roadmap`
on social media still resolves; it just takes one extra hop to land at
`/docs/roadmap`.

## Canonical homes (for DRY)

To avoid duplicating mechanics across docs, these are the canonical
homes for repeated concepts. If you find an explanation of one of these
_outside_ its home doc, it should be a 1-2 sentence pointer + link, not
a full explanation.

| Concept                                                | Canonical home                                                                  |
| ------------------------------------------------------ | ------------------------------------------------------------------------------- |
| bf16 / gradient accumulation / gradient checkpointing  | [`docs/performance/memory_tradeoffs.md`](performance/memory_tradeoffs.md)       |
| LoRA mechanics                                         | [`docs/techniques/lora_guide.md`](techniques/lora_guide.md)                     |
| MoE (mixture of experts)                               | [`docs/techniques/moe.md`](techniques/moe.md)                                   |
| Distillation                                           | [`docs/techniques/distillation.md`](techniques/distillation.md)                 |
| MTP (multi-token prediction)                           | [`docs/techniques/mtp.md`](techniques/mtp.md)                                   |
| ES (evolution strategies)                              | [`docs/techniques/evolution_strategies.md`](techniques/evolution_strategies.md) |
| Quantization (precision study)                         | [`docs/techniques/precision.md`](techniques/precision.md)                       |
| Quantization (Phase 9 status appendix)                 | [`docs/roadmap/blockers.md`](roadmap/blockers.md)                               |
| Interpretability (logit lens, attention vis, ablation) | [`docs/techniques/interpretability.md`](techniques/interpretability.md)         |
| Training pipeline (pretrain → SFT → DPO)               | [`docs/training/`](training/index.md)                                           |
| Post-training factory positioning                      | [`docs/factory/post-training-factory.md`](factory/post-training-factory.md)     |
| Docs golden path                                       | [`docs/README.md`](README.md)                                                   |
| CLI discovery and lab usage                            | [`docs/cli-reference.md`](cli-reference.md)                                     |
| Docs quality audit                                     | [`docs/audits/docs-quality-audit.md`](audits/docs-quality-audit.md)             |
| Active/reference/archive status labels                 | [`docs/doc-status.md`](doc-status.md)                                           |
| Attempt history / worked vs failed                     | [`docs/attempt-ledger.md`](attempt-ledger.md)                                   |
| External products reviewed / steals                    | [`docs/external-products-reviewed.md`](external-products-reviewed.md)           |
| Method vs recipe / technique cards                     | [`docs/techniques/`](techniques/README.md)                                      |
| Owner learning pipeline                                | [`docs/learning-pipeline.md`](learning-pipeline.md)                             |
| Owner learning progress                                | [`docs/learning-progress.md`](learning-progress.md)                             |
| Single-machine roadmap + research                      | [`docs/roadmap/`](roadmap/index.md)                                             |
| Open-source datasets (pretrain/SFT/DPO/code/math/eval) | [`docs/roadmap/datasets.md`](roadmap/datasets.md)                               |
