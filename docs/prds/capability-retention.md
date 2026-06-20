---
title: Capability retention under fine-tuning (PRD — backlog)
description: Measure and preserve a small model's GENERAL intelligence when we specialize it
  (tool-calling, style, persona). This session proved specialization erodes breadth — a retention
  eval battery + retention techniques, run on every fine-tune. Future work; captured for later.
status: backlog
---

# Capability retention under fine-tuning

Every specialist we train risks eroding the base model's general intelligence. We have direct,
measured evidence ([tool-calling-frontier-parity.md](../learn/tool-calling-frontier-parity.md)
§8.4–8.5): a file-ops tool-calling distill that hit **100%** on its domain dropped out-of-domain
agentic from **60→42%** and single-turn from **87→83%**; the multi-backend gold-distill dropped
breadth to **31%**. As we add more specialists (tool-callers, founder-voice / style LoRAs), *"how
much intelligence did we keep?"* must be a first-class metric, not an afterthought.

## Two halves

### 1. Measure retention — a regression suite for intelligence
A fixed "general capability" battery run **before and after every fine-tune**, reporting a
retention delta per axis:
- general reasoning (GSM8K slice + a few MMLU-style items),
- instruction-following,
- other agentic backends (the **breadth gate** — already built),
- single-turn tool-calling (**BFCL** — already built),
- coherence/fluency (perplexity on held-out generic text).

Output: a retention scorecard, e.g. *"tool-caller: +42 file-ops / −18 breadth / −4 single-turn /
−X reasoning."* Make it a **gate** — a specialist that craters general capability is flagged, not
shipped blind. Half the battery already exists (breadth gate + single-turn BFCL).

### 2. Preserve retention — techniques to try
- **Data mixing / replay** — blend a slice of general / other-domain data into the specialist SFT
  (the direct fix for the negative transfer we measured).
- **LoRA hygiene** — lower rank, fewer epochs, lower LR, fewer target layers (we saw val loss → 0.01
  = overfit; less is more).
- **KL-to-reference** (the GRPO lever) — bound drift from the base.
- **Model merging** — TIES-merge (shipped) a specialist back
  toward the base, or merge multiple specialists, to recover breadth.
- **Routing instead of merging** — keep the specialist narrow and route to it only on its domain
  (the "stock 4B is the best generalist" finding makes this attractive).

## Why now / connection
This is the **dual of the self-improving loop**
([self-improving-agents.md](self-improving-agents.md)): self-improvement *adds* capability;
retention measures what specialization *subtracts*. The auto-curriculum (training across the whole
distribution) is itself a retention strategy.

## Acceptance (when picked up)
- [ ] A `retention-battery` that scores a model on N general axes + emits a before/after scorecard.
- [ ] Run it on the existing distilled specialists (quantify what we already lost).
- [ ] Demonstrate data-mixing + LoRA-hygiene recovering breadth without losing depth.

References: catastrophic forgetting (McCloskey & Cohen 1989; the modern LLM version); replay /
rehearsal; TIES-merge (Yadav et al. 2023); journey §8.4–8.5; the breadth gate; the self-improving PRD.
