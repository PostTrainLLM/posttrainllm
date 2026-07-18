---
title: "Training guide"
description: "`posttrainllm train --depth N` derives **every** pretrain hyperparameter from"
---

# Training guide

## The `--depth` single knob (B18)

`posttrainllm train --depth N` derives **every** pretrain hyperparameter from
one number — architecture *and* the learning-rate / batch / step schedule —
following the nanochat surface ([karpathy/nanochat](https://github.com/karpathy/nanochat))
and the Chinchilla compute-optimal corner ([Hoffmann et al. 2022](https://arxiv.org/abs/2203.15556)).

Any explicit flag (`--max-lr`, `--steps`, `--batch`, …) overrides the
derived value, with a warning. The derivation lives in
`native-mac/Sources/TinyGPTModel/DepthDerivation.swift` (`deriveHP`).

### Derivation

| quantity | rule |
|---|---|
| nLayers | `N` |
| dModel | `64 · N` (head_dim 64, GPT-2/Llama shape) |
| nHeads | `N` |
| dMlp | `4 · dModel` |
| params (non-embed) | `12 · L · d²` |
| tokens | `regime · params` — chinchilla = 20×, overtrained = 40× |
| peak_lr | `3e-3 · √(512/dModel)`, clamped to `[1e-4, 6e-3]` |
| batch (seqs) | `⌈32 · dModel / seqLen⌉` |
| total_steps | `⌈tokens / (batch · seqLen)⌉` |

### Derived table (chinchilla regime, seqLen 1024)

| depth | dModel | dMlp | params | peak_lr | batch | steps | tokens |
|---|---|---|---|---|---|---|---|
| 4  | 256  | 1024 | 3.1M  | 4.24e-3 | 8  | 7,680   | 62.9M |
| 12 | 768  | 3072 | 84.9M | 2.45e-3 | 24 | 69,120  | 1.70B |
| 24 | 1536 | 6144 | 679M  | 1.73e-3 | 48 | 276,480 | 13.6B |
| 36 | 2304 | 9216 | 2.29B | 1.41e-3 | 72 | 622,080 | 45.9B |

`--regime overtrained` doubles tokens (and steps); architecture and peak_lr
are unchanged. These are a documented approximation of nanochat's curve, not
a port of its exact constants — `DepthDerivationTests` pins the numbers.

## Learning-rate schedules

`--lr-schedule {cosine,wsd,constant}` (default cosine; `wsd` is
warmup-stable-decay). For WSD, `--decay-shape {1-sqrt,cosine,linear}` (B11)
selects the decay-phase curve (default 1-sqrt, MiniCPM). `--llrd γ` (B15)
adds layer-wise LR decay on the `sft`/`dpo`/`finetune` paths.
