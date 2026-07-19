# posttrainllm — PROJECT STATUS

Last updated: 2026-07-19

## Why / What

posttrainllm is a **Mac-local specialist factory**.

The active product loop is:

```text
target -> data -> post-training -> eval -> package -> report
```

The browser playground, Python reference, WASM/WebGPU training path, native
Swift/MLX runtime, eval harnesses, and research docs are all assets for that
factory. They are not all active product centers.

For Pace, posttrainllm is a development-time factory and eval lab: it can prepare
planner data, adapters, specialist packages, eval fixtures, and reports. Pace
production must not depend on `posttrainllm serve`, localhost, or this repo's dev
runtime.

Current proof points:

- First registered specialist package:
  `specialists/qwen3-4b-file-ops-distilled`.
- It improves file-ops hard gate from 58% to 100%, but regresses
  out-of-domain breadth from 59.6% to 42.3%.
- Therefore it is a routed specialist, not a general planner.
- Second registered specialist package:
  `specialists/qwen3-4b-rest-fused`.
- Its recorded teacher-free ReST run retains the 100% file-ops gate and raises
  the same breadth family from the stock 59.6% to 65%. It ships as a research
  specialist, not a Pace default; historical performance and raw trace logs
  were not preserved and are disclosed as missing evidence.

The full loop has executed end-to-end with both outcomes: the frozen
`qwen06-sql-hygiene-dpo-v1` run ended in a documented **retry-training**
decision, while `qwen3-4b-rest-fused` now has a canonical assembled run,
package, public weights, and narrow **ship** decision. The latter promotes
existing measured evidence; it does not pretend the missing historical
latency/RAM/tok-s and raw traces were recreated.

## Dependencies

| Surface | Location | Role |
|---|---|---|
| Native CLI | `native-mac/Sources/TinyGPT/` | Main factory surface: train, SFT, DPO, distill, eval, serve, trace, package |
| Native model/runtime libs | `native-mac/Sources/TinyGPTModel/`, `TinyGPTServe/`, `TinyGPTData/` | MLX/HF loading, PEFT, rewards, eval helpers, OpenAI-compatible serving |
| Eval scripts | `evals/`, `scripts/` | No-GPU smokes, BFCL/Pace helpers, benchmark/report scripts |
| Browser site | `browser/` | Public demo and readout surfaces; not the active factory control plane |
| WASM/WebGPU | `wasm/`, `webgpu/`, `browser/src/` | Completed learning/perf track; parked unless factory proof needs it |
| Python reference | `python_ref/` | Correctness/reference path for from-scratch pieces |
| Active roadmap | `docs/NEXT.md` | Current sequence only |
| Factory docs | `docs/factory/` | Run schema, eval protocol, packaging, reports |
| Technique registry | `docs/techniques/` | Method-vs-recipe cards, audit inventory, external teardowns, target-specific experiment backlog |
| Docs hub | `docs/README.md` | Golden path through state, attempts, reviewed products, roadmap, and learning |
| Attempt ledger | `docs/attempt-ledger.md` | Worked/failed/regressed/not-tried attempt history |
| External review ledger | `docs/external-products-reviewed.md` | Products, papers, startups, and techniques reviewed or stolen |
| Learning pipeline | `docs/learning-pipeline.md` | Owner learning sequence tied to active factory work |
| Parked lanes | `docs/parked/` | Explicitly paused work so it does not compete with factory proof |
| Detailed backlog | `docs/prds/`, `docs/PLAN.md` | Historical and deep task inventory; not the first navigation layer |

Important constraints:

- Do not run long GPU/model-training loops without explicit owner approval.
- Respect `~/.cache/posttrainllm/gpu.lock` before training.
- Do not touch secrets, cloud credentials, production configs, or Pace runtime
  wiring unless explicitly asked.
- Prefer no-GPU smokes and fixture checks before heavier validation.

## Timeline

| Date / phase | Status |
|---|---|
| 2026-07-19 Foundry evidence receipts | Shipped `automate-posttrainllm` (fleet-automation-closure Store): privacy-safe evidence contract + receipt pipeline for the Foundry control plane. `docs/factory/foundry-evidence.md` is the canonical per-surface contract; `scripts/foundry_receipt.py` emits sanitized receipts (git, registry, run folders, nightly markers, CI); `scripts/check_foundry_receipt.py` validates shape, provenance completeness, manual publication authority, and absence of private payloads; `evals/foundry-receipt-smoke.sh` + `tests/test_foundry_receipt.py` (11 tests) prove private datasets/prompts/checkpoints/outputs cannot enter receipts. Existing public artifacts' quality claims are correctly blocked because their `eval_report.json` lack explicit `source_revision` — surfaced as a blocked gap, not papered over. No new production dependency, no auto-publication, no deploy. |
| 2026-07-16 Fine-Tune Report Card OpenSpec | Drafted `add-fine-tune-report-card`: compile existing factory-run evidence into versioned JSON and a static public before/after report with explicit regressions, leakage/eval validity, performance, missing/historical values, and ship/retry/reject semantics. The draft performs no training, model loading, GPU eval, upload, implementation, or release. |
| 2026-07-13 ReST candidate promotion | Promoted public `qwen3-4b-rest-fused` weights into the second registered specialist package. Canonical metadata run passes the strict publish check with a narrow research-specialist ship decision: file-ops depth 100%, breadth 65% vs stock 59.6%. Added BFCL standalone/monorepo path resolution. Historical timing/RAM/tok-s and raw traces remain explicitly unavailable; no heavy rerun or Pace wiring was performed. |
| 2026-07-11 ref-anchored DPO retries (×2) | Executed two full GPU factory loops on the frozen qwen06-sql-hygiene target. **(1)** Ref-anchored DPO (50 steps, lr 5e-6) **fixed the SimPO collapse** — composed exec 0.860 → 0.900 (SimPO retry was 0.080), DPO-alone healthy 0.120, step-1 loss 0.6931 ≈ log 2. **(2)** Higher-pressure retry (beta 0.3, 200 steps, lr 1e-5) drove loss to 0.0073 and exec to 0.920, but clean-SQL stayed 0.000. **Definitive: composed rank-4 DPO cannot fix output-format hygiene at any tested pressure** (both keep a prose wrapper while execution only rises). Decision **retry-data**. Diagnosis correction: SFT targets are already 108/108 bare SELECT — the `Answer:` wrapper is the base Qwen3-0.6B prose prior, so the fix is generation-strength (stronger SFT or inference steering / output post-process), not a data rebuild. Execution is not the problem (0.860 → 0.920); only the wrapper is. Both runs assembled via `scripts/assemble_factory_run.py` (validate + publish-check pass); runs gitignored. |
| 2026-07-11 ground-up learning roadmap completed | Shipped: all 10 curriculum modules now have polished sessions (added `session-09-tensors`, `session-10-attention`, `session-11-evals-rewards` for the previously reference-only Modules 3/7/10), plus `docs/learn/coverage-map.md` mapping every shipped subsystem to a learning anchor. Guarded by `scripts/check_learning_roadmap.py` (`bash evals/learning-roadmap-smoke.sh`). |
| 2026-07-04 first full factory decision | Shipped: frozen `qwen06-sql-hygiene-dpo-v1` candidate trained (SimPO), evaluated composed against the reproduced frozen baseline, and decided **retry-training** (policy collapse: exec 0.860 → 0.080). Schema-valid run in `runs/2026-07-03-sql-hygiene-dpo-qwen06/`. Also landed: DoRA-aware `bake-lora`, routed-SQL perf harness, clean-SQL scorer. |
| 2026-07-03 canonical factory loop | Verified: `scripts/render_sql_factory_run.py` renders the canonical run folder (config, dataset, eval-baseline, eval-candidate, decision, artifact, train.log, report.md). Native CLI `posttrainllm factory-run render/validate` mirrors the same path. Run schema defined in `docs/factory/run-schema.md`. Actual training/eval remains operator-dependent (GPU + Xcode metal compiler required). |
| Original Phases 1-4 | Complete: Python reference, transformer, training loop, eval basics |
| Phase 5 | Complete: LoRA/adapter paths and PEFT bundle |
| Phase 6 | Complete: dataset manifests, HF integration, GitHub fetcher, synthesis |
| Phase 7 | Complete: browser systems, WASM SIMD, OPFS, gallery |
| Phase 8 | Complete: WebGPU training path and gated fast paths |
| Phase 9 | Complete: browser benchmark/eval and numerics-gate framework |
| Phase 10 | Complete: public browser readiness and docs consolidation |
| 2026-05-31 Mac runtime wave | Shipped: Swift/MLX CLI, serve/agent, Ollama/Continue-compatible surfaces |
| 2026-06-06 factory reframe | Active north star became Mac specialist factory |
| 2026-06-08 eval methodology gate | Shipped: baseline re-stamping, uncertainty, fake Pace/eval methods |
| 2026-06-19 planner lock | Shipped: stock Qwen3-4B-Instruct-2507 bf16 remains general Pace planner |
| 2026-06-20 factory/eval PRD wave | Shipped many scaffold/eval slices; most remaining work needs real training/evals |
| 2026-07-02 cleanup | Active navigation reset around factory loop; non-core lanes parked |

## Products

| Product / artifact | State |
|---|---|
| Factory CLI | Main product surface. It has commands for data prep, post-training, eval, traces, packaging, reporting, and canonical factory-run render/validate/publish checks. |
| Factory run artifacts | Target shape defined in `docs/factory/run-schema.md`; `runs/` is local-output and gitignored. |
| Specialist packages | Two public-weight packages are registered: routed file-ops distillation and the breadth-recovering ReST research specialist. |
| Public artifact registry | First-class release list lives in `docs/factory/public-artifacts.md`; website surface is `/artifacts`; every artifact carries blockers beside evidence. |
| Eval gates | Strong fixture/no-GPU layer exists. Live GPU/full-suite gates remain operator-dependent. |
| Browser playground | Live demo and proof of from-scratch/browser track. Parked for active factory work. |
| PostTrainLLM app | GUI shell over the CLI. Now covers the factory-loop experiment commands: Factory tab runs pretrain/finetune/**DPO**/**distill**; new **Runs** tab runs **factory-run** (validate/publish-check), **eval-gate**, **eval-compare**, **eval-sql**, and **generate** — all via a shared `CLICommandRunner` shell-out. Data-prep, quantization/export, and most interpretability commands remain CLI-only by design (batch/one-off, not interactive). |
| Pace outputs | Dev-time artifacts only: data, grammar/eval assets, adapter/model package metadata, reports. |

## Features (shipped)

Factory primitives:

- Training and post-training: `train`, `finetune`, `sft`, `dpo`, `distill`,
  `es`, PEFT variants, LoRA/DoRA/QLoRA scaffolding, sequence packing,
  gradient checkpointing, NEFTune, z-loss, WSD, LLRD, spike recovery.
- Data: dataset registry/download, HF inspect/load, GitHub fetcher,
  Magpie/synthesis, tokenizer training, extractor data, trace conversion,
  correction-to-data tools, quality filtering, dedupe.
- Evals: `eval-gate`, `eval-compare`, BFCL, tau-bench, HumanEval, lm-eval,
  SQL, router, MILU/Indic, MTEB, review, ScaleDown V1, escalation evals.
- Runtime/serving: OpenAI-compatible `serve`, Ollama-compatible endpoints,
  agent loop, constrained JSON/FSM generation, trajectory recording, prompt
  cache, cloud escalation path.
- Packaging/runtime: export to MLX, safetensors/CoreML helpers, quantized
  inference paths, GGUF/AWQ/GPTQ readers, HQQ/GPTQ tools, merge/bake-lora.
- Reporting/readouts: eval result JSON, browser eval leaderboard, SAE
  timeline, benchmark scripts, specialist package model-card pattern.
- Foundry evidence receipts: `scripts/foundry_receipt.py` emits sanitized
  receipts (git, registry, run folders, nightly markers, CI) and
  `scripts/check_foundry_receipt.py` validates shape, provenance
  completeness, manual publication authority, and absence of private
  payloads. Contract in `docs/factory/foundry-evidence.md`; covered by
  `evals/foundry-receipt-smoke.sh` and `tests/test_foundry_receipt.py`.

Completed/parked learning tracks:

- Browser GPT training from scratch with WASM/WebGPU.
- WebGPU fast paths and numerics gates.
- ANE/CoreML experiments with documented constraints and negative results.
- VLM and Tier 5 research planning/scaffolds.
- Interpretability tools: SAE, ROME, MEMIT, tuned/logit lens, activation
  patching.

## Todo / Planned / Deferred / Blocked

### Active: factory proof

See `docs/NEXT.md` for the current sequence.

Near-term work should answer one of these questions:

1. Can we prepare the right data?
2. Can we post-train a candidate?
3. Can we evaluate it against a frozen baseline?
4. Can we package it as a reusable specialist?
5. Can we report cost, latency, RAM, score delta, regressions, and a
   ship/reject decision?

If a task does not answer one of those, park it.

### Active gaps

- The Fine-Tune Report Card is specified in `openspec/changes/add-fine-tune-report-card` as the public, machine-readable proof layer over canonical factory-run evidence. It should be implemented and dogfooded across successful, routed, retry, reject, and historical cases without triggering new GPU work.
- No single canonical factory command/readout yet. Existing commands are real,
  but orchestration is still spread across scripts and docs. Partially closed
  2026-07-11: `scripts/assemble_factory_run.py` is the generic report-artifact
  bridge (fragments → canonical folder with derived provenance/report, passing
  publish-check and the typed Swift schema; smoke
  `evals/factory-run-assemble-smoke.sh`). Remaining: live Swift train/eval
  commands emitting those fragments, which needs a real GPU run to verify.
- Public artifacts are now tracked, but only one model package has committed
  package metadata and the SQL routed candidate is still report-only until a
  public execution SQL gate is added.
- Run artifacts are not standardized in code yet. The target schema is in
  `docs/factory/run-schema.md`.
- The next specialist target is not frozen in this cleanup. `docs/NEXT.md`
  keeps the sequence target-first.
- Live GPU/full-model evals remain operator-dependent and must respect the
  repo's heavy-work rules.
- QLoRA real packed-base autograd remains blocked in MLX-Swift; current path is
  pedagogical/fake-quant for training, with packed inference support.
- Deferred-tools, broader router, RLVR/ReST loops, and DPO/RFT integration need
  measured candidate runs before more surface area is useful.

### Parked

Parked lanes are documented under `docs/parked/`:

- Browser/WebGPU polish and launch work.
- ANE/CoreML performance research.
- VLM work.
- Tier 5 exploratory research.
- Broad app/UI polish beyond a minimal Factory Run Center.

### Detailed backlog

`docs/prds/STATUS.md` remains the detailed PRD audit. It is useful for
recovering exact task history, but it contains layered/stale sections. Treat the
top summary and current source files as stronger than old per-PRD frontmatter.

`docs/PLAN.md` remains the long historical ledger. It is not the active queue.
