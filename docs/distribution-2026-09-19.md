# Distribution review — 19 September 2026

Part of #148. Audience: English-speaking Mac-local model practitioners worldwide.
This is a learning-lab distribution pass, not a new experiment or commercial launch.

## Search evidence and decision

Refresh `/mlx-lora-fine-tuning`, `/evaluate-local-llm`, and
`/build-small-language-model-specialist`. These match observed how-to/evaluation
search intent and the project's retained evidence. Priority is an editorial
inference, **not a measured highest-volume ranking**.

Observed current public search results for “MLX LoRA fine tuning Apple Silicon
Mac tutorial” include the existing PostTrainLLM guide, Apple's MLX session and
multiple practical tutorials. “evaluate local LLM tool calling BFCL benchmark”
surfaces the official BFCL leaderboard. Distillation searches surface runnable
teacher/student projects. Search result position is not a stable rank receipt.

Primary sources checked:

- [Apple's MLX session](https://developer.apple.com/videos/play/wwdc2025/298/)
- [MLX-LM's LoRA instructions](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
- [BFCL](https://gorilla.cs.berkeley.edu/leaderboard)
- [MLX-LM generation implementation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/generate.py)
- [GaLore paper](https://arxiv.org/abs/2403.03507)

No Search Console query-page export or paid keyword provider was available in
this pass. Volume, difficulty, clicks and demand ordering are unavailable, not
zero. No paid calls. The remaining queries below are explicitly hypotheses
derived from recipe intent; they are not claimed as observed customer searches.

## All 18 recipes mapped

| Recipe                 | Query hypothesis / observed theme                          | Existing destination                     | Decision                           |
| ---------------------- | ---------------------------------------------------------- | ---------------------------------------- | ---------------------------------- |
| constrained-generation | constrained JSON output vs correct tool calls              | `/evaluate-local-llm`                    | Cover in evaluation gate           |
| distillation           | distill small language model tool calling (observed theme) | `/build-small-language-model-specialist` | Refresh                            |
| evolution-strategies   | evolution strategies vs backprop LLM cost                  | `/recipes`                               | Leave reference-only               |
| galore-stability       | GaLore optimizer memory vs activation memory               | `/recipes`                               | Retain measured caveats            |
| interpretability       | activation patching causal controls LLM                    | `/recipes`                               | Leave reference-only               |
| lora                   | MLX LoRA fine tuning Mac (observed theme)                  | `/mlx-lora-fine-tuning`                  | Refresh                            |
| moe                    | sparse MoE active parameters vs runtime speed              | `/recipes`                               | Retain dense-compute caveat        |
| mtp                    | multi token prediction vs speculative decoding             | `/recipes`                               | Leave reference-only               |
| optimizers             | LLM optimizer schedule controlled comparison               | `/recipes`                               | No separate page                   |
| peft-variants          | LoRA DoRA adapter comparison MLX                           | `/mlx-lora-fine-tuning`                  | Link existing recipe               |
| precision              | fp16 bf16 mixed precision numerical validation             | `/evaluate-local-llm`                    | Include runtime gate               |
| pruning                | LLM pruning smaller file vs faster inference               | `/recipes`                               | Retain storage/runtime distinction |
| quantization           | MLX quantization memory quality tradeoff                   | `/evaluate-local-llm`                    | Include load parity gate           |
| speculative-heads      | speculative decoding quality parity MLX                    | `/recipes`                               | Keep qualified caveat              |
| streaming-kivi         | KV cache quantization vs sliding window                    | `/recipes`                               | No new runtime claim               |
| sql-lineage            | SQL fine tuning execution evaluation negative transfer     | `/build-small-language-model-specialist` | Link failure evidence              |
| needle2-evaluation     | tiny tool selector safety held out evaluation              | `/evaluate-local-llm`                    | Link reject evidence               |
| parakeet-browser-asr   | browser ASR WebGPU WER latency comparison                  | `/recipes`                               | Retain closed experiment           |

After publication, compare query-page observations over complete 28-day windows
using the existing measurement pipeline. No traffic lift is claimed. A useful
qualitative outcome is a practitioner reproducing the documented workflow or
reporting a precise failure; reactions alone do not establish usability.

## Community draft — retired, never posted

**Title:** What survived our Mac-local tool-calling experiments: narrow wins,
breadth regressions, and a rejected tiny router

We've published three specialist artifacts and their evaluation notes from
PostTrainLLM, an Apple Silicon learning lab. The useful result isn't that a
small model replaces a frontier model everywhere. It's where specialization
helped, and where it failed.

Our September paired ReST requalification took a 4B candidate from 9/12 to
12/12 on a frozen file-operations depth gate, with observed unexpected side
effects dropping from 8 to 0. On the separate breadth gate it fell from 30/45
to 25/45. That is a routed file-operations candidate, not a general successor.
The sample is small, and those counts are not confidence bounds or production
safety guarantees.

The small intent router is a useful counterexample: an impressive synthetic
holdout did not survive the sealed evaluation. We kept the rejected checkpoint
and report because the failure is part of the learning artifact.

The repo also retains the earlier distillation and frontier-calibration
experiments. Their task-specific results should not be pooled with the newer
paired gate or presented as full BFCL leaderboard scores. No new training was
run for this announcement.

If you work on local specialists, I'd be interested in the regression slices
you require before routing real tasks to them—and in reproducibility failures,
not just headline scores.

- [Paired evidence](https://github.com/PostTrainLLM/posttrainllm/blob/main/evals/verified-wins/rest-requalification-result-v1.json)
- [Distilled artifact](https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled)
- [ReST artifact](https://huggingface.co/posttrainllm/qwen3-4b-rest-fused)
- [Router and limitations](https://huggingface.co/posttrainllm/pace-intent-router-v8)
- [Mac quickstart](https://github.com/PostTrainLLM/posttrainllm#quickstart-mac)

**Historical gate status (2026-09-19):** all three pre-posting gates were
satisfied — wording owner-approved, license/provenance qualification complete
on all three cards (Apache-2.0 for the two Qwen derivatives, MIT for the
from-scratch router, live on Hugging Face), and the clean-clone receipt posted
on #148. The owner closed that broad distribution issue as **not planned** on
2026-09-20 and chose on 2026-09-25 to retire this draft. It remains as research
evidence; no community submission is planned or claimed.
