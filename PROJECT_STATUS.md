# Project Status

Last updated: 2026-06-18

## Current Scope

TinyGPT is a from-scratch GPT-2-shaped transformer project with browser training/inference, Python/PyTorch references, C++/WASM, WGSL/WebGPU acceleration, and a native macOS research track for local model experimentation.

For Pace work, TinyGPT is now the development-time factory and eval lab: it produces planner LoRA artifacts, grammar/eval assets, dataset synthesis scripts, and porting helpers. Pace owns production runtime integration; shipped Pace should not depend on `tinygpt serve` or a localhost daemon.

## Done

- The original 10 milestone browser/research roadmap is complete and merged to main.
- Implemented work includes PyTorch baseline, training, LoRA, evaluation suite, browser WASM, WebGPU, checkpointing, metrics dashboard, write-up, and public repo readiness.
- The README documents shipped WebGPU, Memory64, FlashAttention-style work, performance lessons, and negative results.
- A native macOS app track exists for Hugging Face Llama architecture support and LoRA fine-tuning.
- Future work is documented around the single-machine roadmap rather than the completed browser milestone list.
- The Pace v9 serve path now precomputes tokenizer byte tables once at server boot for much faster grammar-constrained first-token latency. A trie-based grammar-mask experiment was implemented but left disabled after measurement showed it was slower than the legacy path.
- Pace v9/v10 grammar and dataset-helper assets are staged as factory inputs, with remaining train/eval/runtime work tracked as SaaS Maker tasks instead of uncompleted PRD files.
- The eval methodology gate found by #270 is no longer a vague blocker: FakePace/rule-baseline evidence and v2 fixtures exist in `scripts/fake_pace.py` and `docs/learn/eval-methodology-2026-06-08.md`.
- `tinygpt eval-gate` has the no-GPU gate path, baseline re-stamping, `--passes`, repeated-run uncertainty reporting, and optional B23 budget metadata in `gate-result.json`; Swift eval rows emitted via `EvalHarnessSupport` now carry the same protocol block when a budget is provided.
- `tinygpt export-mlx` packages distilled/trained `.tinygpt` checkpoints and fine-tuned `.lora` / `.tgla` adapters into MLX-friendly safetensors directories with config/tokenizer sidecars and a Python MLX loader helper.
- `tinygpt eval-bfcl` can pass `--tools` / `--tool-mode full|deferred` into its managed server; a one-sample demo-model BFCL smoke completed for both modes. The real B26 acceptance gate still requires the full specialist BFCL run.

## Planned Next

1. Run a real specialist through the `eval-gate` command-driven path on a self-hosted Mac runner; only then mark B32 fully ✅ in `docs/PLAN.md`.
2. Finish B23's remaining protocol work: budget logging in BFCL, τ-bench, Pace unhappy paths, and future agent-suite rows, then actual sandbox/resource enforcement.
3. Close B26 deferred-tool mode with the BFCL full-vs-deferred parity gate before flipping defaults.
4. Continue the trace-improvement loop: B22 trajectories → B29 SFT data, then add the judged/rewarded DPO path once B23/B28 make the scores auditable.
5. Preserve trained checkpoints and generated gallery artifacts unless a cleanup is explicitly requested.

## Deferred / Parked

- The original Phases 1-10 browser roadmap is complete; do not reopen it as active work.
- Larger backend/evaluation ideas such as WebNN or alternate attention paths are deferred until they have a measured reason.
- Hosted model service or commercial API scope is parked.
- Pace runtime over TinyGPT HTTP/localhost is parked; keep `serve` as a development and evaluation tool.
- New LoRA/specialist training should not be treated as meaningful without a baseline-aware eval-gate result.
