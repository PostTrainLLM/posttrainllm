# Session — from frontier-parity distillation to the self-improving loop

Date: 2026-06-16. The arc, the decisions, and the transferable lessons. Numbers and mechanics
live in [`tool-calling-frontier-parity.md`](../learn/tool-calling-frontier-parity.md) §8.1–8.5;
this is the meta-narrative.

## The arc in one paragraph

Started with "get the 4B (or 8B) to the multi-turn bar." Distillation took it to **frontier-parity
on file-ops (58→100, matching gpt-5.5, beating Gemma-12B at ⅓ size)** — no 8B needed. Tried to break
it with a harder gate; it **saturated** even longer-horizon file-ops. The real question turned out to
be **breadth**, not depth — and there the specialist had *regressed* (negative transfer). Chasing the
fix proved a sharp boundary on cheap distillation and converged the whole thread onto **self-improving
RL** as the answer. Ended building the (teacher-free) ReST loop + a batched throughput path.

## Transferable lessons (the keepers)

1. **The verifier is the moat, not the trainer.** Every advance hinged on a *sound, frontier-validated*
   gate. Where no verifier exists (we discussed humor / Reddit-voice), you cannot RL or self-improve —
   you're stuck with SFT + vibes. Invest in rewards, not just training.
2. **Distillation reaches frontier-parity cheaply — on verifiable, *prompt-derivable* tasks.** The 4B
   matched a frontier model on file-ops agency. The thesis holds for a domain.
3. **Gold-cloning ≡ distillation *only* when call args come from the prompt.** For data-dependent
   agency (args from tool *results* — 52% of multi-backend turns), cloning concrete gold values teaches
   hallucination. The skill is the *interleaving* (`call → read → use`), which the gold doesn't contain
   → you need real interleaved trajectories (a teacher, or the model's own filtered rollouts). §8.5.
4. **Specialization erodes breadth.** Narrow distill: file-ops 100 / out-of-domain 60→42; multi-backend
   gold 60→31. The *stock* model stayed the best generalist. "How much intelligence did we keep?" is now
   a first-class metric → [capability-retention PRD](../prds/capability-retention.md).
5. **Saturation is real; keep raising the gate.** "then it's not hard enough" → veryhard tier → still
   100 → breadth became the discriminating axis. A gate that doesn't separate top models is done.
6. **The convergence.** Fixing breadth and proving self-improvement are the *same* experiment: the
   model's own checker-passing rollouts carry correct interleaving with no teacher.

## Decisions (log)

| Fork | Choice | Why |
|---|---|---|
| 4B vs step to 8B | **distill the 4B** | reached 100% on the gate; 8B unnecessary |
| harder gate → distill 12B | **dropped the 12B** | veryhard saturated at 4B; 12B buys nothing on file-ops |
| fix breadth via multi-backend gold-distill | **failed → pivot to ReST** | gold-cloning ceiling on data-dependent tasks |
| paid DeepSeek teacher | **free Codex `gpt-5.5`** | cost discipline; `--output-schema` gives clean JSON |
| recover lost `/tmp` model | **gold behaviour-cloning** | gold *is* the trajectory for prompt-derivable args; reproduced 100/95 free |
| Reddit-voice for covert promotion | **declined** | astroturfing + detection-evasion; redirected to honest growth |

## Gotchas worth remembering

- **`/tmp` gets wiped** — persist fused models under `~/.cache/posttrainllm/models/`.
- **`--grad-checkpoint` is mandatory** for long-seq SFT (18-tool catalog floors examples ~3.5k tokens;
  151k-vocab logits OOM the backward without it).
- **BFCL global-state isolation** — instances are keyed by `(model_name, test_id, class)` in module
  globals and reused; concurrent/repeated same-id rollouts corrupt shared state. Fix: unique
  `model_name` per rollout (`rollout_fast.py`). K=1 eval was always clean (checker uses a separate
  `_eval` namespace).
- **Batch=1 rollout is the loop's bottleneck** — a self-improving loop is impractical without batched
  rollouts (`rollout_fast.py`) + (next) prefix-caching the static tools prompt.

## Artifacts produced

- **Docs:** journey §8.1–8.5; PRDs [self-improving-agents](../prds/self-improving-agents.md),
  [local-model-arena-selfplay](../prds/local-model-arena-selfplay.md),
  [capability-retention](../prds/capability-retention.md); learning gap-fixes
  [essential-vs-optimization](../learn/essential-vs-optimization.md),
  [webgpu-execution-model](../learn/webgpu-execution-model.md), + the roadmap exit-exam.
- **Scripts:** `gen_multiturn_trajdata` (+veryhard), `gold_to_sft_traj`, `render_sft_from_traj`,
  `distill_multiturn`, `headtohead_multiturn`, `bfcl_multiturn_codex` (free frontier),
  `rest_iterate`, `rollout_fast`; harness rollout-dumping.
- **Models:** `mt4b_fused` (file-ops specialist, 100/95), `mt4b_mb_fused` (multi-backend, 100 depth / 31 breadth).

## Open / next

- ReST first-iteration result (running) — does breadth rise above stock's 60% with no teacher?
- Validate `rollout_fast.py` vs the single-rollout harness, then run iteration 2 fast.
- If cold-start ReST is flat: auto-curriculum (target the 30–70% band) or a frontier cold-start.
