# AGENTS.md — posttrainllm

## Repository operating rules

This repository is independently operable. Its tracked instructions and
commands are authoritative; no sibling Fleet checkout is required. Protect
production stability, keep changes scoped, verify work with repo-local checks,
and record durable follow-up in this repository's GitHub Issues.

## Purpose

A **learning project**, not a deployed product: build a browser-capable
posttrainllm that trains from scratch and adapts a small base model with LoRA.
Priority is correctness and understanding over output quality or shipping.

Owner north-star: be best-in-class at Mac-local AI, learn the whole space
including the single-machine/distributed boundary, build everything buildable
on a Mac, and keep foundations ready to scale later. Failed experiments count
as learning wins. Tactically, ROI-scope per task still applies.

Durable owner goals live here in AGENTS.md, not in agent-private memory. When
the owner says to remember something, record it in a tracked project document.

History (full north-star, eval philosophy, closure text, parked CLI list):
[docs/archive/agents-history.md](docs/archive/agents-history.md).

## Eval rules (current)

- **Frontier-ceiling gate.** Before a benchmark grades Mac models, a frontier
  model must score ~100% on it. If it cannot, fix or drop the benchmark; never
  report Mac-model accuracy on it. `hermes-fc` fails this gate: it is
  training-only, never a reported metric. BFCL (AST matching) passes.
- Headline metric is "% of frontier capability retained per unit of compute,
  RAM, and $", not raw accuracy.
- Prefer the free Codex CLI (`scripts/bfcl/bfcl_multiturn_codex.py`) for
  frontier validation and teacher trajectories. DeepSeek-V4 costs money: use
  sparingly, only to cross-check.
- Tool-calling target: the smallest model that reaches frontier parity. Push
  1.7B first; step to 4B only if it plateaus.
- Own the on-device model; Apple's FoundationModels is intel and a routing
  floor, never a capability dependency. See
  [docs/learn/apple-on-device-foundation-models.md](docs/learn/apple-on-device-foundation-models.md).

## Working rules

- **Respect the build order.** Python reference, then WASM, then WebGPU. No
  browser/WebGPU path before the Python reference for that component is
  correct and tested. See `README.md` and `docs/archive/learning_roadmap.md`.
- **Correctness gates.** Before scaling, the model must overfit a tiny
  (1-10 KB) repeated dataset. If it cannot, fix model/backprop/data first. See
  `tests/README.md`.
- **Configs are the source of truth.** Exact specs live in `configs/*.json`;
  reference them rather than restating numbers.
- **File headers are the contract.** Keep a source file's header and its
  linked doc in step with the code.
- **Steal first, improve where we can.** Adopt the best existing tool,
  benchmark, kernel, or library (BFCL scorer, MLX QuantizedLinear, Rust
  `tokenizers`) before hand-rolling.
- **Best tool for the job.** Go, C/C++, Rust, Metal, Swift+MLX, PyTorch (MPS),
  and Accelerate are all fine. CUDA is dropped (no Apple-Silicon support).
- **Performance latitude.** After correctness is established, hot paths may
  drop to a faster language when it measurably helps. Keep the readable
  reference as the numerical oracle. Eval speed is I/O- and model-bound:
  parallelism, batching and a warm model server beat a language rewrite.

## Layout

See `README.md` for the directory map and `CONTRIBUTING.md` for build, test,
and lint entry points. Specs in `configs/`, guides in `docs/`, cross-cutting
tests in `tests/` (Swift in `native-mac/Tests/`, browser in `browser/src/`).

## Closed lab and fresh-experiment gate

The build phase is complete. The repo is a closed learning artifact and
practical lab around the Mac-local specialist factory loop
(target, data, post-training, eval, package, report). There is no active
target or implicit backlog; historical TODOs, PRDs and blockers are evidence,
not authorization.

Before any fresh experiment read `PROJECT_STATUS.md`, `docs/NEXT.md` (closure
receipt and admission rule), `docs/factory/`, and `docs/parked/`. New
implementation work needs the owner to open a fresh question and a scoped
GitHub Issue. Each task must serve one of: prepare data, post-train a
candidate, eval against a frozen baseline, package a specialist artifact, or
report score delta, regressions, cost, latency, RAM, tok/s and a ship/reject
decision.

Parked unless a reactivated factory run needs them: browser/WebGPU polish,
Astro migration (approval-gated dependency change), ANE/CoreML, VLM, Tier 5
research, broad Mac app polish, new PRD expansion. Research CLIs (`rome`,
`memit`, `sae`, `laser`, `gptq`, etc.) stay in-tree under `native-mac/Sources/TinyGPT/`,
dispatched only via `posttrainllm experimental <command>`; do not delete them.
Issue #136 keeps the public learning UI, experiment archive, recipe/path
surfaces and CLI discovery active until the closure receipt is live.

## Not in scope for the fleet tooling

Sandbox project: no SaaS Maker product record, deployment, or analytics wiring
unless explicitly requested.

## Safety rules for heavy GPU / compile loops (macOS host)

Flash Attention 2 work, the native Mac app, and big-preset benchmark sweeps
can stress WindowServer (workload runaway, not hardware failure).

- Ask the user before long benchmarks, training, or install/build loops: more
  than a few seconds of pinned CPU/GPU, more than one training step above the
  Small preset, or any sweep repeating kernel dispatches in a tight loop.
- Single-shot heavy verification is fine; stop after it, don't loop.
- Kill background processes you spawned (dev workers, headed Playwright,
  Emscripten jobs) before ending a task.
- Flag before: iterated Flash Attention 2 benches, MLX/Metal runs from the
  native app, `pip install` of PyTorch/JAX/CUDA-adjacent packages, parallel
  compiles (`emcc -j`, `cmake --parallel`, `cargo build`).
- If the host degrades, check `ps -arcwwwxo pid,pcpu,pmem,comm | head -30` and
  kill the runaway process.
