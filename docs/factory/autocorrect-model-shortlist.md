# Autocorrect base-model gate

Research and the first bounded bake-off were completed on 2026-07-25. The
operator approved the three pinned downloads and one offline greedy pass per
candidate. No training, adapter work, packaging, or shipping was performed.
The bake-off remained limited to three Apache-2.0 encoder-decoder checkpoints:

| Candidate | Revision | Parameters | Primary artifact | Why it remains |
|---|---|---:|---:|---|
| `google-t5/t5-small` | `df1b051c49625cf57a3d0d8d3863ed4d13564fe4` | 60.5M | 242,043,056-byte safetensors | Smallest control; SentencePiece fragmentation on misspellings must be measured. |
| `google/flan-t5-small` | `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab` | 77.0M | 307,867,048-byte safetensors | Stronger zero-shot control; rewriting and overcorrection are explicit risks. |
| `google/byt5-small` | `68377bdc18a2ffec8a0533fef03b1c513a4dd49d` | about 300M | 1,198,627,927-byte PyTorch bin | Byte-aware typo candidate; longest sequences and highest resource risk. |

T5Gemma is excluded from the first bake-off: the small release is gated and
Gemma-licensed, and the 2B/2B release exceeds the target's practical parameter
and memory envelope. The official MLX T5 example supports T5/FLAN inference but
does not provide an adaptation loop and hard-codes a `t5-base` tokenizer.
Transformers plus PEFT on MPS is therefore the first proof path; ByT5 also lacks
a directly supported MLX conversion/tokenizer path.

Primary records:

- [T5-small](https://huggingface.co/google-t5/t5-small/tree/df1b051c49625cf57a3d0d8d3863ed4d13564fe4)
- [FLAN-T5-small](https://huggingface.co/google/flan-t5-small/tree/0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab)
- [ByT5-small](https://huggingface.co/google/byt5-small/tree/68377bdc18a2ffec8a0533fef03b1c513a4dd49d)
- [Official MLX T5 reference](https://github.com/ml-explore/mlx-examples/tree/main/t5)

## Executed download and runtime gate

The executed downloads were:

```bash
hf download google-t5/t5-small config.json generation_config.json model.safetensors special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json --revision df1b051c49625cf57a3d0d8d3863ed4d13564fe4 --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/t5-small-df1b051
hf download google/flan-t5-small config.json generation_config.json model.safetensors special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json --revision 0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/flan-t5-small-0fc9ddf
hf download google/byt5-small config.json generation_config.json pytorch_model.bin special_tokens_map.json tokenizer_config.json --revision 68377bdc18a2ffec8a0533fef03b1c513a4dd49d --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/byt5-small-68377bd
```

The disposable runtime was Python 3.12, PyTorch 2.13.0, Transformers 5.14.1,
and SentencePiece 0.2.2. Inference reran with `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`; the committed runner is
`scripts/research/autocorrect_base_bakeoff.py`.

Planning estimates retained for comparison:

| Candidate | Download | First load | Peak inference RSS | LoRA pilot |
|---|---:|---:|---:|---:|
| T5-small | 30-90 seconds | 5-20 seconds | 0.7-1.2 GB | 30-120 minutes |
| FLAN-T5-small | 35-120 seconds | 5-25 seconds | 0.9-1.5 GB | 45-150 minutes |
| ByT5-small | 2-5 minutes | 15-60 seconds | 2.5-4.0 GB | 2-8 hours |

All three artifacts total about 1.76 GB. Reserve 3.5-6 GB of working disk,
including a disposable pinned Python environment. ByT5 LoRA may use 5-8 GB of
unified memory and must begin with a one-step measurement. Cleanup is limited
to the three explicit revision-suffixed directories above; shared Hugging Face
and package-manager caches are not cleanup targets.

These commands and the pinned runtime were executed once under the owner's
approval for this bounded bake-off. The revision-suffixed local directories
remain available, so the next stage does not require another download.

## Measured result

Apple M5 Pro, 48 GB unified memory; one warm-up and one complete 18-row greedy
pass per candidate:

| Candidate | Error reduction | Clean preservation | Protected spans | Peak RSS | Median TTFT | Median end-to-end |
|---|---:|---:|---:|---:|---:|---:|
| T5-small | -1468.75% | 0% | 46.67% | 820 MiB | 24.3 ms | 124.6 ms |
| FLAN-T5-small | 6.25% | 66.67% | 86.67% | 584 MiB | 29.1 ms | 124.5 ms |
| ByT5-small | -4737.5% | 0% | 13.33% | 828 MiB | 53.7 ms | 899.3 ms |

Plain T5 rewrote or translated inputs. ByT5 repeated input fragments and
breached both frozen latency gates. FLAN-T5-small is not useful zero-shot, but
it is the smallest candidate that mostly copies input, shows any positive
error reduction, and stays inside the resource envelope. It therefore advances
only to the future adapter/training-feasibility gate.

The selected frozen baseline is:

- base: `google/flan-t5-small` at
  `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`;
- prompt: `Correct only the typing errors in the following text. Return only
  the corrected text:\n{text}`;
- precision/device: float32 on MPS;
- decoding: greedy, one beam, no sampling, at most 96 new tokens;
- trainable failure slices: missed edits across the supported typo families,
  code-like formatting damage, and deliberate whitespace preservation.

Reproduce the selected offline baseline:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false uv run --isolated --python 3.12 --with torch==2.13.0 --with transformers==5.14.1 --with sentencepiece==0.2.2 python scripts/research/autocorrect_base_bakeoff.py --model-key flan-t5-small --model-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/flan-t5-small-0fc9ddf --output-dir runs/autocorrect-base-bakeoff-v1 --device mps
```

Raw predictions, per-row timing/tokenization, complete slice metrics, runtime
versions, and the selection record are committed in
`evals/autocorrect/base-bakeoff-v1.json`. Model weights remain local and
ignored. Immediate approval is still required for adapter implementation,
compilation, tiny-overfit training, or a pilot.
