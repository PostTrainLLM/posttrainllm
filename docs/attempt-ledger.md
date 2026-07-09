# Attempt Ledger

This ledger records meaningful posttrainllm attempts as worked, failed, regressed,
inconclusive, or not yet tried. It is the human-readable companion to run
folders and factory reports.

The point is not to look successful. The point is to preserve the experimental
state so the next recipe is better than the last one.

Structured index: [`docs/attempts.json`](attempts.json). Check sync with:

```bash
bash evals/attempt-ledger-smoke.sh
```

## Evidence Standard

`docs/attempts.json` is the machine-readable source for this ledger. Every
attempt has evidence sources and a failure-reason confidence label.

| Confidence | Meaning |
|---|---|
| `exact` | Direct run report, decision file, artifact metadata, or current source doc contains the stated result and reason. |
| `inferred` | Reason is reconstructed from prose or artifact notes, but no canonical run folder proves the full claim. |
| `missing-evidence` | Attempt is known, but available docs do not preserve enough evidence to state a real reason. |
| `not-applicable` | No failure reason is expected for this status. |

Do not upgrade an old attempt from `inferred` to `exact` without linking the
run report, decision file, artifact metadata, or source doc that proves it.

## Status Vocabulary

| Status | Meaning |
|---|---|
| `worked` | Passed the intended gate for that attempt |
| `worked-with-caveat` | Improved the target but exposed a blocker/regression |
| `failed` | Did not pass the intended gate |
| `regressed` | Improved one slice but damaged a required gate |
| `inconclusive` | Evidence too weak or eval not credible enough |
| `not-tried` | Planned/scaffolded but not executed as a model run |

## SQL Specialist Attempts

SQL is the current factory POC and the best-documented attempt family.

### Toy SQL SFT

- Recipe: Qwen3-0.6B + rank-4 DoRA/LoRA on 12 rows.
- Evidence: execution `0.167 -> 0.833` on 6-row fixture.
- Status: `worked-with-caveat`.
- Failure reason: Train/eval overlap made the apparent improvement non-shippable.
- Lesson: The SFT loop mechanics work, but eval splits must be frozen before claiming quality.
- Next action: Use only as a loop sanity check; rely on heldout SQL evals for real claims.

### Expanded synthetic SQL SFT

- Recipe: 108 train rows, 50 heldout rows, five SQLite domains.
- Evidence: execution `0.160 -> 0.860`, exact `0.140 -> 0.840`.
- Status: `worked`.
- Lesson: Current synthetic SQL adapter; joins remain weaker than single-table rows.
- Next action: Keep as the synthetic incumbent until a candidate beats it on the same heldout gate.

### Public b-mc2 v1

- Recipe: 512 public-style SFT rows, rank 8, 300 steps.
- Evidence: exact `0.344` vs T5-small `0.484`.
- Status: `failed`.
- Failure reason: The public-style dataset was too small to beat the T5-small baseline.
- Lesson: Public benchmark adaptation needs more coverage before tuning knobs matter.
- Next action: Scale public-style rows and re-evaluate against the same exact gate.

### Public b-mc2 v2

- Recipe: 2048 rows, rank 16, 1200 steps.
- Evidence: exact `0.031`.
- Status: `failed`.
- Failure reason: Increasing rows, rank, and steps together made the recipe worse and confounded the cause.
- Lesson: Do not change data volume, rank, and training length in one uncontrolled jump.
- Next action: Use smaller controlled deltas with fixed eval and comparable training settings.

### Public b-mc2 v3

- Recipe: 2048 rows, rank 8, lower LR, 600 steps.
- Evidence: exact `0.422`.
- Status: `failed`.
- Failure reason: Lower LR and fewer steps recovered quality but still missed the public baseline.
- Lesson: The public recipe was directionally better, but not enough for a win.
- Next action: Try targeted data weighting instead of only global hyperparameter changes.

### Public b-mc2 v4

- Recipe: Join/group weighted public rows, rank 8, 700 steps.
- Evidence: exact `0.531` vs T5-small `0.484`.
- Status: `worked-with-caveat`.
- Failure reason: The public win did not preserve synthetic SQL execution behavior.
- Lesson: A narrow public exact-match win can still damage the incumbent specialist behavior.
- Next action: Route or compose specialists instead of forcing one adapter to satisfy both gates.

### Public v4 synthetic regression check

- Recipe: v4 scored on synthetic execution fixture.
- Evidence: synthetic execution `0.240` vs incumbent `0.860`.
- Status: `regressed`.
- Failure reason: Public-style training overfit schema-linking patterns that did not transfer to synthetic SQLite domains.
- Lesson: Every public benchmark gain needs a breadth/regression gate before packaging.
- Next action: Keep public and synthetic adapters separate unless a candidate passes both gates.

### Blended public+synthetic SFT

- Recipe: Public rows + synthetic rows mixed into one adapter.
- Evidence: public `0.297`, synthetic execution `0.560`.
- Status: `failed`.
- Failure reason: Naive mixture training caused interference and output-format collapse.
- Lesson: Mixing domains is not automatically regularization; it can reduce both capabilities.
- Next action: Use routing, data-mix search, or explicit slice gates before another blended adapter.

### Static multi-LoRA composition

- Recipe: Public + synthetic adapters composed with fixed weights.
- Evidence: best public-pass setting still synthetic-failed.
- Status: `failed`.
- Failure reason: Fixed adapter weights produced a smooth tradeoff but no setting passed both gates.
- Lesson: Static composition cannot solve domain conflict when the right behavior depends on input type.
- Next action: Prefer input-aware routing over global composition weights.

### Routed public + synthetic adapters

- Recipe: Route public schemas to public adapter; synthetic DB rows to synthetic adapter.
- Evidence: public exact `0.531`, synthetic execution `0.860`.
- Status: `worked-with-caveat`.
- Failure reason: The routed artifact lacks public execution benchmarking and perf/package gates.
- Lesson: Routing preserves both measured slices, but artifact status still depends on public execution and performance evidence.
- Next action: Add public execution gate, latency/RAM/tok-s measurement, and a package decision.

### Hygiene SimPO/DPO

- Recipe: Ref-free SimPO on 108 SQL-only preference pairs.
- Evidence: execution `0.860 -> 0.080`, clean-SQL `0.000 -> 0.000`.
- Status: `failed`.
- Failure reason: Ref-free SimPO update collapsed the policy and produced degenerate fenced/prose outputs.
- Lesson: Preference tuning needs reference anchoring, smaller updates, and composed-eval checks.
- Next action: Retry with reference-anchored DPO or much lower LR/step count on the same frozen pairs.

### SQL candidate selection

- Recipe: Choose best SQL among candidates before open generation.
- Evidence: tooling and smoke exist; no model run.
- Status: `not-tried`.
- Lesson: Highest-priority next recipe.
- Next action: Run only after candidate rows are generated without leakage.

### Offline rollout / OAPL-style SQL update

- Recipe: Batch rollouts, score offline, one adapter update.
- Evidence: plan renderer exists; no model run.
- Status: `not-tried`.
- Lesson: Run only after candidate-selection reward surface is clean.
- Next action: Use after candidate selection proves the reward/data loop.

### Controlled SQL LoRA rank sweep

- Recipe: Same data, ranks `{1,2,4,8}`, fixed seed/steps/LR.
- Evidence: not run.
- Status: `not-tried`.
- Lesson: Needed to separate capacity from data/recipe confounds.
- Next action: Run only after the next target/eval is frozen.

## Non-SQL Model / Artifact Attempts

### Qwen3-4B file-ops distilled specialist

- Evidence: file-ops hard gate `0.58 -> 1.00`; breadth `0.596 -> 0.423`.
- Status: `worked-with-caveat`.
- Failure reason: The specialist improved the narrow file-ops gate but regressed out-of-domain breadth.
- Lesson: The artifact is useful only with routed-only positioning; it should not be sold as a general planner.
- Next action: Keep routed-only warnings prominent and add loader/pull smoke before wiring consumers.
- Confidence: `exact`.

### Qwen3-4B ReST fused breadth recovery variant

- Evidence: depth `100%`, breadth `65%` vs stock breadth `60%`.
- Status: `worked-with-caveat`.
- Failure reason: The artifact is archived as a comparison model, not promoted as the selected specialist.
- Lesson: Breadth recovery variants are useful evidence, but need current factory reports before promotion.
- Next action: Promote only after a current eval report, package metadata, and routed-use decision exist.
- Confidence: `inferred`.

### Qwen3-4B multibackend distilled variant

- Evidence: depth `100%`, breadth `31%`.
- Status: `regressed`.
- Failure reason: Negative transfer damaged breadth even though depth remained high.
- Lesson: Multi-backend distillation can over-specialize and needs breadth gates by default.
- Next action: Keep as failed comparison evidence; do not promote without a new breadth-preserving recipe.
- Confidence: `exact`.

### VibeThinker 3B agentic distilled variant

- Evidence: weights preserved; current eval promotion missing.
- Status: `inconclusive`.
- Failure reason: The weights exist, but the docs do not preserve a current factory eval proving a win.
- Lesson: Preserved weights are not a ship decision.
- Next action: Run the factory eval gate and publish a before/after report before using it as a specialist package.
- Confidence: `exact`.

### Apple on-device Foundation Models action-grounding probe

- Evidence: BFCL agentic `25%` full catalog / approximately `0%` compact; Pace planner action-grounding `13%`.
- Status: `failed`.
- Failure reason: Apple's on-device model could not ground actions well enough and its 4096-token context could not hold a real tool catalog.
- Lesson: Apple Foundation Models are useful as a free routing floor and intel source, not as the core capability dependency.
- Next action: Keep Core ML for our own weights as an optional future battery optimization, not a model-dependency bet.
- Confidence: `exact`.

## Pace Planner / Clarify Attempts

### Pace Qwen3-0.6B planner specialists v1-v11

- Evidence: v11 reached train loss `0.001` but refused `0/30` held-out OOS prompts; drilldown shows Pace v9-LoRA `0%/22%/3%` and v11-LoRA `0%/15%/17%` on ambig/oos/destructive.
- Status: `failed`.
- Failure reason: The 0.6B specialists memorized surface behaviors but did not learn the planner judgment rules needed for held-out refusal and clarification.
- Lesson: A tiny local specialist can memorize a corpus without acquiring the product judgment capability.
- Next action: Do not train v12; use larger base models or a different premise when the missing skill is judgment.
- Confidence: `exact`.

### Pace clarify-v1 Qwen3-4B LoRA

- Evidence: 38 contrastive rows moved ambig only `0% -> 5%` while OOS regressed `80% -> 33%` in the retrospective; drilldown records the same attempt as `2%/40%/50%` on ambig/oos/destructive.
- Status: `regressed`.
- Failure reason: Small-corpus LoRA on a competent base caused catastrophic interference across planner dimensions.
- Lesson: Fine-tuning a strong base on a thin behavior slice requires coverage for every dimension that must not regress.
- Next action: Do not fine-tune the planner on narrow clarify rows unless the corpus also covers OOS, destructive, happy path, and breadth gates.
- Confidence: `inferred`.

### Pace two-stage ambiguity detector shim v2

- Evidence: ambig moved `0% -> 20%`, while OOS dropped `78% -> 55%` and destructive stayed `67%`; not shipped on top of Gemma.
- Status: `worked-with-caveat`.
- Failure reason: The shim improved ambiguity detection for the 4B floor but over-triggered and became unnecessary once Gemma reached the same ambig score with better OOS/destructive behavior.
- Lesson: Rule wrappers can expose the missing behavior, but they still need the same regression gates as model updates.
- Next action: Keep as an option only if shipping the 4B footprint floor; do not stack it on the stronger Gemma path.
- Confidence: `exact`.

### Pace reasoning-model unhappy-path drill

- Evidence: Qwen3-4B-Thinking scored `0%/10%/0%` and DeepSeek-R1-Distill-Qwen-7B scored `0%/3%/0%` on ambig/oos/destructive under a 300-token cap.
- Status: `inconclusive`.
- Failure reason: The evaluation budget was consumed by think traces, so the apparent zero scores were not a fair model-quality verdict.
- Lesson: Reasoning models need adequate max tokens and a stop-on-think strategy before interpreting planner scores.
- Next action: Re-run with max_tokens >= 1024 and stop on `</think>` only if Gemma or the locked planner fails in production.
- Confidence: `exact`.

### Pace Gemma-3-12B unhappy-path drill winner

- Evidence: Gemma-3-12B scored `22%` ambig, `82%` OOS, `77%` destructive and won all three unhappy-path dimensions in the n=130 drill.
- Status: `worked-with-caveat`.
- Failure reason: Gemma won the drill but ambiguity remained poor in absolute terms and the decision was later superseded by the general planner lock.
- Lesson: A stronger zero-shot base beat the local fine-tunes, but model-selection evidence can be superseded by later broader gates.
- Next action: Keep as historical unhappy-path evidence; prefer current `PROJECT_STATUS.md`/`docs/NEXT.md` for active planner decisions.
- Confidence: `exact`.

### Pace Qwen3.5 challenger round

- Evidence: Qwen3.5-9B scored `18%/97%/63%`; Qwen3.5-4B scored `15%/55%/70%` on ambig/oos/destructive; champion stood.
- Status: `worked-with-caveat`.
- Failure reason: Qwen3.5 improved some dimensions, especially OOS for 9B, but did not beat the stored champion across the full swap decision.
- Lesson: Single-dimension wins do not justify a planner swap when another required dimension regresses.
- Next action: Use `scripts/eval_planner.sh` for future challengers and keep swap/no-swap verdicts tied to all required dimensions.
- Confidence: `exact`.

## Browser Product / Demo Attempts

### Browser Memory64 large-preset runs

- Evidence: larger browser presets hit Memory64 OOB; matching Node direct-export reproducer passed XL; `INITIAL_MEMORY=268435456` fixed up to XL while Behemoth still exercises growth.
- Status: `worked-with-caveat`.
- Failure reason: The original retries treated the OOB as a model-size problem before the matching reproducer showed a browser pthread plus SharedArrayBuffer memory-growth race.
- Lesson: A reproducer must match the production host and call path before it can explain a browser-only WASM failure.
- Next action: Keep the higher initial memory for supported presets and only claim Behemoth after a SAB-view-aware growth path lands.
- Confidence: `exact`.

### Browser speedup headline curve

- Evidence: single `9.7x` headline was replaced by a preset curve: Small `2.6x`, Medium `6.8x`, Large `9.3x`, XL `12.1x`.
- Status: `worked-with-caveat`.
- Failure reason: The original one-number headline made a shape-dependent performance result look like a universal property of the code.
- Lesson: If a performance result depends on preset size, publish the curve rather than the most convenient point.
- Next action: Keep future public performance artifacts tied to config-specific tables with reproduction context.
- Confidence: `exact`.

### Browser default corpus fix

- Evidence: the old default corpus was `863 bytes`; a Huge model memorized it with train loss `0.14`; default changed to TinyShakespeare at about `1.1 MB`.
- Status: `worked-with-caveat`.
- Failure reason: The demo was trying to prove learning with a corpus so small that memorization looked like training success.
- Lesson: Default data is part of the product claim; a training demo's default corpus must produce non-memorized samples.
- Next action: Keep corpus defaults in the same parity review as model and optimizer defaults.
- Confidence: `exact`.

### Browser learning-rate default drift

- Evidence: browser default LR was `3e-3` while Python reference used `3e-4`; training plateaued around loss `2.45` until the browser default was changed.
- Status: `worked-with-caveat`.
- Failure reason: Reference/kernel parity tests covered math drift but not hyperparameter default drift.
- Lesson: Reference defaults are part of correctness, not just documentation.
- Next action: Add or keep a config-default parity check whenever browser and reference paths share a training story.
- Confidence: `exact`.

### Browser WebGPU export serialization

- Evidence: a trained WebGPU run was lost because `webgpu/gpu_model.ts` had no checkpoint serialization; `exportState` was then implemented and worker plumbing updated.
- Status: `worked-with-caveat`.
- Failure reason: The training path could produce useful weights that the WebGPU backend could not export, and auto-cleanup destroyed a real trained artifact.
- Lesson: Long-running browser training is not product-complete until the smallest export path is smoke-tested before the long run.
- Next action: Smoke export on a short WebGPU run before any long browser training claim.
- Confidence: `exact`.

### Browser generation streaming and KV cache

- Evidence: tokens/sec counter was added, but browser generation still lacked KV cache and true token streaming; task `#72` was logged.
- Status: `not-tried`.
- Lesson: A typewriter animation over an already-complete response is not true streaming.
- Next action: Add worker protocol support for intermediate tokens and KV-cached browser generation before claiming interactive decode latency.
- Confidence: `not-applicable`.

## Runtime / Browser / Architecture Attempts

### WASM backward-scratch reuse

- Evidence: standard `304 -> 305 ms/step`, capable `632 -> ~640 ms/step`.
- Status: `worked-with-caveat`.
- Failure reason: Caching backward scratch buffers removed hot-path allocations but produced no measurable speedup because compute, not malloc, was the bottleneck.
- Lesson: Hot-path hygiene is not the same as a performance win; measure the real step time before claiming speedup.
- Next action: Keep the allocation cleanup, but do not prioritize allocator work until profiling shows allocation cost again.
- Confidence: `exact`.

### WASM SIMD training speedup

- Evidence: standard `304 -> 191 ms/step`, capable `632 -> 391 ms/step`, net `1.6x` speedup.
- Status: `worked`.
- Lesson: Emscripten/LLVM autovectorization was the right browser-training speed lever before hand-written kernels.
- Next action: Keep SIMD enabled by default and use the WASM smoke gate to protect training correctness.
- Confidence: `not-applicable`.

### Browser WebGPU training loop

- Evidence: 24 kernel parity checks, GPU overfit gate loss `5.55 -> 0.002` in 150 steps, and headless-browser e2e passed.
- Status: `worked-with-caveat`.
- Failure reason: Correctness is proven, but speed is not measured because headless Chromium exposes SwiftShader software WebGPU rather than a real GPU.
- Lesson: GPU API correctness can be CI-proven, but performance claims require a hardware adapter measurement.
- Next action: Collect the documented real-device WebGPU vs WASM-SIMD benchmark before quoting a browser GPU speedup.
- Confidence: `exact`.

### WASM register/cache-blocked matmul

- Evidence: microbench `3-4x`, but end-to-end WASM training only `1.03-1.06x` after forward blocking.
- Status: `worked-with-caveat`.
- Failure reason: The isolated microbench overstated impact because the real WASM training workload was threaded, already SIMD-vectorized, and dominated by backward matmuls.
- Lesson: Optimize and report on the real workload, not only on isolated single-kernel microbenches.
- Next action: Keep the bit-exact forward kernel for inference, but judge future perf work with end-to-end training and generation benches.
- Confidence: `exact`.

### WASM backward_dA blocking

- Evidence: fwd+bwd-blocked reached small `90.3`, medium `317.6`, large `1057.4`, xl `1643.6`, or about `1.10-1.13x` over naive.
- Status: `worked-with-caveat`.
- Failure reason: The backward_dA optimization improved end-to-end training, but the remaining backward_dB path still limits the total speedup.
- Lesson: Training speed follows the backward-pass bottleneck; forward-only wins are capped until dA and dB are addressed.
- Next action: Only continue matmul blocking if backward_dB or generation benches show enough remaining headroom.
- Confidence: `exact`.

### Speculative-decoding heads Medusa/EAGLE smoke

- Evidence: baseline `232 tok/s`; Medusa 50-step `202 tok/s` at `21.7%`; Medusa 300-step `375 tok/s` at `20.8%`; EAGLE-2 50-step `200 tok/s` at `26.5%`, all bit-identical where verified.
- Status: `worked-with-caveat`.
- Failure reason: The heads trained and verified losslessly, but acceptance stayed far below the paper recipes because this run lacked long training, logit distillation, tree attention, and a full EAGLE transformer draft block.
- Lesson: Speculative heads are a valid local speed path, but the production recipe is data/training heavy rather than a quick sidecar smoke.
- Next action: Revive only with self-generated data, logit-KL distillation, tree verification, and a real acceptance-rate gate.
- Confidence: `exact`.

### MoE dense-compute smoke

- Evidence: Dense MLP `842 K` params loss `6.09 -> 1.76` at `55.6 step/s`; MoE 4 experts top-2 `2.42 M` params loss `5.95 -> 1.68` at `29.3 step/s`.
- Status: `worked-with-caveat`.
- Failure reason: The MoE architecture, save/load, sample, eval, and inspect paths work, but the current compute path runs every expert and therefore does not deliver sparse-dispatch savings.
- Lesson: MoE is a capacity feature until sparse gather/scatter or grouped matmul lands; it should not be marketed as a compute-saving win yet.
- Next action: Return to MoE only with MLX scatter_add/grouped matmul support or a scoped custom Metal sparse-dispatch kernel.
- Confidence: `exact`.

### CPU speedup bundle

- Evidence: all four items ON reached median `6.8 step/s` vs `5.0 step/s` baseline, `+36%`, with final loss `4.188-4.192` unchanged.
- Status: `worked-with-caveat`.
- Failure reason: The bundle produced a real host-side speedup, but QoS and compiled cosine LR were individually in the noise, prefetch stayed single-digit, and open CPU items remained.
- Lesson: The big win was fused accumulation inside the compiled trace; individual CPU tweaks need isolation before being credited.
- Next action: Use the bundle as shipped, but keep Rust-FFI BPE, preallocated CPU buffers, and SVD-on-CPU AMX as separate future attempts.
- Confidence: `exact`.

### Cold-start bundle

- Evidence: mmap saved `10-20 ms` and `25 MB` peak RSS on `demo.tinygpt`; lazy embedding deferred `262.1 KB`; package tests passed `43/43`.
- Status: `worked-with-caveat`.
- Failure reason: The cold-start path improved the measured demo case, but the 250 MB target file was missing, async spinner overhead added about `30 ms`, and persistent Metal pipeline caching was infeasible through public MLX-Swift APIs.
- Lesson: mmap and direct byte construction are good scaling levers, but large-model cold-start claims need large-model measurements.
- Next action: Re-measure on a real 50-250 MB checkpoint and keep persistent Metal cache work parked unless MLX-Swift exposes pipeline descriptors.
- Confidence: `exact`.

### Gradient checkpointing Mac training

- Evidence: behemoth B=4 ctx=1024 peak memory dropped `27679 MB -> 17816 MB` while step/s moved `0.4 -> 0.3`; tiny memory worsened `161 MB -> 189 MB`.
- Status: `worked-with-caveat`.
- Failure reason: Checkpointing recovered large-model memory but hurt small-model memory and speed, and the OOMGuard estimator still reports uncheckpointed activation projections.
- Lesson: Activation recompute is a scale-dependent lever; it should stay opt-in for models where memory, not step time, is the blocker.
- Next action: Update memory estimation for `--grad-checkpoint` and consider selective layer checkpointing before broad default use.
- Confidence: `exact`.

### KV cache optimization bundle

- Evidence: prompt-cache hot run `1.005 s -> 0.106 s`; pre-alloc decode stayed `706 -> 711 tok/s` with physical cache flat at `6.3 MB`.
- Status: `worked-with-caveat`.
- Failure reason: Persistent prompt cache delivered the TTFT win, but pre-alloc was kept opt-in, pre-alloc does not compose with KIVI or StreamingLLM, and some cache keying edge cases remain.
- Lesson: Reuse of prefilled KV is the user-visible win; cache storage policy changes need composition gates before becoming defaults.
- Next action: Keep prompt-cache as the main shipped path and revisit pre-alloc defaults only after KIVI/StreamingLLM interactions are designed.
- Confidence: `exact`.

### YOCO cache-halving smoke

- Evidence: huge cache at 206 tokens dropped `5.1 MB -> 2.5 MB`, while throughput moved `767 -> 676 tok/s`.
- Status: `worked-with-caveat`.
- Failure reason: YOCO halved decode KV cache memory, but throughput dropped at ctx=256 and HF checkpoint round-trip or production-quality YOCO weights were not proven.
- Lesson: YOCO is a long-context memory lever, not an immediate short-context speedup.
- Next action: Treat YOCO as a long-context experiment until anchor tuning, HF round-trip, and long-context quality gates exist.
- Confidence: `exact`.

### StreamingLLM + KIVI cache compression

- Evidence: StreamingLLM reduced 500-token cache `12.6 MB -> 6.4 MB`; int8 KIVI matched greedy baseline `100%` and int4 averaged `96%` prefix match.
- Status: `worked-with-caveat`.
- Failure reason: The cache compression worked in smoke tests, but int4 precision still used int8 storage bytes, K scales recompute every step, and no held-out perplexity gate measured quality.
- Lesson: KV compression can preserve greedy decode locally, but storage format and quality gates matter before making long-context claims.
- Next action: Add packed int4 storage or grouped KIVI scales only after a cached-forward perplexity or trajectory-match eval exists.
- Confidence: `exact`.

### Data-side sample packing and BPE-dropout

- Evidence: sample packing flattened CoV `0.582 -> 0.061`; BPE-dropout 100-step smoke stayed stable with final loss `7.382` baseline vs `7.597` dropout.
- Status: `worked-with-caveat`.
- Failure reason: Sample packing's histogram property was proven, but BPE-dropout was only a stability smoke and did not prove downstream generalization on this corpus.
- Lesson: Data-pipeline regularizers need behavioral evals, not just stable loss curves, before being treated as quality improvements.
- Next action: Use sample-packing where length bias matters, and evaluate BPE-dropout on rare-word or morphology-sensitive gates before promotion.
- Confidence: `exact`.

### MLXFast SDPA and tied-embedding audit

- Evidence: audit found SDPA call sites and tied-embedding build/save/load paths clean; build succeeded and sample smoke reached `603 tok/s` on demo and `261 tok/s` on mega5.
- Status: `worked`.
- Lesson: The suspected SDPA mask/contiguity and tied-embedding duplication issues were not present.
- Next action: Keep this as positive verification; only reopen if new SDPA call sites or untied embedding save paths are added.
- Confidence: `not-applicable`.

## Tool-Calling / Eval Infrastructure Attempts

### A1 first tool-calling specialist harness

- Evidence: recipe and acceptance harness shipped; training run pending GPU Mac + local BFCL checkout.
- Status: `not-tried`.
- Lesson: The four-step specialist contract is reusable, but the model claim does not exist until BFCL training/eval runs.
- Next action: Run BFCL baseline, SFT, adapter eval, and +3pp gate once GPU/BFCL prerequisites are available.
- Confidence: `not-applicable`.

### B1 SQL eval infrastructure

- Evidence: `posttrainllm eval-sql` shipped and smoke-tested; training/generation originally pending GPU.
- Status: `worked-with-caveat`.
- Failure reason: The scoring half existed before the live SQL factory run, but the original PRD did not include trained adapter evidence.
- Lesson: Execution accuracy over SQLite is the right reusable gate; infra alone is not a specialist result.
- Next action: Continue using eval-sql as the frozen SQL gate and attach run folders to model claims.
- Confidence: `exact`.

Primary SQL source docs:

- [`docs/specialists/b1-sql-poc.md`](specialists/b1-sql-poc.md)
- [`docs/techniques/sql-technique-backlog.md`](techniques/sql-technique-backlog.md)
- [`docs/factory/public-artifacts.md`](factory/public-artifacts.md)
- Local run reports under `runs/2026-07-02-*` and
  `runs/2026-07-03-sql-hygiene-dpo-qwen06/`

## Factory / Documentation Attempts

### Factory run schema

- Evidence: `docs/factory/run-schema.md` defines the expected run folder.
- Status: `worked-with-caveat`.
- Failure reason: The schema exists, but real train/eval commands still need to emit every file automatically.
- Lesson: A schema is necessary but not sufficient; publish checks must enforce complete run folders.
- Next action: Wire live train/eval commands to produce schema-complete run folders automatically.
- Confidence: `exact`.

### SQL factory run renderer

- Evidence: `scripts/render_sql_factory_run.py` renders canonical SQL report artifacts.
- Status: `worked-with-caveat`.
- Failure reason: The renderer is a useful bridge but not yet one universal factory command.
- Lesson: Rendered reports made SQL publishable, but the factory still needs command-level automation.
- Next action: Use the renderer until the canonical train/eval/report command can emit the same artifacts directly.
- Confidence: `exact`.

### Public artifact registry

- Evidence: `docs/factory/public-artifacts.md` tracks artifacts, blockers, release state.
- Status: `worked`.
- Lesson: Public artifacts and blockers are first-class.
- Next action: Keep every artifact entry updated before a release push.
- Confidence: `not-applicable`.

### Technique registry

- Evidence: `docs/techniques/` distinguishes methods from recipes.
- Status: `worked-with-caveat`.
- Failure reason: The registry exists, but the next SQL recipe still needs validator/release enforcement before training claims.
- Lesson: Method names are not enough; recipes need failure mode, data, eval, slice gate, and stop rule.
- Next action: Require a recipe card before any new post-training run.
- Confidence: `exact`.

### TrainLoop-style tooling

- Evidence: candidate choice, slice metrics, trace review, batch plan, LoRA geometry smokes pass.
- Status: `worked-with-caveat`.
- Failure reason: The tools exist and pass smokes, but most recipes have not yet been trained with them.
- Lesson: Discipline is valuable only when enforced in every reported run.
- Next action: Do not report the next SQL candidate without `slice-metrics.json` and `trace_review.md`.
- Confidence: `exact`.

## Historical Coverage Limits

This ledger is now schema-complete for the structured attempts in
`docs/attempts.json`: each entry has status, evidence, confidence, lesson, next
action, and evidence sources. It is **not** a claim that every structured entry
has equal certainty.

Current structured coverage:

| Confidence | Count | Meaning |
|---|---:|---|
| `exact` | 39 | Direct run report, decision file, artifact metadata, or current source doc supports the reason. |
| `inferred` | 5 | Reason is reconstructed from docs/artifact notes, not a canonical run folder. |
| `not-applicable` | 9 | No failure reason is expected for worked/not-tried status. |
| `missing-evidence` | 0 | No structured entry currently uses this label. |

This is also not a claim that every scratch experiment in the repo's older
archive has been normalized. Older archive/session docs still contain
additional lessons, but they should enter this ledger only when we can attach a
status, evidence, confidence, lesson, and next action without inventing history.
See [`history-coverage-audit.md`](history-coverage-audit.md) for the current
coverage boundary.

## Next Ledger Improvements

Required future fields for full historical precision:

- run id
- git commit / binary provenance
- dataset hash
- exact commands
- train/eval cost
- latency/RAM/tok-s
- report URL
- artifact URL
