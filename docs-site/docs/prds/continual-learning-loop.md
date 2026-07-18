---
title: "PRD — On-device continual-learning loop"
description: "**Thesis:** every correction a user makes is free, high-signal training data that"
---

# PRD — On-device continual-learning loop

**Thesis:** every correction a user makes is free, high-signal training data that
*never has to leave the Mac*. Capture it, refresh a LoRA on it overnight, gate it,
promote it. The model gets better from real usage — and privacy isn't a compliance
checkbox, it's the default.

This is the **Trajectory steal** ([trajectory.ai](https://trajectory.ai),
[docs](https://docs.trajectory.ai/introduction)): "Instrument → Understand → Steer →
Learn." Trajectory and Applied Compute both sell continual learning to enterprises and
have to bolt on SOC 2 + "you approve every update" + audit trails to make it palatable.
On-device, those are structural givens — the wedge competitors pay overhead to fake.

## Why / What

- **Problem:** posttrainllm's factory is an *offline batch* loop. A specialist ships once and
  is frozen until someone manually re-runs the pipeline. The market (Trajectory, Applied
  Compute) has moved the loop *online* — improve continuously from production signal.
- **Users:** anyone running a local specialist/planner (Pace, dictation post-proc, a
  per-task assistant) who corrects its output. Their correction is ground truth.
- **In scope:** capturing corrections, turning them into training pairs, an automatic
  gated LoRA refresh, user-gated promotion. All local.
- **Out of scope (for now):** any cloud upload, federated learning, RLHF/online-RL with a
  reward model (Trajectory does text-reward — we start with supervised corrections),
  multi-user aggregation.

## What already exists (do NOT rebuild)

The offline pipeline is shipped — the continual loop wraps and automates it:

- `AgentTrajectory` / `.atraj` (`native-mac/Sources/TinyGPTModel/AgentTrajectory.swift`,
  `Agent.swift`, `AgentLoop.swift`) — token-preserving rollouts.
- `posttrainllm traces-to-data` (`TracesToData.swift`) — trajectories → SFT pairs.
- `posttrainllm sft` (`SFT.swift`) — LoRA/DoRA fine-tune (DoRA default; magnitudes persist
  since the TGLA-v2 fix).
- `posttrainllm eval-gate` (`EvalGate.swift`) — the promotion gate (BFCL/τ-bench/lm-eval).
- `posttrainllm bake-lora` (`BakeLora.swift`) — merge adapter for deployment.

## What's new (the delta)

1. **Correction capture.** `.atraj` records *completed* rollouts; it does not record when
   a user **edits / rejects / retries / overrides** an output. Add a `correction` event
   type (original output, corrected output, intent kind) and hook it into the points where
   the user can correct: dictation edit, tool-call reject, action override. Append to a
   local correction store. *The corrective text is the target* — Trajectory's "not just a
   binary reward but the actual text" insight.
2. **Curation.** Extend `traces-to-data` to turn correction events into (input,
   corrected-output) SFT pairs (and/or DPO pairs: chosen=corrected, rejected=original).
   Dedup; optionally reject-sample low-confidence corrections.
3. **Scheduled refresh.** Periodic (overnight / idle, under `caffeinate`) LoRA/DoRA
   fine-tune on accumulated corrections. *Sequential, not Trajectory's concurrent
   sampling/training pools* — single-GPU contention on a Mac means sequential + caffeinate
   (see the parallel-training lesson). Mix in a replay sample of the original SFT data to
   resist catastrophic forgetting (ratio = TBD).
4. **Gate + auto-rollback.** The refreshed adapter must pass `eval-gate` AND not regress
   vs the current adapter before promotion. Regression ⇒ discard, keep current. This is
   the no-quality-regression rule made automatic — non-negotiable for an unattended loop.
5. **User-gated promotion.** Default: auto-promote only if the gate passes, with a
   notification ("your dictation model improved on 47 of your corrections; using it now").
   Optional always-confirm mode. Nothing ever uploads.

## Design (the loop)

```
serve/agent ──(user corrects)──> correction store (local, on-device)
                                        │  accumulate to threshold N
                                        ▼
                          traces-to-data (corrections → SFT/DPO pairs)
                                        │  + replay sample of base SFT
                                        ▼
                          sft (LoRA/DoRA refresh, overnight, caffeinate)
                                        │
                                        ▼
                          eval-gate (must pass + not regress)
                            │ pass                 │ fail
                            ▼                       ▼
                   promote (user-gated)        discard, keep current
```

## Risks / gates

- **Quality regression / overfitting to recent edits** → eval-gate + rollback (mandatory)
  + replay mix. The single most important guardrail.
- **Feedback loop** — model trains on corrections to its own outputs; could drift. Mitigate
  by gating on a *fixed* held-out eval, not just recent corrections.
- **Sparse/noisy corrections** — how much before a refresh is worth running? (TBD, measure.)
- **Compute** — overnight LoRA on a Mac is feasible (M1 Pro 16GB secondary w/ throttle per
  the training-hardware note); schedule when idle.

## Open questions (fill after learning / measuring — do NOT pre-answer)

- Minimum correction volume N to trigger a refresh? — TBD, measure on real usage.
- DoRA vs LoRA for incremental refresh? — likely DoRA (more lift), confirm it doesn't
  overfit on small correction sets.
- SFT pairs vs DPO pairs (chosen/rejected) from corrections — which generalizes better? — TBD.
- Replay ratio (corrections : original SFT) to balance plasticity vs forgetting? — TBD.
- Auto-promote-if-gate-passes vs always-user-confirm — product call. — TBD.

## Phased plan (smallest shippable first)

1. **Capture only** — ✅ SHIPPED (2026-06-24). `CorrectionEvent` + append-only JSONL
   `CorrectionStore` (`TinyGPTIO/CorrectionEvent.swift`, pure Foundation), `posttrainllm
   record-correction` CLI (`--intent/--original/--corrected/…`, `--list`), defaulting to
   `~/.tinygpt/corrections`. Unit-tested (`CorrectionStoreTests`, runs under `swift test`,
   no Metal). Ingestion: `posttrainllm record-correction` CLI AND `serve POST /v1/corrections`
   (✅ added 2026-06-24 — `--corrections-dir`, atomic O_APPEND store, 0600 perms; clients
   like Pace can capture directly). **Phase 1 complete.**
2. **Curation** — ✅ SHIPPED (2026-06-24). `posttrainllm corrections-to-data --out … [--format
   sft|dpo] [--intent …] [--replay base.jsonl --replay-ratio r]`. Pure curation in
   `TinyGPTIO/CorrectionCuration.swift` (`sftPair`/`dpoTriple`/`CorrectionCurator`,
   unit-tested); SFT rows match the `traces-to-data` ChatML shape. Corrections without an
   `input` (can't ground a pair) are skipped + reported. Replay mix stride-samples the base
   SFT file (deterministic) to resist forgetting.
3. **Gated refresh** — scheduled overnight `sft` + `eval-gate` + auto-rollback. The core
   loop, unattended-safe.
4. **Promotion UX** — user-gated apply + notification.

## External reference

- Trajectory — continual learning platform, "Instrument/Understand/Steer/Learn", Continuous
  LoRA (split sampling/training pools): https://docs.trajectory.ai/introduction ·
  https://trajectory.ai/field-notes/multi-lora-training-for-continual-learning
- Applied Compute — "Improve" via production data + online RL: https://www.appliedcompute.com
