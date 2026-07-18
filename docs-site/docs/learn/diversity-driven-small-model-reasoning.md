---
title: "Diversity-driven small-model reasoning (Spectrum-to-Signal)"
description: "Three transferable training methods from the VibeThinker papers — Diversity-Exploring Distillation, MaxEnt-Guided Policy Optimization (MGPO), and specialist weight-merging — mapped to where each upgra"
---

# Diversity-driven small-model reasoning (Spectrum-to-Signal)

VibeThinker (1.5B → 3B) shows a small dense model matching flagship reasoning on
*verifiable* domains (math/code). The recipe is the **Spectrum-to-Signal Principle
(SSP)**: first *widen* the model's space of correct-but-diverse reasoning (Spectrum,
in SFT), then *sharpen* onto the winning paths with verifiable-reward RL (Signal).
A small model lacks the diversity scale gives large ones for free — so you **train**
the diversity in before RL can exploit it.

Why this page exists: SSP names and validates the exact ingredients our teacher-free
loop was missing ([self-improving-agents PRD](../prds/self-improving-agents.md),
[journey §8](./tool-calling-frontier-parity.md)). Each method below is mapped the house
way — **what / why-it-matters-here / source / repo anchor** — and we don't re-teach
GRPO/RLVR basics (see [advanced-llm-training](./advanced-llm-training.md)).

> Verified on our infra: VibeThinker-3B scored **GSM8K 40/40 = 100%** ([`scripts/gsm8k_eval.py`](../../scripts/gsm8k_eval.py)) — the reasoning claim holds. It has **no native tool-calling**, so its value to us is as a *reasoning-strong distill base*, not a drop-in agent.

## 1. Diversity-Exploring Distillation (the "Spectrum" — SFT)

- **What:** SFT does *not* imitate one best solution path. Sample *many* teacher
  traces per query (keep full intermediate steps); per domain, select the checkpoint
  with the **most valid solutions** (not lowest loss, not highest Pass@1); then
  **parameter-merge** the domain specialists into one model that keeps high output
  diversity.
- **Why it matters here:** our ReST loop keeps the *first* checker-passing trajectory
  per task — single-path, accuracy-oriented. That's exactly the failure SSP warns
  against: low spectrum → RL has nothing diverse to sharpen. The fix is to collect
  *diverse* wins (K>1, distinct strategies) before SFT.
- **Source:** VibeThinker-3B §SFT — [arXiv:2606.16140](https://arxiv.org/abs/2606.16140).
- **Repo anchor:** [`scripts/rollout_fast.py`](../../scripts/rollout_fast.py) already
  does batched K-rollout collection; today it keeps any win, not diverse wins.

## 2. MaxEnt-Guided Policy Optimization — MGPO (the "Signal" — RL)

- **What:** an auto-curriculum inside GRPO. Weight each prompt
  `w(q) = exp(−γ · D_ME(p(q) ‖ 0.5))` — **upweight prompts near 50% accuracy** (where
  correct and incorrect rollouts coexist = the capability frontier), and apply that
  weight to the group-relative advantage in a GRPO-style clipped objective.
- **vs GRPO:** GRPO weights every prompt equally; MGPO **downweights saturated (p≈1)
  and impossible (p≈0)** prompts and concentrates gradient on the learnable middle.
  It's the maximum-entropy form of DAPO-style dynamic sampling.
- **Why it matters here:** this *is* the "target the 30–70% pass band" auto-curriculum
  in our PRD, with a clean formula. We already adopted DAPO dynamic sampling
  (task #46); MGPO is the principled upgrade — and cheap (a re-weight in the sampler).
- **Source:** VibeThinker §RL — [arXiv:2606.16140](https://arxiv.org/abs/2606.16140);
  origin in [VibeThinker-1.5B, arXiv:2511.06221](https://arxiv.org/abs/2511.06221).

## 3. Specialist weight-merging (the negative-transfer antidote)

- **What:** train **per-domain specialists** separately, then **merge their parameters**
  into one model — preserving each domain's skill without blending the training.
- **Why it matters here — this is the big one.** Our measured failure was *negative
  transfer*: a narrow distill erodes other domains (file-ops specialist: breadth
  60→42; multi-backend gold-distill: 60→31; [journey §8.4–8.5](./tool-calling-frontier-parity.md)).
  Merging specialists is the structural answer: don't train one blended model — train
  file-ops / vehicle / trading / travel specialists and **merge the weights**. We
  already do LoRA + fuse, so this is buildable now.
- **Source:** VibeThinker §SFT (domain-specialist merging) — [arXiv:2606.16140](https://arxiv.org/abs/2606.16140).
- **Repo anchor:** [`scripts/distill_multiturn.sh`](../../scripts/distill_multiturn.sh)
  (LoRA SFT → fuse) is the per-specialist builder; merging multiple fused models is the
  missing step.

## Consolidation steps (briefly)

- **Offline self-distillation:** re-mine high-quality RL-stage trajectories, filtered by
  a "learning-potential" score within length buckets (avoids length bias). A refinement
  of our rejection-sampling SFT.
- **Instruct RL:** a final alignment pass (format-sensitive + long-context + general
  alignment) to make a reasoning model user-facing.

## "VibeThinker for agents" — the concrete plan

SSP, instantiated on our verifiable domain (BFCL multi-turn, the checker is the reward):

1. **Spectrum** — collect *diverse* passing trajectories per task (`rollout_fast` K>1,
   keep distinct strategies, not first-win).
2. **Specialists + merge** — train per-backend specialists, parameter-merge into one →
   tests the negative-transfer fix directly.
3. **Signal** — MGPO-weighted RL on the 30–70% frontier tasks.

We have every ingredient (base = Qwen3-4B, verifier = BFCL checker, batched rollouts,
LoRA+fuse). SSP just names the algorithm. First high-ROI move: the **specialist-merge**
experiment — it attacks our known failure mode with infra we already have.

## Related

- [Tool-calling frontier-parity journey §8](./tool-calling-frontier-parity.md) — where the negative-transfer numbers come from.
- [Self-improving agents PRD](../prds/self-improving-agents.md) · [Capability-retention PRD](../prds/capability-retention.md).
- [Advanced LLM training](./advanced-llm-training.md) — GRPO/RLVR/distillation basics (not re-taught here).

## Sources

- [VibeThinker-3B: Exploring the Frontier of Verifiable Reasoning (arXiv:2606.16140)](https://arxiv.org/abs/2606.16140)
- [Tiny Model, Big Logic: VibeThinker-1.5B (arXiv:2511.06221)](https://arxiv.org/abs/2511.06221)
- [WeiboAI/VibeThinker-3B · Hugging Face](https://huggingface.co/WeiboAI/VibeThinker-3B)
