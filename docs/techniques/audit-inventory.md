# Audit 2026 Technique Inventory

This is the structured companion to [`../audit_2026.md`](../audit_2026.md).

`audit_2026.md` is a prose audit. It mixes defaults, experimental features,
flagged alternatives, and a few duplicate mentions where the same method is
useful under different conditions. This file makes that treatment explicit.

## Inventory Standard

An audit row is **not automatically an attempt**.

| Surface | Meaning | Where it belongs |
|---|---|---|
| Technique row | A method, feature, or implementation surface from `audit_2026.md` | This file |
| Measured experiment | A concrete before/after run with evidence, lesson, and next action | [`../attempt-ledger.md`](../attempt-ledger.md) |
| Recipe | A concrete application of a method to a target/eval | Target-specific backlog, such as [`sql-technique-backlog.md`](sql-technique-backlog.md) |
| Product cleanup | CLI, source layout, or UX simplification work | PRD/backlog, not attempt ledger |

## Coverage Summary

Source: `docs/audit_2026.md`.

| Bucket | Audit rows | Treatment |
|---|---:|---|
| Keep/default | 45 | Default or required capability, but still needs run-level evidence before quality claims |
| Experimental | 8 | Accessible for learning or future recipes, not default |
| Flagged | 30 | Kept with caveats; use only when the condition matches |
| Delete | 0 | Empty under the stated conviction bar |
| **Tracked audit rows** | **83** | Row-level inventory, including intentional duplicate mentions |

## Duplicate / Overlap Notes

Some techniques appear in more than one bucket because the audit records both
current utility and future conditions:

| Technique | Why duplicated | Exact treatment |
|---|---|---|
| YOCO | Listed as experimental and also flagged under architecture variants | Keep as long-context memory experiment; not a short-context speed default |
| BPE-dropout | Listed in data-side results and flagged as training-time exotic | Stable implementation; quality benefit still needs behavioral eval |
| MoE | Experimental architecture and separate measured dense-compute smoke | Capacity experiment until sparse dispatch exists |
| Gradient checkpointing | Default keep at large scale, but scale-dependent | Use for memory-bound large runs, not tiny/small defaults |

## Keep / Default Rows

| Area | Technique | Evidence in audit | Ledger treatment |
|---|---|---|---|
| Training | AdamW optimizer | Outperformed Lion/Sophia/Muon/Adafactor in 200-step tests | Technique row; optimizer comparison rows stay flagged unless promoted to attempts |
| Training | bf16 dtype | Memory + range win; matches flagship training | Technique row |
| Training | Cosine LR + warmup | Used in flagship training runs | Technique row |
| Training | Gradient clipping | Prevents bf16 blowups; no measured downside | Technique row |
| Training | Gradient checkpointing | Behemoth B=4 ctx=1024 `27.7GB -> 17.8GB` | Normalized in attempt ledger as `gradient-checkpointing-mac-training` |
| Training | Sample packing for SFT | CoV(length*freq) `0.582 -> 0.061` | Normalized in attempt ledger as `data-perf-sample-packing-bpe-dropout` |
| Training | Persistent token cache | `10-30 min` saved per re-run | Technique row; not enough standalone run detail here |
| Training | CPU speedup bundle | `5.0 -> 6.8 step/s` on small B=16 | Normalized in attempt ledger as `cpu-speedup-bundle` |
| Tokenization | BPE via smollm2 | Used for real-text training | Technique row |
| Tokenization | Byte-level vocab=256 | Powers browser gallery | Technique row |
| Tokenization | HFTokenizer wrapper | Loads HF-family models | Technique row |
| Alignment | SFT with response masking | ChatML, Alpaca, Llama, plain templates work | Technique row |
| Alignment | DPO | Smoke tested; loss converges | Technique row |
| Alignment | SimPO | Reference-free, lower memory | Technique row; failed SQL hygiene SimPO is a separate attempt |
| Alignment | ORPO | Merges SFT + DPO stage | Technique row |
| Alignment | KTO | Single-side feedback path | Technique row |
| PEFT | LoRA | Standard base adapter | Technique row |
| PEFT | DoRA | `5-10%` better than LoRA at same rank in smoke | Technique row |
| PEFT | LoRA-FA | Halves trainable params | Technique row |
| PEFT | LoRA+ | B-LR multiplier verified | Technique row |
| PEFT | NEFTune | Paper-backed one-line SFT win; smoke tested | Technique row |
| PEFT | Adapter file format | `.lora` round-trip safety | Technique row |
| PEFT | Multi-LoRA composition | Composition implementation exists | SQL static composition failure is normalized separately |
| Inference | KV cache | `470 vs 209 tok/s` on flagship | Technique row; later KV optimization bundle normalized |
| Inference | KIVI int8 KV | `100%` greedy-prefix match vs fp32 on flagship | Normalized in attempt ledger as `streamingllm-kivi-cache-compression` |
| Inference | Prefix caching | System-prompt reuse | Normalized in attempt ledger as `kv-cache-optimization-bundle` where measured |
| Inference | StreamingLLM sink | Quality preserved at 500 tokens | Normalized in attempt ledger as `streamingllm-kivi-cache-compression` |
| Inference | Speculative decoding, vanilla draft | Standard decode technique works | Technique row; Medusa/EAGLE heads normalized separately |
| Inference | HF model loading | Loads Qwen, Llama, Mistral, Phi | Technique row |
| Inference | AWQ reader | Loads AWQ-quantized HF model | Technique row |
| Inference | ANE Core ML inference path | `365 tok/s` on Shakespeare via Core ML | Technique row; parked unless deploy path reactivates |
| Inference | OpenAI-compatible HTTP serve | Curl-tested; lm-eval-harness compatible | Technique row |
| Eval/bench | `tinygpt eval` | Perplexity `4.71` on flagship matches val | Technique row |
| Eval/bench | `tinygpt bench` | TTFT `1.91ms`, `794 tok/s` on Shakespeare | Technique row |
| Eval/bench | `tinygpt score-bench` + manifest patcher | Browser leaderboard pipeline works | Technique row |
| Eval/bench | lm-evaluation-harness HTTP adapter | OpenAI-compatible serve verified | Technique row |
| Quality | 40 XCTests | CI gate with core coverage | Technique row |
| Quality | swiftformat + CI lint | 0 violations on 76 files | Technique row |
| Quality | Crash-recovery tests | SIGTERM-race verified | Technique row |
| Quality | GitHub Actions CI | Mac + Ubuntu runners | Technique row |
| Infrastructure | Atomic save-every + resume | SIGINT pause of v5 demonstrated | Technique row |
| Infrastructure | OOMGuard | Pre-flight memory aborts doomed configs | Technique row |
| Web playground | WebGPU + WASM browser training | Gallery models trained in browser | Browser/product attempts normalized where concrete |
| Web playground | Dynamic doc route | Docs web-visible | Factory/docs enforcement surface |
| Web playground | Leaderboard page | Scored entries exist | Technique row |

## Experimental Rows

| Technique | Audit reason | Treatment |
|---|---|---|
| MoE | Pedagogical paper reimplementation | Normalized dense-compute smoke; future sparse dispatch needs new attempt |
| Distillation | Standard, not used at scale | Candidate method for agent factory recipes |
| Magpie synthetic data generation | Useful for future agent traces | Future data method, not attempted here |
| Evolution Strategies | Research curiosity | Parked learning/research surface |
| Tuned lens | Educational interpretability tool | Reference/learning surface |
| Logit lens / attention heatmap / activation patching / layer ablation | Educational interpretability tools | Reference/learning surface |
| YOCO | Long-context cache halving | Normalized smoke; future long-context gate needed |
| Sliding window attention | Bounded long-context attention | Future long-context method |

## Flagged Rows

| Area | Technique | Tested / observed | When useful |
|---|---|---|---|
| Optimizer | Lion | 200 steps tiny; loss `3.18` vs AdamW `2.62` | Longer convergence runs |
| Optimizer | Sophia | 200-step Sophia-light; slightly behind AdamW | Full Sophia variant may differ |
| Optimizer | Muon | Tiny preset; `5.2` vs `16.3 step/s` | Larger models where overhead amortizes |
| Optimizer | Adafactor | Huge preset 50 steps; 2x slower but lower state memory | Big memory-bound training |
| Architecture | DiffAttention | 22M smoke; no measured benefit | Larger or long-context reasoning runs |
| Architecture | MoD soft routing | No compute savings | Hard top-k plus scatter_add |
| Architecture | MTP | Smoke train; marginal regularization | Much larger bases |
| Architecture | ALiBi | Not tested at long context | Context extrapolation |
| Architecture | Sliding window attention | Not tested above ctx 4k | Long agent histories |
| Architecture | YOCO | `-51%` cache, `-12%` short-context decode | Long contexts above short-ctx crossover |
| Stability | DeepNorm | Untested in flagship runs | Very deep networks |
| Stability | Layer-wise LR decay | Not wired to a real run | Fine-tuning specialists |
| Stability | Embedding RMSNorm | v4/v5 with step-1 spike plus small lift | Needs longer controlled comparison |
| Training exotic | GaLore | 100-step loss descends; memory win unrealized | Optimizer-state surgery lands |
| Training exotic | BPE-dropout | 100 steps; regularization cost | Robustness evals |
| PEFT variant | VeRA | 30 steps; 512x fewer trainable params | Many-specialist factory |
| PEFT variant | LoftQ | 30-step simulated int4 init | Real int4 base model exists |
| PEFT variant | AdaLoRA | 30-step importance scoring | Rank reallocation implemented |
| PEFT variant | RsLoRA | Scale applied | High rank adapters |
| PEFT variant | PISSA init | Faster early convergence | SFT default candidate |
| PEFT variant | LayerDrop | Degraded fine-tune quality | Pretraining at depth |
| Quantization | SmoothQuant | Calibration works; no float matmul gain | int8 matmul kernel lands |
| Quantization | HQQ storage-only | Roundtrip shrinks file; no runtime win | Packed int4 matmul kernel |
| Quantization | GPTQ from-scratch | Rel error `0.1064`; loads and samples | Own-model export path |
| Quantization | QAT | 30-step loss descends; qat-err bounded | int4/int8 specialist deployment |
| Pruning | Unstructured pruning | 50% sparsity; gzip `-38%` | Download-size only until sparse matmul |
| Pruning | Structured head pruning | Drop 4/8 heads; quality degrades | Physical removal implemented |
| Pruning | Structured layer pruning | 9.6M -> 8.0M, coherent samples | Real topology/wallclock path |
| Spec heads | Medusa heads | 50 head-train steps; 21-23% acceptance | Long head training with production recipe |
| Spec heads | EAGLE-2 | 50 head-train steps; 26.5% acceptance | Long head training with production recipe |

## Delete Rows

The delete bucket is intentionally empty in `audit_2026.md`.

The actionable cleanup is not source deletion. It is:

1. Inline `AUDIT FLAG` notes at entry points.
2. CLI curation into simple defaults plus experimental flags.
3. Help text and docs that present one recipe per capability.

Those are product cleanup tasks, not attempt records.
