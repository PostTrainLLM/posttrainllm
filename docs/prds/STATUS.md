# PRD status — code-verified audit (2026-06-20)

Canonical, **code-cross-checked** status of every active PRD in `docs/prds/`.
Each verdict was verified against `native-mac/Sources/`, `scripts/`, `evals/`,
and `browser/src/` — **not** the PRD's own `status:` frontmatter, which is
unreliable (many were stale; several said `not-started` while the feature had
partly shipped). When a PRD's frontmatter disagrees with this table, **this
table wins**.

> Why this exists: a 2026-06-20 audit found frontmatter understated progress
> and `docs/PLAN.md`'s `✅` markers overstated it (it marks features "shipped"
> that miss their PRD's acceptance criteria). This doc is the reconciled truth.

## Summary (after the 2026-06-20 implementation session)

| Verdict | Count | Meaning |
|---|---|---|
| ✅ Done | 10 | all acceptance criteria met + verified |
| 🟡 Partial | 22 | core/scaffolding ships, named gaps remain |
| ⬜ Not-started | 22 | no deliverables found in code |
| 📄 Non-task | 6 | decision / positioning / tracking / upstream-blocked doc |
| **Total** | **60** | |

### Finished in the 2026-06-20 implementation session (7 PRDs)

All verified by `swift test` / smoke scripts. Build note: Xcode-27's default
build system has a broken incremental relink; use `swift build --build-system
native --product tinygpt`.

| PRD | What shipped | Verification |
|---|---|---|
| **B15** llrd | `--llrd γ` on sft/dpo/finetune via `scaleLayerwiseLR` | LLRDTests (2) |
| **B11** wsd | `--decay-shape {1-sqrt,cosine,linear}` | TrainSchedHelpersTests |
| **B18** depth | `--depth` derives lr/batch/steps + `--regime`; DepthDerivation module + training_guide table | DepthDerivationTests (6) |
| **B10** quality | `--score` {doc_id,score} sidecar mode | quality-filter-smoke.sh (science 0.77 > spam 0.02) |
| **B12** spike | `--auto-rollback off\|warn\|on` adaptive LR-cut controller | SpikeRecoveryTests (4) |
| **C9** determinism | `evals/determinism-smoke.sh` harness + corrected doc | smoke (step-0 exact, ~2.7e-5 same-seed) |
| **B17** saelens | exporter writes README + docs section | builds; py round-trip needs `sae_lens` |

C9 finding: MLX/Metal training is reproducible to ~1e-5 but **not bit-exact**
past step 0 (nondeterministic GPU reductions) — full step-N replay isn't
achievable on this backend. B17 remains partial (sparsity = analysis-time).

**~44 PRDs still carry real remaining work** (22 partial + 22 not-started),
most needing GPU training runs, special hardware, or network deps to finish.

---

## ✅ Done (4) — acceptance met; candidates for removal

- **C3 dora-ondisk-format** — DoRA magnitudes persist + reload via `LoraIO.swift` (v2 back-compat); wired through `sft`. Only gap: no dedicated roundtrip test.
- **quantized-inference-swift** — both phases ship: `serve --quantize int4|int8` + native packed `QuantizedLinear` load (`HFModel.swift`), covered by a logit-cosine parity test.
- **multi-turn-agentic-eval** — `scripts/bfcl_multiturn_eval.py` real stateful executor; frontier backends (codex/deepseek); single→multi-turn cliff documented. (frontmatter wrongly says `proposed`.)
- **pace-planner-v11-training-data** — seed→amplify→judge pipeline built + run (709-row corpus trained); unhappy-class eval suites exist. Track later closed at the gate, but the data PRD itself shipped.

## 🟡 Partial (26) — shipped core, real gaps

**Training quality / optimizer**
- **B10 quality-classifier** — bag-of-ngram scorer + `quality-filter` ship; missing `--score` sidecar mode, 6-bucket softmax/macro-F1, smoke. (frontmatter STALE)
- **B11 wsd-schedule** — WSD curve + `--lr-schedule wsd` ship; missing `--decay-shape` choice (locked to 1-sqrt) and the "becomes default" flip. (STALE)
- **B12 loss-spike-recovery** — observe-only spike detector ships; the **auto-rollback controller** (the PRD's actual goal) is unbuilt. (STALE)
- **B16 m5-na-prefill-bench** — mlx-swift bump landed; the before/after prefill measurement + decision note were never recorded. (STALE)
- **B18 nanochat-depth-knob** — `--depth N` derives architecture dims; missing schedule-HP derivation (lr/batch/steps) + regime flag. (STALE)
- **C4 tool-extractor-bpe** — BPE encode path ships via manual `--tokenizer`; missing auto-detect, offset/char-span alignment, smoke. (STALE)

**Interpretability**
- **B13 interp-on-checkpoints** — SAE-only timeline (`sae --checkpoint-dir`) feeds the viewer; the unified `interp-replay` orchestrator + `--interp-every` hook are missing. (STALE)
- **B17 saelens-interop** — `sae-to-saelens` exporter ships; missing `sparsity.safetensors`, README schema, Python load-roundtrip test, docs. (STALE)
- **B19 group-sae** — group training + round-trip ship but with a **design deviation** (axis-0 union vs spec'd d_model-concat); missing range-parser, sae-explore attribution, tests. (STALE)

**Inference**
- **B14 speculative-decoding** — offline `sample --draft` ships with accept-rate report; **serve integration + T=0 numerics gate + throughput eval are absent** (serve was the primary target). (STALE)

**Agent protocol / eval discipline**
- **B23 agent-eval-protocol** — repeated-pass uncertainty + budget metadata ship at the gate/compare layer; per-harness `--passes K` loops + new task rows pending.
- **B26 deferred-tools** — full `--tool-mode` scaffolding + tests + parity runner ship; BFCL parity **ship gate** unverified on a real specialist (stays off by default).
- **B28 composite-reward-framework** — `CompositeReward` type + tests ship; **no training-loop integration** (`--reward-fn` on dpo/es, GRPO consumer, viewer curves, recipe).
- **B31 gallery-and-project-pins** — Swift manifest mirrors + first Mac specialist registered; browser schema discriminator + pin-aware `pull`/`validate` + B6 picker unshipped.
- **B32 eval-ci-gate** — gate logic + CLI + GitHub Action + exit-code smoke ship; live whole-suite run on a Mac runner pending.
- **B33 laptop-finetune-onboarding** — `quickstart` wizard + resolver + smoke + docs ship; missing eval-vs-baseline delta step + raw-text training path. (frontmatter STALE — says not-started)
- **C10 train-run-dashboard** — drag-drop live-charts viewer ships + wired; missing grad-norm chart (not even logged), live/OPFS mode, eval-star overlay. (STALE)

**RL / trace-improvement loop**
- **self-improving-agents** — every ingredient ships (rollout harness, verifiable reward, `--dump-rollouts`, SFT step) + one teacher-free round ran; the ≥2-round monotonic loop + auto-curriculum were never executed. (STALE)
- **qlora-large-model-finetune** — `--qlora` flag + packed inference load ship, but training runs on a **dequantized** base — the packed-base `QLoraLinear` (the actual memory unlock) is stubbed "pending". (STALE)

**Factory / Pace / vision**
- **factory-planner-v7-tools-in-prompt** — tools-in-prompt serve + verb-enum grammar ship; per-verb arg schemas not enforced; xLAM-scale SFT + external evals pending.
- **factory-vision-m4-impl-plan** — only M4.1 config/tensor inspection lands; weight load throws notImplemented; mRoPE/deepstack/token-replacement/parity unbuilt. (STALE)
- **factory-vision-specialist** — M1–M3 ship with CLIP parity (0.999995); M4 functional port + M5–M10 (train/data/serve/eval/handoff) open.
- **specialist-pace-planner** — recipe primitives all real and exercised, but the small-student goal was **not** met; track explicitly **closed** (pivoted to 4B+ / qlora PRD). (STALE)
- **macos26-int8-ane-handoff-port** — both phases shipped + pass numerics gate, but they **disprove the premise**: decode stayed ~22 tok/s (goal was ~30); negative result, effectively closed. (STALE)
- **vlm-ab-uivenus-vs-qwen3vl** — A/B eval runner built + both models on disk, but the 30-fixture set + the actual port-target **decision** (the PRD's whole point) were never finalized. (STALE)

**Long-horizon**
- **pace-task-loop-v1** — T0 latency bench + fixtures ship; T1 `PaceTaskLoop` Swift loop + T2 live run unbuilt (Pace app is a separate repo).

## ⬜ Not-started (24) — no deliverables in code

- **Specialists**: A1 first-specialist-tool-caller (all Tier-E/trainer deps exist; the A1 adapter+recipe+leaderboard row never produced), B1 second-specialist (blocked-by A1), B5 cloud-escalate-training (runtime path exists; *trained* defer never built), B6 mac-app-demo Factory tab (blocked-by A1), B8 multilingual-specialist (blocked-by A7), B25 scaledown-specialist.
- **Agent protocol**: B2-B7 router-family (building blocks exist; bundle deliverables don't), B34 batched-eval-runtime, B35 local-agent-vertical-poc.
- **Training/optimizer**: B15 layerwise-lr-decay-sft (only pretrain prior-art; no SFT/dpo `--llrd`), B21 micro-automixer.
- **Harness/measurement**: B9 energy-per-token, C5 decode-jitter-thermal, C9 determinism-harness (seed-determinism shipped; bit-exact step-N **replay** harness not built), E6 eval-scaledown.
- **RL environments**: game-rl-environment-poc (skeleton only), gepa-prompt-evolution (parked behind v11), local-model-arena-selfplay (phase-2).
- **Tier 5 frontier**: 5.1 reasoning-on-22M, 5.2 testtime-compute-scaling, 5.3 vision-language-toy, 5.4 diffusion-lm-micro, 5.6 tts-toy, 5.7 explainer-video-model.

## 📄 Non-task (6) — not buildable "to-do" work

- **5.5 sparse-moe-kernels** — design doc; blocked on MLX `scatter_add` upstream (its own framing). Dense MoE is the shipped fallback.
- **capability-retention** — backlog/positioning ("future work; captured for later").
- **factory-completeness-tracker** — tracking matrix; its primitive claims hold up in code.
- **factory-vision-m4-architecture-decision** — decision made (Option A, UI-Venus base) and acted on.
- **pace-planner-v11-ship-gate** — gate-criteria doc; honored (v11 run once, failed all dims, 30B kept).
- **tinygpt-product-thesis** — positioning/strategy doc.
