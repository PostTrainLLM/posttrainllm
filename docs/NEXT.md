# PostTrainLLM Closure and Fresh-Experiment Gate

The historical model and experiment work is fully accounted for. Issue #136 is
closed. Serial Swift and browser builds, current CLI runtime evidence,
responsive rendered review, dependency-security disposition, completion
validation, tests, coverage, current-SHA CI, deployment, and the live guest
audit all passed for the completion release. This document preserves the factory
sequence as lab context. It is not a second task queue.

Issue #137 remains the only external release queue: it owns notarization and the
final public distribution receipt. Issue #138's controlled ReST, Parakeet,
WebGPU, and Needle experiment tranche was completed on 2026-09-03 with four
tracked decisions and no open experimental run. Neither issue revives the
historical TODOs below.

Fresh work begins only when the owner has chosen a new question—normally after
completing a relevant path in
`docs/learn/path-registry.json`—and opens a scoped GitHub Issue that names:

- the baseline and candidate recipe;
- the frozen primary and regression evals;
- the data source and leakage boundary;
- the bounded time, compute, RAM, and cost budget;
- the ship, retry, and reject thresholds.

Issue #138 satisfied the written-spec and owner-review portions of that gate;
its bounded runs are now closed. No other training, model download, PRD
expansion, or parked lane is authorized merely because it appears below.
Conditional next actions, TODO markers, and blockers in retained historical
documents explain what was not built; they do not mean the closed project is
incomplete.

For the full documentation path, start at `docs/README.md`. Browse all 76 final
attempts at `/experiments`, the 18 recipe contracts at `/recipes`, and the nine
ready paths plus thirteen buildable artifacts at `/learn`. The artifact
contract is tracked in `docs/learn/artifact-journey.json`. For reviewed external
products and techniques, use `docs/external-products-reviewed.md`.

## Release Acceptance Envelope

The completion claim is split into five receipts. A green earlier receipt does
not imply that a later one happened.

| Receipt           | Required proof                                                                                                                                          | Current state (2026-09-03)                                                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Local source      | Completion validator, unit tests, coverage, quality, and clean diff checks pass                                                                         | **Passed**: 76 experiments, 18 recipes, 9 paths, 13 journey artifacts, 17 public artifacts, 0 unresolved statuses; attempt, completion, report-card, browser-test, and quality gates are green |
| Native CLI        | Serial release build, discovery/runtime smoke, and Xcode tests pass on the current source                                                               | **Passed**: release build and 107-entry runtime catalog pass; 218 Xcode tests pass, 6 optional-fixture tests skip, production coverage 32.51% |
| Browser build     | Production Astro/docs/agent build and internal-link checker pass                                                                                        | **Passed**: 46 app pages, 310 docs pages, 359 paired agent surfaces, and 110,565 internal links checked                                      |
| Rendered UI       | `/`, `/experiments`, `/recipes`, `/learn`, Needle, Parakeet, and CLI docs pass keyboard, interaction, console, overflow, and 390/768/1440 px inspection | **Passed**: all 36 route/viewport checks are green with zero overflow, console, page, request, or P0/P1 failures; hero-curve clearance is enforced at 56px                             |
| Published release | Exact source is committed and pushed, current-SHA CI is green, deployment succeeds, and live guest checks match the source                              | **Passed for the earlier completion SHA only**: `ebe1ba6`, CI run `33561299127`, deploy run `33562477716`, and all 21 live route/viewport checks. The 2026-09-03 closeout is not yet claimed deployed. |

The completed release ran the boundary in this order:

1. Build and test the native CLI serially; run `commands`, `help`, `version`,
   unknown-command, and factory/experimental discovery smokes against that
   binary.
2. Run `pnpm --dir browser run build`, including the docs/agent builders and
   generated-link checker.
3. Preview the production output and refresh the design receipt at 390, 768,
   and 1440 px. Kill every preview/browser process started for the review.
4. Re-run completion, test, coverage, quality, and `git diff --check` after any
   fixes.
5. With source-publication approval, commit and push the exact checked tree,
   wait for current-SHA CI, explicitly trigger deployment, and verify the live
   guest journeys.
6. Reconcile `PROJECT_STATUS.md` and Issue #136 only after the live SHA and
   surfaces match, then close the project from the AI-work perspective.

## Retained Factory Thesis

posttrainllm is a Mac-local specialist factory:

```text
target -> data -> post-training -> eval -> package -> report
```

The canonical loop now has both retry and ship examples. Character Chess is now
a documented failed lane, not the active target. Its owned 44.53M model passed
the eight-position wiring gate, then the owner-approved target-masked 10k pilot
reached 10.54% validation exact versus 6.16% analytic random (+4.38 points) and
10.33% test exact versus 6.23% (+4.10). That missed the frozen +10-point gate.
More importantly, both raw and guarded policies won 0/6 games against random
legal play; eight guard interventions produced no wins. Do not run the 100k,
1M, or 2M stages under this recipe. Preserve the failed artifact and its
reusable masked-SFT, legal-candidate, guard, ladder, and replay infrastructure.
No new training target is selected; choose one before another model run.

The Everyday Specialist Benchmark and specialist capability graph are now
completed infrastructure. Their first measured routed-system attempt is a
useful negative result: Pace v8 plus Apple on-device fallback cannot meet the
frozen selective gates (perfect-router oracle 96.4% versus a 99% final bar).
Do not tune those gates or present the development cascade as qualified. A
future routed candidate needs better leaves and a newly frozen evaluation, not
more threshold search on this public set.

## Fresh-Experiment Operating Rule

Every newly authorized task must answer one of these:

1. Can we prepare or improve the data?
2. Can we post-train a candidate?
3. Can we evaluate it against a frozen baseline?
4. Can we package it as a specialist artifact?
5. Can we report score delta, regressions, cost, latency, RAM, and a decision?

If not, it is outside the closed lab and needs a separately scoped project.

Post-training tasks must also name a **recipe**, not only a method. Use
`docs/techniques/` before training:

- `docs/techniques/method-vs-recipe.md` defines the standard.
- `docs/techniques/sql-technique-backlog.md` is the closed SQL recipe lineage.
- `docs/techniques/trainloop-teardown.md` records the latest external teardown.

"Try DPO", "try RLVR", or "try a different LoRA rank" is not specific enough.
The recipe must name the failure mode, data, eval gate, slice gate, and stop
rule.

## OpenSpec completion reprioritization (2026-07-25)

The owner explicitly reprioritized finishing all OpenSpecs. That decision
started the **no-model foundation tranche** of
`build-mac-local-autocorrect-specialist` without selecting or training a new
model target. The verified foundation is documented in
[`factory/autocorrect-foundation.md`](factory/autocorrect-foundation.md):
versioned contract/taxonomy/threshold fixtures, tiny consented original
fixtures, strict evaluator, source-first leakage/provenance checks, Mac keyboard
simulator with edit traces, bounded tiny-overfit/pilot manifests, distribution
report, and an Apple protocol assessment.

Codex/frontier calibration (task 2.5), pinned base-model research, and the
approved three-candidate offline bake-off (tasks 4.1-4.5) are complete. The
18-row smoke ruler required no repair. FLAN-T5-small is frozen as the smallest
plausibly trainable base: it stayed within the resource envelope but reached
only 6.25% zero-shot error reduction, 66.67% clean preservation, and 86.67%
protected-span preservation. Exact commands and measured evidence are in
[`factory/autocorrect-model-shortlist.md`](factory/autocorrect-model-shortlist.md)
and `evals/autocorrect/base-bakeoff-v1.json`.

Tasks 5.1-5.2 completed 2026-07-25 without training. The ordinary supervised
recipe is frozen in `evals/autocorrect/adapter-recipe-v1.json` and the
encoder-decoder LoRA path is implemented in `scripts/research/autocorrect_adapter.py`;
both are documented in
[`factory/autocorrect-adapter-recipe.md`](factory/autocorrect-adapter-recipe.md).
Measured forward-only on CPU against the real pinned base: 48 adapted modules,
344,064 trainable parameters (0.4471%), and logits bit-identical after injection
(max absolute delta 0.0). 19 offline tests pass via
`bash evals/autocorrect-adapter-smoke.sh`. LoRA is hand-rolled so torch,
transformers, and peft stay off the project dependency surface.

Task 5.3, the repeated-data overfit gate, ran 2026-07-25 with owner approval and
**passed**: exact match 1.0 at step 50 of 200, loss 1.585 -> 0.030, 0.28 min,
1,135 MiB peak RSS on MPS. Evidence:
`evals/autocorrect/tiny-overfit-result-v1.json`. Read the caveat before quoting
it — the fixture has one unique target, so the score measures capacity and
wiring, not correction, and the diagnostic probe showed copy bias, memorization
leakage, and instruction echo on unseen input.

Tasks 5.4-5.5 ran 2026-07-25 with owner approval and the **pilot regressed**:
error reduction `+0.0625 -> -0.8125` on the unchanged frozen suite, unnecessary
edit rate 0.839 against a 0.005 bar. The failure mode is overcorrection, not
copy bias — the model became a paraphraser. Evidence:
`evals/autocorrect/pilot-result-v1.json`.

Two blockers came out of it:

1. **The pilot was truncated by construction.** It stopped at step 50 of 300 on
   `stop_on_clean_preservation_below: 0.995`, but the base's own zero-shot clean
   preservation is 0.667, so that ship-grade bar fires at the first evaluation
   regardless of training.
2. **Tasks 5.6-5.7 are rejected, not pending.** An edit-aware objective
   up-weights edit positions, which targets the opposite of the measured failure
   and would push overcorrection past 5.7's own reject condition.

**Do not run further training under `adapter-recipe-v1`** — it has reached its
stop rule and its movement policy forbids moving bars inside a live run. The
next step is a `v2` recipe that separates training stop rules from ship bars,
draws on more of the 26 available source documents, and adds a meaning-change
guard. That is a spec change, not a training run.

## Historical Factory Sequence (inactive)

The sequence below is retained because it is the correct execution order if a
future issue reactivates the factory. None of its steps is currently assigned.

### 0. Keep Public Artifacts First-Class

Public artifact inventory lives in `docs/factory/public-artifacts.md`. The
portable before/after proof for an artifact is its
[report card](factory/report-card.md); the published cohort and its documented
absences are in `docs/factory/report-card-cohort.md`.

Before starting a new run or release push, update the artifact entry with:

- measured evidence
- blockers
- next release action

Then recompile the report cards and confirm no drift:

```bash
python3 scripts/factory/publish_report_cards.py
python3 scripts/factory/publish_report_cards.py --check
```

New runs should emit the optional `eval-validity.json` and `cost.json`
fragments. Without them no candidate can reach a **fully verified** ship —
frontier-ceiling, frozen-eval identity, leakage, and cost/time have nowhere to
live, and every current card lists that as a blocker.

Current shipped research artifact: `qwen3-4b-rest-fused`, with package metadata,
public weights, a narrow routing decision, and a fresh paired requalification
receipt. Its legacy-package report card remains not fully verified because the
card format cannot import the raw run-folder validity fields.

All six public Hugging Face models now have dedicated case studies under
`/artifacts`, including the rejected and missing-evidence releases. Use those
pages—not Hub request counts—as the public explanation of model quality,
limitations, and next evidence action.

The last report-only priority was `qwen06-sql-routed-v1`. Its canonical report
run can be rendered with:

```bash
python3 scripts/sql/render_sql_factory_run.py --out runs/2026-07-02-sql-routed-qwen06-v1
```

### 1. Pick the Factory Target

Choose exactly one target before training.

**Queue state (2026-08-05): no active training target is selected.** Character
Chess stopped at the 10k gate: it learned a small, repeatable held-out move
signal but no demonstrable advantage over random legal play in the bounded
full-game screen. Its 100k/1M/2M stages are rejected under the current recipe;
the earlier SQL and ReST lanes remain closed or report-only.

The last POC target was the SQL specialist. Its low-compute fixture is
`evals/sql-poc/`; the brief is `docs/specialists/b1-sql-poc.md`.

**Frozen target (2026-07-03): `qwen06-sql-hygiene-dpo-v1`** — the single
preference-tuning/output-hygiene candidate from cleanup task 4. Frozen before
training:

- Baseline model: `Qwen/Qwen3-0.6B` + synthetic expanded adapter
  (`runs/2026-07-02-sql-expanded-qwen06/qwen06-sql-expanded.lora`), the
  synthetic side of `qwen06-sql-routed-v1`. Frozen baseline scores:
  synthetic execution 0.860, synthetic exact 0.840, clean-SQL raw rate 0.000
  (0/50 raw completions are a single bare SQL statement).
- Candidate method: `posttrainllm dpo` on `evals/sql-poc-expanded/preferences.jsonl`
  (108 hygiene pairs; verified zero prompt/gold overlap with the dev set),
  composed with the SFT adapter at inference via the existing multi-LoRA stack
  (`--lora sft --lora dpo`). First plan was `bake-lora` then DPO on the merged
  base, but `bake-lora` did not support DoRA adapter magnitudes at freeze time
  and the SFT adapter is DoRA — recorded as a tooling gap, not worked around
  with new infrastructure. (Gap closed 2026-07-04: `bake-lora` now bakes DoRA
  magnitudes. The frozen candidate keeps multi-LoRA composition; do not
  re-plan a frozen run.)
- Eval suite: `posttrainllm generate` + `posttrainllm eval-sql --db-dir
evals/sql-poc-expanded/dbs` on the frozen 50-row
  `evals/sql-poc-expanded/dev.jsonl`, plus the clean-SQL raw-output metric
  (single statement, starts with SELECT, no fence/prose, nothing after `;`).
- Regression suite: the public64 b-mc2 exact gate (0.531) is unchanged by
  construction — the public adapter and router are untouched. Recorded as a
  skipped recheck, not a measured one.
- Ship bar: synthetic execution >= 0.86 (no regression) AND clean-SQL raw
  rate >= 0.80. "Ship" means the candidate replaces the synthetic side of
  `qwen06-sql-routed-v1` as current-best; it does not unblock public
  packaging, which stays gated on a public execution benchmark.

**Outcome (2026-07-04): retry-training.** The ref-free SimPO run collapsed
the policy (composed execution 0.860 → 0.080, clean-SQL 0.000; the adapter
alone generates fence spam). Full schema-valid run artifacts and report:
`runs/2026-07-03-sql-hygiene-dpo-qwen06/`. Clean-SQL scorer now exists at
`scripts/sql/score_sql_clean_output.py`. Next candidate: reference-anchored DPO
(or SimPO at ~10× lower lr / ≤50 steps) on the same frozen pairs, evaluated
composed. Gotcha for future runs: record the posttrainllm binary provenance —
the 2026-06-25 release build scores identical preds at 0.000 where the
2026-07-02 debug build scores 0.860, and composes multi-LoRA differently.

**Retry outcome (2026-07-11): retry-training — collapse fixed, hygiene still
unmet.** Reference-anchored DPO (`--loss-type dpo --beta 0.1`, r4 q/v, 50 steps,
lr 5e-6) on the same 108 frozen pairs, evaluated composed. Result: **no
collapse** — composed execution `0.860 → 0.900` (+0.040), DPO-adapter-alone
`0.120` (healthy, not fence-spam), DPO step-1 loss `0.6931 ≈ log 2`. But
clean-SQL raw rate stayed `0.000`: 41/50 outputs changed yet all keep the
`Answer:`/`Explanation:` prose wrapper. Execution bar passes, hygiene bar
fails → not shipped. Reproduced the 0.860 baseline exactly first with a fresh
swift-build DEBUG binary (git 74cb267). Full run:
`runs/2026-07-11-sql-hygiene-dpo-refanchored-qwen06/` (assembled via
`scripts/factory/assemble_factory_run.py`; validates + publish-check passes). Next:
higher-pressure ref-anchored DPO (150-300 steps and/or beta 0.3, lr 1e-5),
watching exec; else fix the SFT data to emit a bare SELECT. Takeaway:
reference anchoring is the validated cure for the SimPO collapse; format
hygiene is a separate, still-open pressure problem.

**Higher-pressure retry outcome (2026-07-11): retry-data — composed DPO ruled
out for hygiene.** Ref-anchored DPO at beta 0.3 / 200 steps / lr 1e-5 drove the
loss to 0.0073 and pushed composed execution to `0.920` (+0.060 vs baseline),
but clean-SQL stayed `0.000`: the composed output keeps `Answer:` and the
DPO-alone output keeps `The answer is:`. **Across two pressure regimes (gentle
50-step and aggressive 200-step) composed rank-4 q/v DPO never removed the prose
wrapper while execution only rose — output format is SFT/base-controlled, not
DPO-reachable.** Decision: **retry-data**. Run:
`runs/2026-07-11-sql-hygiene-dpo-refanchored-b03-s200-qwen06/`.

**Diagnosis correction (2026-07-11):** the SFT data is **already clean** —
108/108 `evals/sql-poc-expanded/train.jsonl` targets are bare SELECT with no
wrapper. So the `Answer:`/`The answer is:` lead-in is the **base Qwen3-0.6B
prose prior**, not a data defect; a data rebuild would be a no-op. The hygiene
goal needs a **generation-strength** fix, not a data-content one:
(a) stronger SFT (higher rank / more epochs / more bare-SELECT examples) to
overpower the base prior, or (b) inference-time steering (few-shot bare-SELECT
exemplars, a stop sequence, or constrained-generation SELECT prefix). Since
`eval-sql` already extracts the inner SELECT (exec 0.92), a cheap deterministic
output post-process is also a legitimate hygiene fix. Execution is not the
problem (0.860 → 0.920 across retries) — only the output wrapper is.

**TrainLoop-style additions required for the next SQL retry (2026-07-04):**

1. Method-vs-recipe registry: `docs/techniques/`.
2. Case-study report shape: `docs/factory/case-study-template.md`.
3. Candidate-selection curriculum before another open-generation hygiene retry:
   `scripts/sql/build_sql_candidate_choice.py` and
   `scripts/sql/score_sql_candidate_choice.py`.
4. Slice metrics: `scripts/sql/score_sql_slices.py`.
5. Trace review: `scripts/sql/review_sql_trace.py`.
6. Batch-first rollout plan: `scripts/render_batch_posttrain_plan.py`.
7. LoRA diagnostics on every meaningful adapter: `scripts/lora_geometry.py`.

No next SQL candidate should be reported without `slice-metrics.json` and
`trace_review.md`.

Good targets:

- Pace planner/action-surface specialist.
- Routed file-ops successor that preserves breadth better than
  `qwen3-4b-file-ops-distilled`.
- A second narrow domain only if its eval is already frozen.

Exit criteria:

- Baseline model named.
- Candidate method named.
- Eval suite named.
- Regression/breadth suite named.
- Ship/reject threshold written down.

### 2. Freeze the Eval

Use existing eval plumbing first:

- `eval-gate`
- BFCL or Pace fixtures
- `eval-compare`
- failure/breadth fixtures
- latency/RAM/tok-s measurement where feasible

Do not train against a moving target.

Exit criteria:

- `eval-baseline.json` exists.
- Baseline command is recorded.
- Pass/fail threshold is recorded.
- Known eval limitations are recorded.

### 3. Prepare Data

Use existing data tools before writing new ones:

- `traces-to-data`
- `corrections-to-data`
- `reasoning-classify`
- `quality-filter`
- `dedupe`
- `synthesize` / `magpie` only when teacher data is needed

Exit criteria:

- Dataset manifest exists.
- Source provenance is recorded.
- Dedup/filter stats are recorded.
- Held-out split is locked.

### 4. Train the First Candidate

Use the cheapest method first:

1. SFT / LoRA.
2. DPO or preference tuning only after good/bad pairs exist.
3. ReST/RLVR-style loops only when the reward is verifiable.
4. Merge/routing only after measuring breadth damage.

Exit criteria:

- Training config is saved.
- Train log is saved.
- Adapter/model artifact path is recorded.
- No extra model/base churn happened mid-run.

### 5. Evaluate and Decide

Compare candidate to baseline and incumbent.

Required report fields:

- score delta
- pass/fail
- regressions
- breadth retention
- latency
- RAM or peak RSS when available
- token throughput when available
- cost/time
- artifact path
- ship/reject/retry decision

Exit criteria:

- `report.md` exists.
- `decision.json` exists.
- Specialist package is created only if the decision is `ship`.

## Historical Verification Reference

These commands describe the retained factory verification surface. They are
useful inside a newly authorized experiment, but they are not recurring work
items in the closed lab.

0. Run the no-GPU factory smoke set for the TrainLoop-style additions:
   `bash evals/sql-choice-smoke.sh`,
   `bash evals/sql-trace-review-smoke.sh`, and
   `bash evals/lora-geometry-smoke.sh`.
   0.1. Run the stricter publish evidence smoke:
   `bash evals/factory-publish-check-smoke.sh`.
   0.2. Run the docs golden-path smoke:
   `bash evals/docs-world-class-smoke.sh`.
   0.3. Run the factory-run assembler bridge smoke:
   `bash evals/factory-run-assemble-smoke.sh`.
   0.3.1. Run the durable lifecycle smoke:
   `bash evals/factory-run-lifecycle-smoke.sh`.
   0.4. Run the fine-tune report card smoke:
   `bash evals/fine-tune-report-card-smoke.sh`.
   0.5. Run the autocorrect no-model smokes:
   `bash evals/autocorrect-foundation-smoke.sh` and
   `bash evals/autocorrect-adapter-smoke.sh`. Both are now in the CI evals job.
1. ~~Verify live command evidence emission on the next approved factory run.~~
   **Done (2026-08-22):** closed as superseded (#69). The infrastructure is
   merged and smoke-verified; live-run verification is now implicit in the next
   real factory run rather than a standalone ticket.
   **Bridge (2026-07-11):** `scripts/factory/assemble_factory_run.py` is the
   generic report-artifact bridge. It turns the emitted fragments (`config`,
   `dataset`, `eval-baseline`, `eval-candidate`, `decision`, optional
   `artifact`/`slice-metrics`/`trace_review`) into a canonical run folder with
   derived `provenance.json` (git + real dataset SHA-256) and `report.md` (eval
   delta computed, not typed), and the output passes both
   `scripts/factory/check_factory_run_publish.py` and the typed Swift `FactoryRunFolder`
   validator (smoke: `bash evals/factory-run-assemble-smoke.sh`).
   `scripts/sql/render_sql_factory_run.py` remains the SQL-specific one-shot renderer.
   **Lifecycle metadata (2026-07-25):** new native renders and generic
   assemblies emit versioned `run-status.json`, update verified advisory
   current/latest pointers, and record boundary transitions only after durable
   metadata writes. `factory-run init/status/transition/list/reconcile` are
   metadata-only; stale active runs remain active-with-warning until explicit
   operator action. Legacy folders remain valid and can be imported explicitly
   without invented history. This does not resume training or alter
   `decision.json`/publication authority.
   **`--factory-run` flags (2026-08-04):** opt-in integration has Swift `sft`
   record bounded training/cost/artifact evidence, `eval-gate` record the frozen
   primary suite's canonical baseline/candidate pair, and `eval-compare` derive
   compatible slice metrics. Typed writes cross lifecycle boundaries only after
   durable validation, and `bash evals/factory-run-live-evidence-smoke.sh`
   proves the full metadata path without loading MLX. The next owner-approved
   factory run exercises these flags as part of its normal flow; any
   command-integration defect found then gets its own focused issue.
2. Run `scripts/sql/build_sql_spider_execution_gate.py` against a local Spider DB
   bundle and score the current routed candidate on execution accuracy.
3. Measure routed SQL latency, RAM/peak RSS, and tok/s
   (harness ready: `scripts/sql/measure_sql_routed_perf.py`).
4. ~~Run exactly one preference-tuning/output-hygiene candidate.~~ Done
   2026-07-04 — decision retry-training (see frozen-target outcome above).
5. ~~Report and decide package vs retry.~~ Done 2026-07-04 — schema-valid
   run + report in `runs/2026-07-03-sql-hygiene-dpo-qwen06/`; retry lane
   defined there.

Use `docs/prds/PRIORITY.md` only when a task needs PRD-level acceptance
criteria. Do not work from the full PRD list directly.

## Parked

These remain parked unless an explicitly reactivated factory run needs them:

- browser polish
- Astro migration
- public launch/HN prep
- ANE/CoreML research
- VLM porting
- Tier 5 research
- broad Mac app GUI polish
- new PRD expansion
