---
title: "Local-model arena — turn-based strategy, self-play RLVR (PRD)"
description: Pit Mac-local models against each other and against frontier models in
  turn-based strategy games, then self-play-RL a local model until it beats a frontier
  model playing zero-shot. The match win/lose IS a verifiable reward — RLVR with no
  hand-authored golds or checker.
---

<!-- PRD metadata (moved from frontmatter for Blume schema compatibility) -->
**status:** proposed

# Local-model arena (self-play RLVR on turn-based strategy games)

Pit Mac-local models against each other — and against a frontier model — in
turn-based strategy games, then RL a local model in-environment until it beats the
frontier model that plays the same game **zero-shot**.

## Why this is the sharpest version of the north star

- It collapses the whole thesis (see [AGENTS.md](https://github.com/PostTrainLLM/posttrainllm/blob/main/AGENTS.md) "Eval philosophy")
  into one demoable claim: **a 4B RL'd inside a game beats a frontier model playing
  that game cold.** The frontier model is smarter in general but never *specialized*
  here — that asymmetry is the entire point, and it's reachable on a Mac.
- **The match outcome is a verifiable reward.** No authored checker, no golds — the
  game decides win/lose. Contrast the BFCL multi-turn gate
  ([multi-turn-agentic-eval.md](multi-turn-agentic-eval.md)), which needed a
  hand-built checker. Cheaper signal, and **open-ended so it won't saturate** the way
  single-turn RL did (the argument is made in
  [game-rl-environment-poc.md](game-rl-environment-poc.md) — don't re-litigate it).

## Relationship to existing work (DRY — link, don't re-explain)

- [game-rl-environment-poc.md](game-rl-environment-poc.md) — single NPC improves at
  one behavior in the fleet's **own** game. This PRD is the **competitive, multi-model
  sibling on off-the-shelf games**. Same GRPO loop, different environment + an
  adversary.
- [rl-multi-agent-roadmap.md](../learn/rl-multi-agent-roadmap.md) — the parked
  multi-agent blueprint this realizes.
- [tool-calling-frontier-parity.md](../learn/tool-calling-frontier-parity.md) §5 — the
  validated from-scratch MLX GRPO loop (group-normalized advantage, KL-to-ref,
  grad-accum) we reuse via an `(env.reset, env.step, reward)` interface.
- Reward + trajectory plumbing: [B28 composite-reward](B28-composite-reward-framework.md),
  B22 trajectory-recorder (shipped).

## Steal first (do NOT build an arena from scratch)

- **TextArena** (Guertler et al., 2025; github `LeonGuertler/TextArena`) — open-source
  LLM-vs-LLM framework: ~50+ turn-based text games, a `reset/step` env API, string
  observations/actions, a player interface, and TrueSkill leaderboards. Plug a local
  mlx player and a frontier player in as two agents. **This is the load-bearing steal.**
- **Project Vend** (Anthropic, 2025) — LLM runs a vending-machine business; reference
  for "economic/strategy game as a benchmark."
- **Generative Agents / Smallville** (Park et al., 2023, arXiv:2304.03442) — the
  town/shop flavor, for the later "arena world" direction.

## Game selection (the one real design call)

Pick for: turn-based, **crisp + cheap-to-check win condition**, **RL-improvable**
(learned heuristics beat brute reasoning), cheap to simulate many rollouts, low
observation/action token cost.

- **Avoid:** real-time action / "button-mashing" (LLMs have no reflex or latency edge);
  deep pure-reasoning games where frontier + search dominate and a 4B can't catch up
  (chess, Go); trivially solved games (tic-tac-toe).
- **Sweet spot (turn-based strategy):** a small resource/territory game (simplified
  Catan/Risk-like), a negotiation/auction game, a card/deduction game (simplified
  poker, Liar's Dice), or positional games with a branching factor that rewards learned
  heuristics. TextArena ships many of these off the shelf.
- **PoC pick:** ONE such TextArena title with a clean win condition and short
  transcripts. Default to a 2-player negotiation or simple-strategy game.

## Design

1. **Player adapter** — wrap `mlx_lm` generate as a TextArena agent (observation
   string → legal action string). Frontier agent reuses the OpenAI-style client from
   [`scripts/bfcl/bfcl_multiturn_deepseek.py`](../../scripts/bfcl/bfcl_multiturn_deepseek.py).
2. **Baseline tournament** ("before") — local-stock vs frontier-zero-shot vs
   scripted/random; record win rates (TrueSkill).
3. **Self-play RLVR** — GRPO on the local policy; reward = game outcome (win +1 /
   lose −1, optional shaping). Opponent = a **frozen snapshot / past-self pool** so the
   policy isn't chasing a moving target; refresh the pool periodically.
4. **Re-tournament** ("after") — does the RL'd local model beat frontier-zero-shot?
   Track the win-rate trend during training + the final head-to-head.

## Acceptance criteria

- [ ] Local + frontier players run in the arena on one turn-based strategy game;
      baseline win rates recorded.
- [ ] Self-play GRPO run; local win rate vs a fixed opponent **rises** over training
      (stable, KL-bounded — the loop is already proven).
- [ ] **Headline:** RL'd-local win rate vs frontier-zero-shot **≥ 50%** on that game (a
      real "beat frontier cheaply" artifact) — or a documented honest negative with the
      reason (frontier too strong / game too reasoning-bound / reward hacked).

## Risks / notes

- **Illegal-move loops / reward hacking** — enforce legal-move masking (grammar-
  constrained decoding; see factory-serve-grammar, shipped) and
  penalize illegal moves; keep the reward strictly the game outcome.
- **Self-play collapse / cycling** — keep an opponent pool of past snapshots; always
  evaluate against a *fixed external* baseline (frontier-zero-shot / scripted), not just
  self-win-rate.
- **Frontier API cost** — train against local self-play; use the frontier opponent only
  for periodic evaluation, cached + capped.
- **Sample efficiency** — GRPO is rollout-hungry and one Mac bounds scale; the PoC
  targets a *trend on one game*, not a general game-player.
- **Sequencing** — phase-2. Trigger only after the tool-calling 4B distill→GRPO loop
  lands; don't let it derail frontier-parity work.

## Future — the actual "arena product"

Many games + a public **Mac local-model leaderboard** (TrueSkill), sibling of the
agentic leaderboard. Fold the viewer into the eval-leaderboard viewer (shipped) /
[B31 gallery](B31-gallery-and-project-pins.md).
