---
title: Self-improving agents — the closed loop (PRD)
description: "Close the act -> score -> learn -> curriculum loop so a Mac-local agent improves itself with NO teacher, using a verifiable reward. The smallest proof: a teacher-free ReST loop on the file-ops env that raises pass-rate round over round. The compounding engine: an automatic curriculum that keeps proposing tasks at the edge of the agent's ability."
status: proposed
---

# Self-improving agents — the closed loop

A self-improving agent is just a **closed loop**: act in an environment → score the result with
a verifiable reward → learn from the good experience → choose what to practice next → repeat. We
ran every step of this *by hand* in the tool-calling work
([tool-calling-frontier-parity.md §8.1-8.3](../learn/tool-calling-frontier-parity.md)). "Self-
improving" = closing the loop and removing the human from it. This PRD is the **method**; the
[game-RL PoC](game-rl-environment-poc.md) and [arena](local-model-arena-selfplay.md) are specific
*environments* to run the loop in.

## Why now / why us

- **The reward + environment are the scarce ingredients, and we own them.** We have verifiable
  multi-turn environments (BFCL backends), a checker that scores end-state (the reward), a frontier-
  ceiling discipline to keep the reward honest, a rollout harness, and a from-scratch MLX trainer.
- **It's on-thesis:** reach frontier capability cheaply on a Mac, and *learn the whole space* —
  self-improvement is the current frontier of agent research.

## The pieces we already have (don't rebuild)

| Loop step | Existing artifact |
|---|---|
| Act / roll out | `scripts/bfcl_multiturn_eval.py` (native tool-calling, MAX_STEPS agentic loop) |
| Verifiable reward | BFCL `multi_turn_checker` (end-state) — already the reward in every gate |
| Keep good experience | rejection sampling (the RFT filter) — `bfcl_multiturn_*.py --dump` / `gold_to_sft_traj.py` |
| Learn | `scripts/distill_multiturn.sh` (render → LoRA SFT → fuse) and the GRPO loop (§5) |
| Choose what's next | the cliff-finding methodology (easy→hard→veryhard→breadth) — to be **automated** |
| Keep the reward honest | frontier-ceiling gate + free `bfcl_multiturn_codex.py` (gpt-5.5) |

## The smallest proof (PoC) — a teacher-free ReST loop

Prove the loop closes: a model improves on the env using **its own** experience, no teacher, no
gold-cloning. (STaR, Zelikman 2022; ReST / ReST-EM, Gulcehre 2023 / Singh 2024.)

1. **Sample** K trajectories per task (temperature > 0 for diversity) from the *current* model on a
   training split — `bfcl_multiturn_eval.py` with a sampler tweak + a `--dump-rollouts`.
2. **Score** each with the checker (the verifiable reward).
3. **Keep the wins** (checker == pass). These are the model's *own* correct trajectories — not a
   teacher's, not the gold.
4. **SFT** on the wins (`distill_multiturn.sh`), fuse.
5. **Re-eval** on the held-out gate; if improved, **repeat** with the new model.

**Success criterion:** held-out pass-rate **rises across ≥2 rounds with no teacher/gold.** That is
self-improvement, demonstrated, on a Mac. (We already have the degenerate t=0 / gold-cloned version
working — §8; this swaps the teacher for the model's own filtered rollouts.)

## The compounding engine — automatic curriculum

A fixed task set saturates (we watched the 4B saturate file-ops). The loop only *compounds* if
something keeps proposing tasks **at the edge of the agent's ability**:

- A generator (`gen_multiturn_trajdata.py`, already parametric over depth/turns/breadth) proposes
  tasks; keep those the current model passes **~30-70%** of (the learnable frontier).
- As the model improves, the generator **scales difficulty** (more turns, deeper nesting, new
  backends). The "cliff" we've been finding by hand becomes the training signal.
- Frontier (gpt-5.5, free) periodically validates the new tier is sound (still ~aces it).
- Cite: automatic curriculum / PCG; self-proposed tasks (Absolute Zero, Zhao 2025).

## The discipline — the reward is the whole ballgame

- **Grounded + verifiable reward compounds; ungrounded self-judging collapses.** Keep the reward
  the checker / gold-state, *not* the model grading itself (reward hacking, confident-error
  reinforcement). Self-critique (Reflexion, Shinn 2023) is fine as a *proposal* mechanism, never as
  the reward.
- For domains without a checker, prefer a **held-out programmatic verifier** or a *sparing* frontier
  judge, and guard the policy with **KL-to-reference** (the GRPO variant) so it can't drift far.

## Levers / variants (compose as needed)

- **Filtered-SFT (ReST-EM):** simplest, stable, what the PoC uses.
- **RLVR / GRPO:** policy-gradient on the reward — richer, needed for open-ended envs (the
  [game-RL PoC](game-rl-environment-poc.md) / [arena](local-model-arena-selfplay.md)).
- **Self-play task generation:** the agent (or a paired proposer) invents the curriculum.
- **Verifier-in-the-loop (V-STaR):** also train a verifier on wins+losses; use it to rank rollouts.

## Acceptance criteria

- [ ] `--dump-rollouts` (sampled, scored, win-filtered) added to the multi-turn harness.
- [ ] One ReST iteration: stock → self-rollouts → filter → SFT → eval, **pass-rate rises**.
- [ ] ≥2 iterations with **monotonic (or non-decreasing) held-out improvement, no teacher**.
- [ ] A curriculum step: generator targets the 30-70% band; difficulty scales as the model improves.
- [ ] Reward stays grounded (checker); a brief audit shows wins aren't checker-hacks.

## Risks / notes

- **Reward hacking** — audit a sample of "wins"; keep the checker strict (it compares real end-state).
- **Diversity / mode collapse** from repeated rejection-SFT — sample at temperature, dedup wins, keep
  a replay buffer of varied solutions, consider KL-to-ref (GRPO).
- **Curriculum stall** — if everything is ~0% or ~100%, no signal; target the mid-band.
- **Compute** — rollout-hungry; one Mac bounds K and rounds. PoC targets a *trend*, not a finished agent.
- **Sequencing** — phase-2, after the current distill/breadth eval lands; reuse, don't rebuild.

## Relationship to other PRDs

- [game-rl-environment-poc.md](game-rl-environment-poc.md) — the RL flavour of this loop in the
  fleet's own game.
- [local-model-arena-selfplay.md](local-model-arena-selfplay.md) — competitive self-play; the match
  outcome is the verifiable reward.
- [B28 composite-reward](B28-composite-reward-framework.md), [B22 trajectory-recorder](B22-trajectory-recorder.md)
  — reward + experience plumbing this loop consumes.
