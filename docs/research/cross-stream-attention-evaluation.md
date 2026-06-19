---
title: B20 — Learnable cross-stream attention evaluation
description: Read-and-evaluate write-up on the modded-nanogpt speedrun's "cross-stream attention" trick; decide whether to adopt for TinyGPT.
---

# Learnable cross-stream attention — adopt or skip?

**Verdict: skip for now; revisit when we have a from-scratch run with
≥ 50M params and the speedrun playbook becomes the bottleneck.**

This doc fulfils PLAN.md §3 Tier B B20: *"Investigate learnable
cross-stream attention — modded-nanogpt speedrun trick; not yet a
paper but on the GPT-2-quality speedrun playbook. Read-and-evaluate
before adoption. ~half-day investigation, build cost TBD."*

## What "cross-stream attention" refers to

The [modded-nanogpt speedrun](https://github.com/KellerJordan/modded-nanogpt)
playbook stacks ~20 micro-tricks on top of Karpathy's nanoGPT to drive
the wall-clock to a fixed FineWeb val-loss target. One of those
tricks, introduced around mid-2025 in the run-log, is **learnable
cross-stream attention**: within a transformer block, the residual
stream forks into two parallel sub-streams that the next attention
layer routes between with a small learnable gate. Conceptually:

```
x → split → stream_A   →  attn  →  …
       └─→ stream_B  →  attn  →  …
                ↘  gate(α, β)  ↗
                       y
```

The published gain in the speedrun's wall-clock-to-target framing:
~3–6% faster convergence to the same target val-loss vs the
single-stream baseline — meaningful in a competitive sense, modest in
absolute terms.

## What we'd need to ship

1. **Block-level surgery in `Sources/TinyGPTModel/TinyGPTModel.swift`** to
   fork the residual stream and route through the gate. The MLX-Swift
   `Block` is already the right granularity; the change is internal to
   `Block.callAsFunction`.
2. **One extra learnable parameter per block** (the gate's α, β
   coefficients). Negligible param count overhead at our scale.
3. **A numerics gate** per the [no-quality-regression rule](../../memory/feedback_no_quality_regression.md)
   — show no degradation on at least the byte-level Shakespeare smoke
   AND one of the trained gallery preset configurations before the
   default flips.
4. **Speculative-decoding compatibility check** — speculative
   decoding (B14) traces the residual stream; a forked stream changes
   the draft path's hidden state shape.

## Why "skip for now" is the right call at TinyGPT's scale

Three independent reasons:

### 1. The win shows up at speedrun scale, not our scale

modded-nanogpt's speedrun runs are typically a few minutes total at
GPT-2-124M-equivalent capacity on H100s. The 3–6% wall-clock win is
measurable because the rest of the configuration is pinned and the
training distribution is exactly FineWeb val-loss. TinyGPT's typical
configurations:

| Surface | Param count | Eval setup |
|---|---:|---|
| Browser preset | 22 M | Shakespeare LM loss |
| Mac Huge preset | ~96 M | Pile-mini sample loss + downstream lm-eval |
| Specialist (4B / 12B) | 4 B / 12 B | BFCL / τ-bench / Pace harness |

At the browser-preset scale, run variance from `--seed` drift is
larger than 3–6% on most settings; the speedrun trick wouldn't be
visible. At the Mac-Huge scale the training corpus is much wider than
FineWeb-only, so the speedrun's empirical curve doesn't extrapolate
cleanly. At the specialist scale, our QLoRA-on-pretrained path
([[feedback_focus_finetune_distill_large]]) means the base block's
forward is frozen — cross-stream attention would affect only the LoRA
adapter's interaction with attention, not the trained base, which is
not what the speedrun trick targets.

### 2. The interaction surface is larger than the gain

Cross-stream attention touches:

- **Spec-decode (B14, shipped)** — the draft model's hidden state
  has to match the verifier's; forking changes the shape.
- **GaLore (shipped)** — projector basis tracks per-tensor gradient
  geometry; per-stream gradients diverge from the single-stream
  baseline.
- **DoRA (TGLA v2, shipped)** — magnitude vector is `[out_features]`;
  cross-stream attention with output-shape changes complicates the
  magnitude semantics.
- **ANE M8 chunked path** — each Core ML chunk is a closed sub-graph;
  forking the residual mid-chunk forces a chunk boundary or a
  Layer-Norm refactor.

Each of those is a real numerics-gate to re-clear. The aggregate cost
is days, not hours; the gain is bounded by point 1.

### 3. Not yet a paper

The speedrun playbook has been an excellent source of validated
tricks (WSD, layer-wise LR decay — both shipped) but only after the
community converged on them. Cross-stream attention, as of 2026-06-17,
hasn't received a write-up or ablation outside the speedrun PR
comments. The cost-of-investigation is non-zero (the ablation itself
would consume compute we'd rather spend on the specialist track), so
the right move is **wait for the paper, then adopt**.

## What would change this verdict

Revisit B20 if any of these become true:

- TinyGPT ships a from-scratch run at ≥ 50M params on FineWeb-like
  data (we'd be in the speedrun's regime, the gain would be visible).
- The speedrun PR gets a formal write-up with ablations on at least
  two corpora (the gain generalises).
- The interaction-surface items in point 2 above land formally — at
  that point the marginal cost of adding cross-stream attention is
  smaller because the boilerplate is already paid.

In the meantime: this is filed and PLAN.md §3 B20 stays ⬜ with the
explanation "evaluated 2026-06-17 — skip; revisit on scale or paper."

## See also

- [modded-nanogpt repo](https://github.com/KellerJordan/modded-nanogpt) — speedrun playbook + run log
- [wave_4_landscape.md](./wave_4_landscape.md) — the broader competitor scan that triggered this and B16–B24
- [[feedback_no_quality_regression]] — the gate framework any speedrun-trick adoption must pass
- [[feedback_focus_finetune_distill_large]] — why we're not in the from-scratch ≥50M regime today
- PLAN.md §3 Tier B — for the full backlog this resolves against
