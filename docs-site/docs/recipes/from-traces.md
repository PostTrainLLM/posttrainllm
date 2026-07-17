---
title: "From .atraj rollouts to a trained specialist"
description: "B22 + B29 + B30 + posttrainllm sft chained — the closed substrate→training loop, V1."
---

# From `.atraj` rollouts to a trained specialist

This recipe walks the **substrate-refinement cycle** that closes between
B22 (token-preserving trajectory recorder), B29 (trace-to-training-data),
B30 (reasoning-depth classifier for mix balancing), and `posttrainllm sft`.

Inputs in / model out, no LLM judge in V1, no DPO.

## The loop

```
agent rollouts → .atraj files (B22)
   ↓
posttrainllm traces-to-data        (B29)   →  raw-sft.jsonl
   ↓
posttrainllm reasoning-classify --train    →  reason.tgfr
posttrainllm reasoning-classify --score    →  scored.jsonl     (B30)
posttrainllm reasoning-classify --filter   →  balanced.jsonl
   ↓
posttrainllm sft --data balanced.jsonl --base <gallery-pin>
```

## Step 1 — collect trajectories

```bash
posttrainllm agent specialist.tinygpt --tools tools.json \
  --trajectory-dir ~/.cache/posttrainllm/atraj/tool-call-v1 \
  --trajectory-task "tool-call" \
  --single "look up the weather in Paris"
```

Every rollout emits one `<uuid>.atraj`. Keep them under a per-task
directory so B29 can `--task tool-call` them as a batch. See
[`docs/agent_runtime.md`](../agent_runtime.md) §"Token-preserving
trajectories (B22)" for the format.

## Step 2 — turn the trajectories into SFT JSONL

```bash
posttrainllm traces-to-data ~/.cache/posttrainllm/atraj/tool-call-v1 \
  --task tool-call \
  --out raw-sft.jsonl
```

Default filters: tool-echo drop (assistant turns that emitted a
tool-call JSON but never reached `{"answer": ...}` are excluded —
those are training-data noise, not training-data signal), exact dedup
on `(prompt, response)`, and MinHash near-dedup on the prompt at
Jaccard ≥ 0.85.

Tune the MinHash threshold per corpus:

```bash
posttrainllm traces-to-data ~/.cache/posttrainllm/atraj/tool-call-v1 \
  --task tool-call \
  --minhash-threshold 0.7 \
  --out raw-sft.jsonl
```

Run with `--dry-run` first to preview the per-stage drop counts before
committing to a write.

## Step 3 — balance the depth mix

Trace dumps are single-hop heavy by default (those are the prompts
that succeed soonest in production). Without balancing, the trained
specialist regresses on multi-hop and comparison prompts even though
both are present in `raw-sft.jsonl`. B30 fixes this:

```bash
# Train the depth classifier ONCE per corpus family.
posttrainllm reasoning-classify \
  --train labeled-seed.jsonl \
  --heldout labeled-heldout.jsonl \
  --out reason.tgfr

posttrainllm reasoning-classify --score raw-sft.jsonl \
  --model reason.tgfr --out scored.jsonl --field user

posttrainllm reasoning-classify --filter scored.jsonl \
  --target-mix "single=0.3,multi=0.5,comparison=0.2,other=0.0" \
  --out balanced.jsonl
```

The Castform-aligned `0.3/0.5/0.2` mix biases toward the depth that
regresses most often. Adjust per the per-class evals you care about.
See [`balanced-training-mix.md`](balanced-training-mix.md) for the
full B30 details.

## Step 4 — fine-tune

```bash
posttrainllm sft --base <pin-from-gallery> --data balanced.jsonl ...
```

## What V1 is NOT

These are explicit deferrals, all flagged in the CLI so the operator
knows what's missing:

- **No LLM-pivot judge filter.** `--judge-model <id>` is reserved but
  exits non-zero in V1 — wiring the judge would need a live LLM, and
  this recipe is intentionally compute-light. Coming in B29 V2 via
  `posttrainllm judge` (E7) as a subprocess.
- **No DPO-pair construction.** `--mode dpo` is reserved but rejected;
  V1 ships `--mode sft` only. DPO needs either a per-step reward
  signal or a judge-score margin; PRD §"Open questions" picks the
  shape.
- **No external observability ingest** (Braintrust / Langfuse). The
  `.atraj` files are the V1 substrate; external ingest is V2.

## Where this lives in code

| File | Role |
|---|---|
| `Sources/TinyGPTModel/AgentTrajectory.swift` | B22 — record types + Codable I/O |
| `Sources/TinyGPT/AgentLoop.swift` | B22 — recorder hooks at every turn boundary |
| `Sources/TinyGPT/TracesToData.swift` | B29 — orchestrator |
| `Sources/TinyGPT/ReasoningClassify.swift` | B30 — depth classifier + filter |
| `evals/traces-to-data-fixtures/*.atraj` | smoke fixture (5 trajectories) |
| `evals/traces-to-data-smoke.sh` | end-to-end smoke (rows in / rows out + filter-summary asserts) |

## Pairs with

- [[balanced-training-mix.md]] — B30's standalone recipe.
- [[B35-local-agent-vertical-poc.md]] — downstream consumer.
- [[B32-eval-ci-gate.md]] — gate the trained specialist before
  promoting it to a gallery pin.
