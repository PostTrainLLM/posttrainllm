# Autocorrect base-model gate

Research frozen on 2026-07-25. No weights were downloaded, no packages were
installed, and no model was loaded. The initial bake-off is deliberately
limited to three Apache-2.0 encoder-decoder checkpoints:

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

## Approval gate

The exact future downloads are:

```bash
hf download google-t5/t5-small config.json generation_config.json model.safetensors special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json --revision df1b051c49625cf57a3d0d8d3863ed4d13564fe4 --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/t5-small-df1b051
hf download google/flan-t5-small config.json generation_config.json model.safetensors special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json --revision 0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/flan-t5-small-0fc9ddf
hf download google/byt5-small config.json generation_config.json pytorch_model.bin special_tokens_map.json tokenizer_config.json --revision 68377bdc18a2ffec8a0533fef03b1c513a4dd49d --local-dir /Users/sarthak/.cache/posttrainllm/autocorrect-bases/byt5-small-68377bd
```

Planning estimates for the M5 Pro / 48 GB host, not measurements:

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

Immediate approval is still required before executing these commands,
installing the pinned runtime, loading weights, compiling, or using the GPU.
