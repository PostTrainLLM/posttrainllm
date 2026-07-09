# GPU / research backlog — what's left, and how to do it

The PRDs below can't be finished-and-verified in a CPU sandbox: they need a GPU
(training is the deliverable), special hardware, network installs, or are
multi-week from-scratch model builds. The **verifiable scaffolding ships** (eval
gates, `posttrainllm generate`, recipes) — what remains is the run/implementation.
This is the implementation outline for whoever picks them up on a GPU box.

> Honesty note: I deliberately did **not** write thousands of lines of untested
> model internals (a from-scratch VLM/diffusion/TTS in one shot would be a
> hallucinated approximation). Each entry is an outline, not fake code.

## Specialist training tier (eval gate + `generate` already ship)

The pipeline is built: `sft --llrd` → `posttrainllm generate` → the eval gate. What's
left is the GPU run + (for some) a domain parse step.

- **A1 / B1 / B8** — recipes ship (`scripts/recipes/a1-tool-caller.sh`,
  `b1-sql.sh`, `b8-indic.sh`). Run on GPU with real SFT data; gates: `eval-bfcl
  --lora` (+3pp), `eval-sql`, `eval-milu`.
- **B2–B7 router** — needs a `router-predict` step (run the trained classifier
  vs the FSM over BFCL queries → `{method,predicted_tool,gold_tool}`), then
  `eval-router`. The classifier/FSM exist (`ToolRouterModel`, `PaceFastRouter`);
  wire a predict loop, then the bake-off scorer is ready.
- **B5 / B35** — `generate` produces the raw response; add a thin parse
  (`response → {defer_pred}` for B5; `→ {found_issues:[]}` for B35), then
  `eval-escalate` / `eval-review` score it.
- **B25-V2** — implement `RelevanceHead` (Linear d_model→2 on the final
  residual) + `--loss relevance-bce` in `sft`; the `compress` CLI swaps its
  lexical scorer for the head's per-token scores. `eval-scaledown` already gates it.

## Quantized-training tier

- **qlora** — implement `QLoraLinear`/`QDoraLinear`: a frozen packed
  `QuantizedLinear` base (the inference load already ships, `HFModel.swift`) with
  LoRA on top, forward via `quantized_matmul`. Today `sft --qlora` fake-quants
  (LoftQ init on an fp16 base); the packed-base layer is the memory unlock.

## Inference / port tier

- **vision-M4** — finish the Qwen3-VL forward in `HFVLMLoader.load()` (currently
  `.notImplemented`): weight materialization, mRoPE, image-token scatter,
  deepstack injection, then a parity test vs `mlx_lm`.
- **macos26-ANE / specialist-pace** — both already shipped their engineering;
  the open items are measured runs / a closed product loop, not new code.

## Hardware / network runs (no new code)

- **B16** M5 NA prefill bench — run `scripts/bench_decode.py` on M5, record the
  before/after in `docs/research/mac_decode_baseline_m5pro.md`.
- **C5 / B9 full** — run `bench_decode_thermal.py` (30 min) / `bench_energy.py`
  under `sudo` (see `setup_powermetrics_sudoers.sh`); the harnesses ship.
- **E6-V2** — `install-scalebench.sh` then a wrapper over the official harness.
- **B17 round-trip** — `pip install sae_lens`, load the exported SAE, assert parity.
- **B23/B26/B32/B33** — code ships; run the live GPU eval gates.

## Tier 5 — multi-week from-scratch model builds

Each is a research project, not a session task. Outlines:

- **5.1 reasoning-on-22M (GRPO)** — a GRPO/DAPO loop: rollout buffer,
  group-normalized advantage, KL-to-ref, on the file-ops env. Reuse the verified
  MLX GRPO primitives noted in the PRD.
- **5.2 testtime-compute-scaling** — a `scan-testtime` harness over the existing
  `bon` (best-of-N) + a FLOPs counter → quality-vs-FLOPs curve. Smallest of the
  seven; mostly orchestration over shipped primitives.
- **5.3 vision-language-toy** — LLaVA-style: ViT encoder + projector + LM, from
  scratch. New `VLForward`, `TrainVL`, `EvalVQA`.
- **5.4 diffusion-lm-micro** — discrete masked-denoising 22M: `DiffusionLM`
  forward + masked-denoise train + iterative sample.
- **5.5 sparse-moe-kernels** — blocked upstream on MLX `scatter_add`; dense MoE
  is the shipped fallback.
- **5.6 tts-toy** — EnCodec tokens + autoregressive LM over codebook IDs.
- **5.7 explainer-video-model** — storyboard DSL + renderer + a visual-planner
  specialist (depends on 5.3).

See `docs/prds/STATUS.md` for the per-PRD verdicts this complements.
