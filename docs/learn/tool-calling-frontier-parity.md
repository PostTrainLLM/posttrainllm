# Tool-calling: how close can a Mac-local small model get to frontier?

**What:** the arc from "our 1.7B scores ~55% on tool-calling" to a frontier-validated
metric, an honest size curve, and a distillation result that closes most of the gap.
**Why it matters here:** this is the cost-compression thesis made concrete — *reach
frontier capability at a fraction of the cost*, measured on a ruler we trust.

Recorded 2026-06-14. Companion principle: the **frontier-ceiling gate** in
`AGENTS.md` ("Eval philosophy"). Distillation mechanics: [distillation.md](../distillation.md).

## 1. The eval was broken before the models were

The first "55%" came from scoring against [hermes-fc](https://huggingface.co/datasets/NousResearch/hermes-function-calling-v1)
gold with exact-string match. That metric is unwinnable:

- **~29% of held-out examples have *ungroundable* gold args** — device IDs, txn
  codes, whole JSON payloads, even a literal `unique_nft_identifier` placeholder —
  values that appear *nowhere* in the prompt. No model can reproduce them.
- **A frontier model (Claude via `claude -p`) scored ~12%** on the hard cases, and
  its answers were frequently *more correct* than the gold. Hard exact-match ceiling
  ≈ 71%.

**Rule that came out of this:** before any benchmark grades a Mac model, a frontier
model must ace it (~100%). If frontier can't, the eval is broken — fix or drop it.
hermes-fc is now **training-only, never a reported metric.**

## 2. The ruler we trust: BFCL with AST matching

[BFCL](https://gorilla.cs.berkeley.edu/leaderboard.html) golds are *verified
groundable* and multi-valued (each param lists acceptable values). We built a
controlled harness (single-turn categories) and validated it: **frontier = 124/125
(99.2%)**. The lone miss (`parallel_9`) is a doubly-underdetermined gold (batched
array call ≡ parallel calls; `"5:00 PM"` ≡ `"5 pm"`) — accepted as passing.

Legitimate harness fixes made to *reach* frontier 100% (not to inflate small models):
Python-syntax instruction (BFCL's own convention), implicit-multiplication
canonicalization (`3*x` ≡ `3x` — BFCL's own gold `3x**2` is non-executable),
recursive nested-dict matching, and a brace-matching parser.

> **Two parser bugs were hiding the local models' real ability.** The first regex
> discarded multi-call outputs that used one closing `</tool_call>` for several
> blocks (a model convention); the second couldn't parse bare-JSON calls with
> nested `arguments`. Fixing them moved the distilled 1.7B's parallel_multiple from
> a fake 8% to a real 60%, and the 4B's simple_python from a fake 0% to 84%. Lesson:
> a lenient, well-tested parser is part of a fair eval.

## 3. The honest size curve (validated BFCL slice, n=25/category)

| Model | simple | multiple | parallel | par_mult | live_s | live_m | **avg** |
|---|---|---|---|---|---|---|---|
| **Frontier (Claude)** | 100 | 100 | 96 | 100 | 100 | — | **~99** |
| 30B-A3B (≈3B active) | — | — | 96 | 96 | — | — | ~frontier |
| base-4B (stock) | 84 | 96 | 92 | 80 | 88 | 60 | **83** |
| base-1.7B (stock) | 92 | 96 | 20 | 16 | 72 | 42 | 56 |
| distilled-1.7B (hermes) | 80 | 84 | 68 | 60 | 76 | 24 | 65 |
| **FT-1.7B (ToolACE)** | 80 | 96 | 68 | 64 | 92 | 56 | **76** |

Headlines: the **30B-A3B matches frontier on multi-call at ~3B active params** (the
cost-compression proof). The **stock 1.7B is already frontier-level on single-call
(92/96)** — its only real weakness is multi-call decomposition.

## 4. Conclusion on distillation/SFT

**Best result via distillation/SFT so far: avg 76 for the 1.7B** (fine-tuned on 8,270
[ToolACE](https://huggingface.co/datasets/Team-ACE/ToolACE) examples, 42% multi-call,
prompts identical to the eval). It **closed most of the multi-call gap** (parallel
20→68, parallel_multiple 16→64), and now *beats* the 4B on live_simple (92 vs 88).
That's ~2/3 of the way from base-1.7B (56) to base-4B (83).

But SFT-distillation **plateaus short of frontier-parity**, and it **trades**:
- Hard multi-call still lags (parallel/parallel_multiple 68/64 vs 4B 92/80, frontier 96/100).
- It *regressed* single-call (92→80) — the same trade hermes showed. Fine-tuning on a
  tool-call corpus dilutes the base's already-strong single-call.

This matches the validated thesis (see [distillation.md](../distillation.md)):
**distillation can match but not exceed its data/teacher ceiling.** Remaining *distillation*
levers we have NOT exhausted: (a) fix the data mix to recover single-call; (b) distill
from our **local 30B** (already frontier-level on multi-call) instead of a generic
dataset. Pure SFT's cap for the 1.7B looks to be ~the 4B's level, not frontier.

## 5. Where reinforcement learning comes in

To *exceed* the SFT ceiling you need RL — it optimizes a verifiable reward directly
rather than imitating data. Status of the from-scratch MLX GRPO work (no MLX GRPO
exists; built here):

- **Loop validated** on GSM8K (reward trended up vs the zero-shot floor) — sample K
  rollouts → verifiable reward → group-normalize advantage (no critic) → policy
  gradient on the LoRA.
- **Now has a real reward**: the validated BFCL AST matcher *is* a verifiable reward
  function — exactly what RLVR needs. Earlier GRPO-on-tool-calls used the broken
  exact-match; that's fixed.
- **Known stability fix pending**: the tool-call GRPO run spiked (loss → -59) without
  KL regularization. Add a KL-to-reference penalty before the real runs.

**Result (2026-06-14).** GRPO on FT-1.7B (reward = graded AST match + over-emission
penalty; KL to frozen FT-1.7B; held-out BFCL [25:] prompts; grad-accumulation for
Qwen3's 151k-vocab logits). Stable throughout (loss ~0, KL ≤ 0.025 — no blowup). It
delivered a **modest, targeted** lift, exactly on the categories we aimed at:

| | simple | multiple | parallel | par_mult | live_s | live_m | avg |
|---|---|---|---|---|---|---|---|
| SFT (FT-1.7B) | 80 | 96 | 68 | 64 | 92 | 56 | 76 |
| **+GRPO** | 80 | 96 | 68 | **68** | 92 | **64** | **78** |

**The arc: base 56 → SFT 76 → GRPO 78.** Conclusion: **SFT does the heavy lifting;
RL is a small targeted top-up** (+8 live_multiple, +4 parallel_multiple). The 1.7B
**plateaus ~78** — short of the 4B and frontier on hard multi-call. Strong result
(4B-competitive on 4/6) but not parity. → escalate to the 4B.

## 6. The 4B sweep — and the punchline: on a strong base, *selection beats training*

We surveyed the best small bases (June 2026) and ran the recipe. Validated BFCL slice:

| Model | simple | mult | par | par_m | live_s | live_m | **avg** |
|---|---|---|---|---|---|---|---|
| Frontier (Claude) | 100 | 100 | 96 | 100 | 100 | — | ~99 |
| **Qwen3-4B-2507 bf16 — STOCK** | 92 | 96 | 96 | 96 | 88 | 56 | **87.3** |
| Hammer2.1-3b stock (FC-specialist*) | 96 | 100 | 92 | 88 | 84 | 60 | 86.7 |
| Qwen3-4B-2507 + ToolRL-GRPO | 92 | 96 | 92 | 92 | 92 | 56 | 86.7 |
| Qwen3.5-4B-8bit stock | 88 | 100 | 80 | 84 | 92 | 72 | 86.0 |
| Qwen3-4B-2507 **4-bit** stock | 84 | 96 | 92 | 80 | 88 | 60 | 83.3 |
| Qwen3-4B + function-masking SFT | 84 | 92 | 88 | 84 | 72 | 60 | 80.0 |

*Hammer trains on BFCL-like data → structured scores partly by-design.

**Findings:**
- **Precision was the biggest lever of the whole project.** bf16 (87.3) vs 4-bit (83.3) =
  **+4 for free** — the FC-quantization finding, confirmed. *The best result came from a
  flag, not training.*
- **ToolRL-GRPO is neutral on a strong base** (87.3→86.7; traded parallel for live_simple).
  RL's headroom needs examples the model gets *inconsistently* — scarce when the base is
  already ~87. (It *did* help the weak 1.7B: +2.)
- **Function-masking SFT regressed the strong base** (−7). The masking trick nudged its
  target (live_multiple 56→60) but the SFT process taxed everything else. Hammer's trick
  works *from-scratch* in the base's native training, not LoRA-bolted onto a strong model.
- **`live_multiple` is the wall** — no intervention moved real-user function-selection past
  ~60 (frontier ~90+). A *data/base* gap, not a training-knob gap.
- **Qwen3.5 (qwen3_5 arch) is inference-only here** — mlx_lm has no backward for it; can't
  fine-tune/GRPO on this Mac.

**Verdict: best Mac-local 4B tool-caller = Qwen3-4B-Instruct-2507 @ bf16, STOCK**
— beats SOTA-4B (Hammer-4B 76), zero training, every training intervention made it worse.
**The meta-lesson: training is the lever for *weak* bases (1.7B 56→78); on a strong base the
wins are base + precision selection. We proved this empirically rather than assuming it.**

## 7. Closing the eval gaps (the honest headline)

Two fixes made the number trustworthy:
- **`live_multiple` was never frontier-gated** — running it, frontier scored only **84**,
  with ~3/4 misses being under-determined golds (USA≡United States, a *fuller* address
  penalized) — the hermes disease again. Adding country-alias + multi-word-superset
  semantic matching lifted **frontier 84→92** (sound, no over-accept) and **our 4B 56→64**,
  sound categories unchanged. **Honest headline: Qwen3-4B-2507 bf16 = 88.7, frontier = 98.0.**
- **Irrelevance probe: our 4B abstains 40/40 (100%)** when no tool fits — no over-triggering.
  (Format-sensitivity to trivial rewording: 0pp — but that's a weak templated proxy; real
  LLM-paraphrase, where the field sees 13–19pt drops, is future work.)

**On the *sound* categories the 4B is ~93–94 — near-frontier.** The residual gap is
genuine capability on the hardest real-user args (`live_multiple` 64 vs frontier 92), not
something more training of *this* base fixes.

## 8. Multi-turn / agentic — the cliff, measured (2026-06-14)

Single-turn (88.7) said nothing about *holding a conversation*. Built a stateful
multi-turn harness reusing BFCL's machinery (`execute_multi_turn_func_call` +
`multi_turn_checker` + the `involved_classes` backends); `scripts/bfcl_multiturn_eval.py`.

**The build lesson:** the *inference side* is the eval. A hand-rolled text-transcript
prompt under-elicited badly — the 30B-A3B scored **0/8 despite acing single-turn (96/96)**.
The fix: drive the model with its **native tool-calling chat template** (`tools=` catalog +
proper `assistant`/`tool` message roles — what Qwen3 was trained on) + BFCL's own
multi-turn behaviour prompt. That lifted the 30B from **0% → 50%** — in BFCL's expected
~50-70% range for `multi_turn_base` (the hardest category; *even frontier doesn't ace it*).

**The cliff (multi_turn_base, native-template harness, n=20 same examples):**

| Model | single-turn | **multi-turn** | drop |
|---|---|---|---|
| Qwen3-30B-A3B (3B active) | ~96 | **45%** | −51 |
| **Qwen3-4B-2507 bf16** | 88.7 | **25%** | **−64** |

So even the strong 30B more than halves on the *hardest* multi-turn; the 4B drops to 25%.

**But "95-96% multi-turn" is unachievable on `multi_turn_base` for *anyone*** — the BFCL-V4
leader sits at 75% *overall* and multi-turn runs lower; frontier caps ~50-70%. By our own
frontier-ceiling rule, a 95% bar there is mis-calibrated. So we built a **difficulty-graded,
right-sized gate** — deterministic single-backend (GorillaFileSystem) agentic tasks tuned so a
strong model aces the easier tiers while the gap to a small model grows (`scripts/make_multiturn_gates.py`).

**The capability gradient — frontier-validated (DeepSeek-V4-pro, true frontier):**

| Tier | task shape | **DeepSeek-V4-pro** | 30B-A3B (proxy) | **Qwen3-4B-2507 bf16** |
|---|---|---|---|---|
| single-turn | one call | ~99 | ~96 | 88.7 |
| easy multi-turn | 1-2 calls | 100% | 100% | 94% |
| moderate | 3-4 calls + cd-nav | 100% | 100% | 86% |
| **hard** (canonical gate) | 5-7 calls, deep nesting, 4 turns | **100%** | 83% | **58%** |
| `multi_turn_base` (BFCL hardest) | multi-backend, long | — | 45% | 25% |

**The hard tier is the sound, discriminating gate** — a *true* frontier model (DeepSeek-V4-pro,
via OpenAI function-calling) aces it **100%**, while the **4B clearly cliffs to 58%** (a 42-pt
frontier-to-small gap). So `make_multiturn_gates.py` + the DeepSeek backend
(`bfcl_multiturn_deepseek.py`) give a *calibrated* multi-turn ruler: frontier ~100%, and the 4B's
curve **94 → 86 → 58** maps exactly where it degrades as agentic complexity rises. (The 30B-A3B
sits between at 83% on hard — a strong but not-frontier 3B-active proxy.)

**The 4B is a capable *simple*-agent, not a poor agent** — near-frontier on easy/moderate flows,
cliffing only as depth/length/turns grow. We expected the climb lever to be *multi-turn RL*;
in fact **rejection-sampling distillation alone cleared it** (§8.1). RL (GRPO) stays available
as a further top-up, but wasn't needed to reach frontier-parity on this gate.

(API note: BFCL func docs use `"type":"dict"`; OpenAI/DeepSeek require `"object"` — the DeepSeek
backend normalizes BFCL's type vocabulary to JSON-schema, and needs a `curl` User-Agent to clear
Cloudflare. Key read from `/tmp/deepseek_key` / `$DS_KEY_FILE`, never committed.)

(Build note: the inference side IS the eval — a hand-rolled text transcript scored the 30B 0%;
the native tool-calling chat template + proper roles fixed it. And `echo`-content tasks were
flaky because small models over-call and a stray `touch` blanks the file — idempotent
mkdir/mv/rm tasks make the gate clean. Both are real "agentic eval is subtle" lessons.)

## 8.1 Climbing the cliff — frontier-trajectory distillation (2026-06-16)

Goal: get the 4B from its 58% hard-tier cliff to the ~95% frontier level **without
stepping up to 8B**. Two levers, stacked:

1. **Free first — a plan-then-execute system prompt** (plan the full call sequence, act one
   step at a time, never repeat a succeeded call, stop when done). Stock 4B **58 → 75** on the
   12-task gate (the harness `SYS` is now `MT_SYS`-overridable). A real +17, but brittle.
2. **The durable lever — RFT (rejection-sampling distillation).** Recipe, all Mac-local:
   - **Scale the task family:** `gen_multiturn_trajdata.py` templates hundreds of deterministic,
     idempotent GorillaFileSystem agentic tasks (gold-validated via `multi_turn_checker`).
   - **Teacher trajectories:** run **DeepSeek-V4-pro** over 100 held-out tasks (`bfcl_multiturn_deepseek.py
     --dump`), keep **only the 99 the checker passed** (rejection sampling ⇒ clean labels).
   - **Render in the student's own format:** `render_sft_from_traj.py` re-emits each trajectory
     through the 4B's chat template (`tools=` + `<tool_call>` + tool roles) as mlx_lm text.
   - **LoRA SFT:** 16 layers, lr 1e-5, 4 epochs. *`--grad-checkpoint` is mandatory* — every
     example is ~3.1-3.7k tokens (the 18-tool catalog floors them) and the 151k-vocab logits OOM
     the backward pass without it. One command: `distill_multiturn.sh`.

**The climb (held-out, zero train/eval content overlap — verified):**

| Qwen3-4B-2507 | hard gate (12) | 40-task held-out set |
|---|---|---|
| stock | 58% | — |
| + plan prompt | 75% | 60% |
| **+ distilled (99 frontier trajectories)** | **100%** | **95%** |

**The 4B now matches DeepSeek-V4-pro (100%) on the frontier-validated hard gate** — frontier-parity
on multi-turn file-system agency, at 4B, locally, no 8B needed.

**The tradeoff (honest):** single-turn BFCL slipped ~**87 → 83** avg (simple_python −8,
parallel_multiple −16, multiple/parallel unchanged, live_multiple +4) — the classic specialization
cost of a narrow SFT. Recoverable by mixing single-turn data into the SFT or fewer epochs if we
want both skills; for a multi-turn agentic product (Pace) the trade is strongly positive.

**Scope:** proven on the GorillaFileSystem multi-turn domain (the gate's backend). Generalization
to other agentic backends (trading, ticketing, …) is untested — distilling a multi-backend mix is
the obvious next step. The recipe — *author verifiable tasks → frontier RFT → SFT in the student's
template* — is domain-general.

## 8.2 Conclusive head-to-head — Pace incumbent (Gemma) vs the 4B (2026-06-16)

Pace ships **Gemma**; this is the deciding comparison. Same hard gate, same plan prompt,
n=12. Gemma scored **zero-shot** via LM Studio (OpenAI function-calling); the distilled 4B is
the §8.1 specialist; frontier + stock-4B are anchors. Reproducible via `headtohead_multiturn.sh`.

| Model | params | hard-gate task-completion |
|---|---|---|
| DeepSeek-V4-pro (frontier anchor) | — | **100%** |
| **Qwen3-4B-2507 — distilled** | **4B** | **100%** |
| Gemma-4-12b-qat | 12B | 83% |
| Qwen3-4B-2507 — stock (+plan prompt) | 4B | 75% |
| Gemma-3-12b | 12B | 33% |

**The distilled 4B matches frontier and beats both Gemma-12B variants at ⅓ the parameters** —
higher agentic accuracy *and* smaller/faster/less-RAM. For a multi-turn agentic app, the
distilled 4B is the clear winner over the incumbent.

**Honest framing:** the 4B is *specialized* on this domain (GorillaFileSystem) via cheap
frontier-distillation; Gemma is *zero-shot*. The claim is the project thesis — *a cheaply
specialized small model beats a larger general model on the target task* — **not** "4B > 12B in
general." Distilling Gemma the same way would likely lift it too. Caveats: Gemma-3-12b's 33%
partly reflects weaker tool-call formatting (Gemma-4-qat's 83% shows the protocol is fine, so
most of the gap is real capability); Pace's exact production Gemma is still TBD (if Gemma-3, the
upgrade is dramatic; if Gemma-4-qat, still +17pp at ⅓ size); decode tok/s + RAM (the 4B wins both
structurally) and single-turn (distilled 4B ~83) are the remaining leaderboard columns.

## 8.3 Domain saturated at 4B + a free frontier backend (2026-06-16)

Pushed a **longer-horizon `veryhard` tier** (6-8 turns, 9-16 calls, heavy cd-navigation; new
templates the 4B never trained on — `gen_multiturn_trajdata.py … veryhard`) to see if a *harder*
gate would finally separate the distilled 4B from frontier and justify a bigger model:

| Model | veryhard (12) |
|---|---|
| gpt-5.5 (true frontier) | **100%** |
| **Qwen3-4B-2507 — distilled** | **100%** |
| DeepSeek-V4-pro | 83% |
| Qwen3-4B-2507 — stock (+plan) | 25% |

**The distilled 4B aces it too — matching the strongest frontier (gpt-5.5) on longer unseen
tasks, while stock collapses to 25%.** Conclusion: **the file-ops agentic domain is saturated at
4B** — a harder *file-ops* gate won't discriminate it, so a distilled 12B has no payoff here. The
real open question is **breadth** (other BFCL backends — trading/ticketing/travel — that the 4B
never trained on), not depth. (DeepSeek's 83% < gpt-5.5's 100% just means DeepSeek is a slightly
less reliable frontier on fiddly 16-call navigation; the gate is sound — true frontier aces it.)

**Free frontier backend (cost fix):** validation + teacher trajectories now run on the **Codex
CLI (`gpt-5.5`), free under subscription** — `scripts/bfcl_multiturn_codex.py` drives it
single-shot per step via `codex exec --output-schema` (forced JSON tool-calls), reusing the same
BFCL executor + checker. Gotcha: OpenAI strict structured-output requires `additionalProperties:
false` on every object and forbids free-form objects, so `arguments` is passed as a JSON *string*
and parsed. This retires the paid DeepSeek API for routine frontier work.

## See also
- [distillation.md](../distillation.md) — the distillation workflow + match-vs-from-scratch protocol.
- [eval-methodology-2026-06-08.md](./eval-methodology-2026-06-08.md) — broader eval protocol.
- [performance.md](../performance.md) — the WASM register/cache-blocked matmul finding (microbench vs real-workload).
- `AGENTS.md` → "Eval philosophy" — the frontier-ceiling gate + reach-frontier-at-lower-cost goal.
