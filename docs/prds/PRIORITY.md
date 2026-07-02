# PRD Priority Triage

Last updated: 2026-07-02

This file is the working priority map for every PRD currently on disk.

Active work still starts from:

1. `PROJECT_STATUS.md`
2. `docs/NEXT.md`
3. `docs/factory/`

Use this file only when a factory task needs a PRD-level acceptance checklist.

## Current Factory Gaps

These are the real gaps before building the next candidate:

1. **Target lock** — SQL is selected for the first factory POC. The expanded
   Qwen3-0.6B live run improved from 0.160 to 0.860 on 50 non-overlapping
   heldout rows and was correctly marked `retry-data`; the next gate is
   preference tuning or a public benchmark slice.
2. **Canonical run command/readout** — `FactoryRun` and
   `FactoryRunFolder` define the schema/readout and `tinygpt factory-run`
   renders/validates a complete run folder. The next missing piece is wiring
   real eval/train commands to emit those files automatically.
3. **Live baseline eval** — done for expanded SQL POC on Qwen3-0.6B.
4. **Dataset manifest** — expanded manifest exists with 108 train, 50 heldout,
   108 preference rows across five SQLite domains.
5. **First SFT candidate** — done for expanded SQL POC; next candidate should
   use DPO/SimPO on SQL-only and failure-derived preference pairs.
6. **Before/after report** — score delta, regressions, cost, latency, RAM,
   tok/s, artifact, and decision.
7. **Specialist package** — only if the decision is `ship`.

## Low-Compute Evidence

Verified on 2026-07-02 without model training, GPU sweeps, sudo, or network
installs:

Canonical rerun command:

```bash
bash evals/low-compute-prd-sweep.sh
```

The sweep may populate `/tmp/gpt2-tok` from Hugging Face for the C4 tokenizer
fixture. Set `TINYGPT_FETCH_TOKENIZER_FIXTURE=0` to skip that fetch in offline
environments.

| Area | Evidence |
|---|---|
| Run artifact schema | `FactoryRun` typed schema added in `native-mac/Sources/TinyGPTIO/FactoryRun.swift`; direct typecheck passes with `swiftc -typecheck`. |
| Eval gates / protocol | `evals/eval-gate-smoke.sh` passes, including pass/fail exits, repeated-pass uncertainty, protocol env, and baseline restamp. |
| Onboarding / run planning | `evals/quickstart-smoke.sh` passes for chat/tool-call fixture planning and missing-file failure. |
| Trace-to-data loop | `evals/traces-to-data-smoke.sh` passes for tool-echo filtering, exact dedupe, MinHash thresholding, dry-run, and deferred judge rejection. |
| Factory run folder | `factory-run-folder-smoke.sh` passes for canonical run-folder write/read/validate/report generation. |
| Router / deferred tools / escalation | `router-bakeoff-smoke.sh`, `b26-deferred-parity-smoke.sh`, and `escalate-smoke.sh` pass. |
| Batched eval runtime | `evals/b34-throughput-smoke.sh` passes against a local OpenAI-compatible mock, proving bounded-concurrent request submission and speedup reporting without a model server. |
| Pure Swift helper logic | `evals/swift-pure-model-smoke.sh` passes for B28 composite rewards, B11 WSD schedule math, B12 spike recovery, B15 layer-wise LR factors, and B18 depth-derived hyperparameters without building the MLX package graph. |
| Data quality / mix / compression | `quality-filter-smoke.sh`, `automix-smoke.sh`, `compress-smoke.sh`, and `scaledown-smoke.sh` pass. |
| Repro / interp / packages | `determinism-smoke.sh`, `interp-replay-smoke.sh`, and `project-validate-smoke.sh` pass. |
| Packaging/export | `export-mlx-smoke.sh` passes for committed `.tinygpt` fixture export and synthetic adapter export; Python `mlx` loader execution skipped when `mlx` is unavailable. |
| Specialist eval fixtures | `eval-sql-smoke.sh`, `milu-smoke.sh`, `review-smoke.sh`, and `reasoning-classifier-smoke.sh` pass. |
| SQL factory POC | `sql-poc-smoke.sh` and `sql-poc-expanded-smoke.sh` pass, including row-level SQL failure traces and generated preference pairs. |
| Tokenizer/router path | `extractor-bpe-smoke.sh` passes with the temporary GPT-2 tokenizer fixture prepared by `low-compute-prd-sweep.sh`. |
| Measurement harness math | `bench_energy.py --self-test` and `bench_decode_thermal.py --self-test` pass without sudo or a model server. |

Package-level Swift builds that touch MLX need the full Xcode beta developer
dir because global `xcode-select` points at Command Line Tools, which do not
include `metal`. Use:

```bash
DEVELOPER_DIR=/Applications/Xcode-27.0.0-Beta.app/Contents/Developer \
  swift build --build-system native --product tinygpt
```

Remaining gates that are not part of the low-compute sweep:

- `B34` now has no-model bounded-concurrency smoke coverage. It still needs
  real tinygpt-vs-mlx-server/oMLX qualification before claiming the PRD's
  `>=3x` live eval-runtime gate.
- `C10`/`B6` now have typed run artifacts and a render/validate command. The UI
  should still wait until real train/eval commands emit `runs/<id>/`
  automatically during a live factory run.
- `A1` acceptance is intentionally excluded from low-compute checks; it requires
  a GPU Mac, BFCL checkout, and an existing adapter.

## P0 — Build Next

These directly support the first canonical factory run.

| PRD | Priority | Use now for |
|---|---|---|
| [A1 first-specialist-tool-caller](A1-first-specialist-tool-caller.md) | P0 | Template for the first target's train/eval/package loop. Update mentally from "BFCL tool-caller" to "selected factory target". |
| [B33 laptop-finetune-onboarding](B33-laptop-finetune-onboarding.md) | P0 | Canonical CLI orchestration. Recast as `quickstart/factory-run` emitting the run schema, not just onboarding. |
| [B32 eval-ci-gate](B32-eval-ci-gate.md) | P0 | Baseline/candidate gate shape and failure exit semantics. |
| [B23 agent-eval-protocol](B23-agent-eval-protocol.md) | P0 | Repeated passes, fixed budgets, uncertainty, and resource accounting. |
| [B31 gallery-and-project-pins](B31-gallery-and-project-pins.md) | P0 | Project pins, package validation, and artifact identity. Mostly shipped; use the remaining pieces only if packaging blocks the run. |
| [B10 quality-classifier](B10-quality-classifier.md) | P0 | Data filtering sidecar for target data if quality/noise is a problem. Already has a useful V1. |
| [B21 micro-automixer](B21-micro-automixer.md) | P0 | Data-mix search before training if the target has multiple data sources. Use dry-run/lightweight mode first. |

## P1 — Immediately After First Candidate

These are useful once the first SFT candidate exists or if the first run
reveals the matching failure mode.

| PRD | Priority | Trigger |
|---|---|---|
| [B28 composite-reward-framework](B28-composite-reward-framework.md) | P1 | Candidate has verifiable failures and needs DPO/RLVR/ReST-style reward integration. |
| [self-improving-agents](self-improving-agents.md) | P1 | First candidate produces traces and the reward is stable enough for a second round. |
| [continual-learning-loop](continual-learning-loop.md) | P1 | Factory needs repeated correction -> data -> train cycles. |
| [B2-B7 router-family](B2-B7-router-family.md) | P1 | Specialist wins narrowly but damages breadth; route instead of forcing one general model. |
| [B26 deferred-tools](B26-deferred-tools.md) | P1 | Tool catalog size becomes a real eval/runtime bottleneck. |
| [B5 cloud-escalate-training](B5-cloud-escalate-training.md) | P1 | Candidate must learn when local model should defer/escalate. |
| [B34 batched-eval-runtime](B34-batched-eval-runtime.md) | P1 | Eval runtime blocks iteration speed. |
| [C5 decode-jitter-thermal](C5-decode-jitter-thermal.md) | P1 | Candidate is good enough that sustained decode/thermal behavior matters. |
| [B9 energy-per-token](B9-energy-per-token.md) | P1 | Candidate is good enough for power/energy comparison. |
| [qlora-large-model-finetune](qlora-large-model-finetune.md) | P1 | SFT on bf16/LoRA plateaus and memory blocks larger-base experiments. |
| [C10 train-run-dashboard](C10-train-run-dashboard.md) | P1 | CLI run schema exists and needs a visual run reader. |
| [B6 mac-app-demo](B6-mac-app-demo.md) | P1 | CLI factory loop proves improvement; then build the minimal Factory Run Center. |

## P2 — Later Factory Support

Useful, but not needed before the first measured factory proof.

| PRD | Priority | Why later |
|---|---|---|
| [B1 second-specialist-shell-or-sql](B1-second-specialist-shell-or-sql.md) | P2 | Only after the first target proves the loop. |
| [B8 multilingual-specialist](B8-multilingual-specialist.md) | P2 | Needs target-specific data/eval and should not compete with first proof. |
| [B25 scaledown-specialist](B25-scaledown-specialist.md) | P2 | Good specialist candidate, but only if selected as the target. |
| [E6 eval-scaledown](E6-eval-scaledown.md) | P2 | Relevant only for B25/context-compression target. |
| [B11 wsd-schedule](B11-wsd-schedule.md) | P2 | Training-quality polish unless first candidate shows LR schedule issues. |
| [B12 loss-spike-recovery](B12-loss-spike-recovery.md) | P2 | Use when real training has instability, not before. |
| [B15 layerwise-lr-decay-sft](B15-layerwise-lr-decay-sft.md) | P2 | Tune after baseline SFT. |
| [B18 nanochat-depth-knob](B18-nanochat-depth-knob.md) | P2 | Useful for from-scratch/pretrain ergonomics, not the current adapter loop. |
| [C4 tool-extractor-bpe](C4-tool-extractor-bpe.md) | P2 | Relevant if mini-router/tool extraction becomes the selected path. |
| [C9 determinism-harness](C9-determinism-harness.md) | P2 | Keep reproducibility constraints, but bit-exact replay is not achievable on current MLX/Metal. |
| [B14 speculative-decoding](B14-speculative-decoding.md) | P2 | Runtime speed after quality is proven. |
| [B16 m5-na-prefill-bench](B16-m5-na-prefill-bench.md) | P2 | Hardware measurement after a candidate matters. |
| [B13 interp-on-checkpoints](B13-interp-on-checkpoints.md) | P2 | Debugging/learning lane, not factory proof. |
| [B17 saelens-interop](B17-saelens-interop.md) | P2 | Useful for analysis export; not active. |
| [B19 group-sae](B19-group-sae.md) | P2 | Interpretability cost reduction; not active. |
| [capability-retention](capability-retention.md) | P2 | Important evaluation concept, but implement through the selected target's regression suite first. |
| [factory-planner-v7-tools-in-prompt](factory-planner-v7-tools-in-prompt.md) | P2 | Use only if selected target is planner/tool-schema prompt work. |
| [pace-task-loop-v1](pace-task-loop-v1.md) | P2 | Pace app integration is separate from TinyGPT factory proof. |

## P3 — Parked Research

Keep these for learning/future expansion. Do not open during the factory proof.

| PRD | Priority | Park reason |
|---|---|---|
| [5.1 reasoning-on-22M](5.1-reasoning-on-22M.md) | P3 | Tier 5 research; not current factory proof. |
| [5.2 testtime-compute-scaling](5.2-testtime-compute-scaling.md) | P3 | Tier 5 research. |
| [5.3 vision-language-toy](5.3-vision-language-toy.md) | P3 | VLM/toy research. |
| [5.4 diffusion-lm-micro](5.4-diffusion-lm-micro.md) | P3 | Diffusion LM research. |
| [5.6 tts-toy](5.6-tts-toy.md) | P3 | Audio/TTS research. |
| [5.7 explainer-video-model](5.7-explainer-video-model.md) | P3 | Far-future multimodal/product research. |
| [factory-vision-m4-impl-plan](factory-vision-m4-impl-plan.md) | P3 | VLM porting parked. |
| [factory-vision-specialist](factory-vision-specialist.md) | P3 | VLM specialist parked. |
| [vlm-ab-uivenus-vs-qwen3vl](vlm-ab-uivenus-vs-qwen3vl.md) | P3 | VLM decision parked. |
| [game-rl-environment-poc](game-rl-environment-poc.md) | P3 | RL environment research. |
| [local-model-arena-selfplay](local-model-arena-selfplay.md) | P3 | Self-play research. |
| [gepa-prompt-evolution](gepa-prompt-evolution.md) | P3 | Prompt-evolution research; not factory proof. |
| [B35 local-agent-vertical-poc](B35-local-agent-vertical-poc.md) | P3 | Coding-agent product wedge is not the current TinyGPT center. |
| [GPU-RESEARCH-BACKLOG](GPU-RESEARCH-BACKLOG.md) | P3 | Hardware-heavy backlog; use only after target proof. |

## Archive Candidates

These should not be selected for new work. Keep the files for history unless a
future cleanup physically moves them into an archive directory and updates links.

| PRD | Archive reason |
|---|---|
| [C3 dora-ondisk-format](C3-dora-ondisk-format.md) | Shipped/closed. |
| [quantized-inference-swift](quantized-inference-swift.md) | Shipped/closed. |
| [multi-turn-agentic-eval](multi-turn-agentic-eval.md) | Shipped as eval infrastructure. |
| [pace-planner-v11-training-data](pace-planner-v11-training-data.md) | Data PRD shipped; later gate chose not to ship that planner. |
| [pace-planner-v11-ship-gate](pace-planner-v11-ship-gate.md) | Decision/gate doc honored; no build work. |
| [specialist-pace-planner](specialist-pace-planner.md) | Track closed; pivoted to stock 4B/general planner lock. |
| [factory-completeness-tracker](factory-completeness-tracker.md) | Tracking document; primitives mostly hold up in code. |
| [factory-vision-m4-architecture-decision](factory-vision-m4-architecture-decision.md) | Decision made; downstream VLM work parked. |
| [tinygpt-product-thesis](tinygpt-product-thesis.md) | Historical positioning; superseded by factory-first cleanup. |
| [macos26-int8-ane-handoff-port](macos26-int8-ane-handoff-port.md) | Negative result; parked/closed. |
| [5.5 sparse-moe-kernels](5.5-sparse-moe-kernels.md) | Blocked upstream; design note only. |

## Archive Policy

Do not move files during active build work. Soft-archive first by listing them
above.

Physically move a PRD only when:

- no active doc links depend on its current path, or links are updated in the
  same change;
- it is shipped, superseded, negative-result closed, or upstream-blocked;
- `docs/prds/README.md` and this file stay in sync.
