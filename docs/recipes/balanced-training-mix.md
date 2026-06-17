---
title: Balanced training mix via reasoning-depth classification
description: Use B30 ahead of B29 to control single-hop / multi-hop / comparison ratios in the SFT corpus.
---

# Balanced training mix

By default a trace-dump corpus (B22 → B29) is single-hop heavy — those
are the queries that succeed soonest in real agent loops, so they
accumulate fastest. Training on the raw blob bakes in that imbalance
and makes the resulting specialist worse at multi-hop and comparison
prompts even though both are present in the data.

This recipe runs **B30** (`tinygpt reasoning-classify`) over the
synthesized JSONL before B29 hands it to `tinygpt sft`, so the depth
ratio is a knob the operator sets explicitly.

## Pipeline

```
.atraj rollouts            (B22)
   ↓
tinygpt traces-to-data     (B29)  →  raw-sft.jsonl
   ↓
tinygpt reasoning-classify --score      → scored.jsonl
tinygpt reasoning-classify --filter     → balanced.jsonl
   ↓
tinygpt sft --data balanced.jsonl       (Tier A)
```

## Step 1 — train the depth classifier (one-time per dataset family)

A small hand-labeled seed (~500 prompts spanning the 4 classes) is
enough to bootstrap. Castform's published mix examples use a
4-of-{single-hop, multi-hop, comparison, other} split; the same labels
apply here.

```bash
tinygpt reasoning-classify \
  --train labeled-seed.jsonl \
  --heldout labeled-heldout.jsonl \
  --out reason.tgfr
```

Expected output: per-class precision / recall / F1, model written to
`reason.tgfr` (~256 KB at default vocab 65 536).

## Step 2 — score the trace-dump corpus

```bash
tinygpt reasoning-classify \
  --score raw-sft.jsonl \
  --model reason.tgfr \
  --out scored.jsonl
```

Each row gains a `reasoning_depth` field. Throughput is bound by
tokenization (~hundreds of MB/s on M-series), not arithmetic.

## Step 3 — downsample to a target mix

```bash
tinygpt reasoning-classify \
  --filter scored.jsonl \
  --target-mix "single=0.3,multi=0.5,comparison=0.2,other=0.0" \
  --out balanced.jsonl
```

Aliases (`single` → `single-hop`, `multi` → `multi-hop`, `compare` →
`comparison`) are accepted. The largest feasible N is chosen so the
target ratios are achievable from on-disk supply; rows in the smallest
class become the bottleneck.

A typical first cut: `single=0.3,multi=0.5,comparison=0.2` —
Castform-aligned, biased toward multi-hop to lift the depth that
most-often regresses on raw trace dumps.

## Step 4 — train

```bash
tinygpt sft --data balanced.jsonl --base <gallery-pin> ...
```

## Notes

- **V1 is a bag-of-trigram softmax-4** (the FineWeb-Edu shape, extended
  to multiclass). Tiny, fast, deterministic. No GPU needed for either
  train or score.
- **The on-disk format is `.tgfr`** — magic `TGFR` + uint32 version +
  uint32 vocab + uint32 ngram + uint32 numClasses + per-class
  (float32 bias + vocab × float32 weights). Inference is one hash pass
  + one dot product per class.
- **Continuous-depth scoring** (e.g. "1.7-hops") is intentionally out
  of V1 scope — categorical labels match how `--target-mix` is
  expressed.
- Pairs with [[B10 quality classifier]] — depth and quality are
  orthogonal axes; run both in series for full corpus control.
