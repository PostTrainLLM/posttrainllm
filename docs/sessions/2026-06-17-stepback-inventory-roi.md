# Step-back: what we have, the wall, and the ROI menu

Date: 2026-06-17. A deliberate pause to inventory the assets, name the wall, and
rank what's next by ROI — *before* committing to another build. Narrative of the
arc lives in [the 2026-06-16 session doc](./2026-06-16-distill-to-self-improvement.md)
and [journey §8](../learn/tool-calling-frontier-parity.md); this is the ledger + the fork.

## The arc that led here

Distillation hit frontier-parity on file-ops agentic (4B 58→100, beats Gemma-12B at ⅓
size) → the real gap was *breadth*, where specialists regress (negative transfer) →
teacher-free **ReST** lifted breadth 60→65% with depth held → then we widened the lens:
measured **Apple's on-device model** as a candidate (it can't ground actions), mined
**VibeThinker's** training recipe (SSP/MGPO/specialist-merge), and closed the
**distributed-boundary** thesis gap with a working data-parallel PoC. The honest read:
the *learning* compounded; the *product* (agentic tool-calling) is near its cheap ceiling.

## What we have (the inventory)

### Models (`~/.cache/posttrainllm/models/`)
| model | what it is | numbers |
|---|---|---|
| `mt4b_fused` | Qwen3-4B distilled, file-ops agentic specialist | **100%** hard, beats Gemma-12B at ⅓ size |
| `mt4b_rest_fused` | + teacher-free ReST iteration | depth **100%**, breadth **65%** (stock 60%) |
| `mt4b_mb_fused` | multi-backend gold-distill (the failed one) | depth 100 / breadth **31%** (negative transfer) |
| `vibethinker-3b-mlx` | converted reasoning specialist | **GSM8K 40/40 = 100%**; no tool-calling |

### Infrastructure (`scripts/`)
- **Sound, frontier-validated agentic gate** — BFCL multi-turn executor + checker, file-ops + breadth fixtures. *The moat.*
- **Backends that all speak one OpenAI-FC API:** frontier (`bfcl_multiturn_codex.py`, free gpt-5.5), local MLX (`bfcl_multiturn_eval.py`), any OpenAI server / Gemma (`bfcl_multiturn_deepseek.py`), and **Apple on-device** (`fm_agent_bridge.swift`, new this session).
- **Teacher-free self-improvement loop** — `rest_iterate.sh` + batched collector `rollout_fast.py` (validated: 4/8, no state corruption).
- **Distributed-boundary PoC** — `dist_dp_poc.py`: data-parallel all-reduce verified bit-identical across n=2/4 ranks on one Mac.

### Findings / intel (durable)
- **Gold-cloning ≡ distillation only when args derive from the prompt;** data-dependent args need real interleaved trajectories (journey §8.5).
- **Apple on-device floor:** can't ground actions — agentic gate 25% (full catalog) / **0%** (compact, no schemas → wrong args); planner gate action-grounding 13%, OOS-refusal 95%. 4096-token context can't hold a real tool catalog. *Intel, never a dependency* — decision: not building on Apple's model.
- **VibeThinker recipe** ([diversity doc](../learn/diversity-driven-small-model-reasoning.md)): Diversity-Exploring Distillation + MGPO + **specialist weight-merging** — the last is the direct antidote to our negative-transfer wall.

## The wall

1. **Cheap distillation is maxed on trained domains.** File-ops saturated at frontier; breadth is a long-tail grind (+5pp from ReST, and each further point costs much more).
2. **No forcing function to an outcome.** Each result spawns three experiments — rich for learning, but nothing was *shipping*. That's why it felt like it wasn't going anywhere.
3. **Shipping ≠ wiring.** `mt4b_fused` speaks BFCL `tool_calls`; Pace's planner needs the v10/v11 intent-envelope (`spokenText` + 7 intents incl. safety). Shipping it = **re-distillation on Pace's action surface**, gated by the v11 ship gate — a real project, not a plug-in.

## The ROI menu (what we can do)

Ranked by payoff/effort; honest about which axis each serves.

| # | option | effort | payoff | axis | note |
|---|---|---|---|---|---|
| 1 | **Specialist-merge experiment** | LOW–MED | MED | research | cheapest shot at the breadth wall; infra exists; either lifts >65% or closes the lane honestly |
| 2 | **MGPO auto-curriculum patch** to ReST | LOW | MED | research | re-weight sampler to the 30–70% frontier band; cheap efficiency gain |
| 3 | **Model radar** (systematic small-model discovery) | LOW | MED | intel | turns VibeThinker-style luck into a pipeline; on-thesis |
| 4 | **Re-distill mt4b on Pace's action surface** | HIGH | HIGH | **product** | the real shipped outcome; gated by the v11 ship gate (hard unhappy-path dims) |
| 5 | **Serving/throughput** (continuous batching) | MED–HIGH | HIGH | both | ~10× rollouts (unblocks all future RL) + Pace latency win |
| 6 | **Pivot: distributed boundary** | MED | learning | learning | build on the PoC (toy ZeRO, 2-Mac Thunderbolt); positions for scale |
| 7 | **Consolidate & stop** | done | closure | — | this doc is the capstone; reassess fresh |

**Honest recommendation:** if the goal is a clean *verdict* on the agentic lane, do **#1 (specialist-merge)** — cheap, attacks the measured wall, and gives a yes/no. If the goal is a *shipped outcome*, **#4** is the only one that ends with a Pace capability, but commit to it as a real project (it needs the v11 corpus + ship gate). #5 is the best "unblocks everything" bet if we intend to keep doing RL.

## Pending (in flight as of writing)
- VibeThinker-as-agentic-distill-base: SFT done, hard/breadth eval running (does a reasoning specialist distill into a better agent than Qwen3-4B?).
- Apple compact-52: trending 0% — confirms the catch-22.
