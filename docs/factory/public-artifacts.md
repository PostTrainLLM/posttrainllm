# Public Artifacts

Public artifacts are first-class factory outputs. They are different from local
run files: a public artifact should be understandable outside this repo, have a
small committed metadata surface, and list its blockers as clearly as its wins.

Website surface: `/artifacts`. The website should behave like a built-in blog
for artifacts: one index page for scanning, one detail page per artifact, and
numbers/blockers/evidence on every page.

## Release Rule

Every public artifact entry must include:

- artifact id and type
- current status
- what can be published now
- measured evidence
- competitive context
- blockers
- next release action

Weights, adapters, and large run outputs do not need to live in git, but the
public artifact must explain where they came from, how they were evaluated, and
why it is or is not ready to package.

Where an artifact has a compiled [Fine-Tune Report Card](report-card.md), that
card is the canonical before/after proof surface: it carries the numbers, their
measurement states, and the verification blockers. This registry entry stays the
release-state record. A report card never changes release policy — the `State`
column below still governs what may be released. Published cards and what the
dogfood review found: [`report-card-cohort.md`](report-card-cohort.md).

Public artifact storage target: Hugging Face Hub. Use Cloudflare R2 only as an
optional private cache or legacy mirror. See
`docs/factory/huggingface-artifact-storage.md`.

Competition rows must be labeled as:

| Label | Meaning |
|---|---|
| `Direct` | Same fixture, prompt/eval setup, metric, and scorer. |
| `Directional` | Useful market or method context, but not the same eval. |
| `Not comparable` | Public high bar or adjacent system that explains the target lane but cannot be claimed as a win/loss. |

Public copy should prefer "we beat X on this exact local gate" only for
`Direct` rows. Everything else is context until the same benchmark is run.

Hugging Face's public request counter is not an adoption metric. It is not
deduplicated into known people and does not prove a full weight download,
successful load, or useful run. Case studies may link the public repository but
must not turn its request count into a user claim.

## Artifact States

| State | Meaning |
|---|---|
| `release-ready-metadata` | Small committed metadata exists; large weights may still be external. |
| `release-ready-weights` | Metadata and model weights are public on the artifact store. |
| `candidate-current-best` | Best measured candidate, but not yet a shipped specialist package. |
| `report-only` | Good public write-up/repro artifact, but no model should be used directly. |
| `blocked` | Needs a named unblocker before public release work continues. |
| `parked` | Real artifact, but not active in the factory sequence. |

## Current Public Artifact List

| Artifact | Type | State | Public value | Next release action |
|---|---|---|---|---|
| `offhours-context-interference` | Agent-behaviour benchmark | `report-only` | Separates unresolved personal context from matched interruptions and raw volume. Devin showed no mental-toll penalty; the first repeatable failure occurred in the neutral arm at 8,000 submitted words/day. | Freeze the Devin result and run the unchanged protocol against local Qwen with exact prompt-token and model provenance. |
| `pace-intent-router-v8` | From-scratch intent classifier | `release-ready-weights` | Shows why sealed distribution gates matter: 95.5% source-matched synthetic accuracy fell to 57.1% on sealed V1, despite 3.8ms mean latency. | Keep as the latency floor and generator-overfit case; train only on public failure themes and judge a successor on a new sealed V2. |
| `qwen3-4b-file-ops-distilled` | Specialist package | `release-ready-weights` | Shows a real posttrainllm-built routed specialist: 58% -> 100% on file-ops hard gate, with breadth regression disclosed. | Keep routed-only warnings prominent; add a loader/pull smoke when wiring consumers. |
| `qwen3-4b-rest-fused` | Research specialist package | `release-ready-weights` | Teacher-free ReST preserved 100% file-ops depth and recovered breadth to 65% vs stock 59.6%. | Keep research-only; run a fresh product-specific gate before any runtime wiring. |
| `qwen3-4b-multibackend-distilled` | Rejected specialist weights | `report-only` | Preserves the failed negative-transfer result: 100% file-ops depth with breadth collapsed to 31%. | Keep as a failed comparison artifact; do not promote without a new breadth-preserving recipe. |
| `vibethinker-3b-mlx` | MLX conversion | `report-only` | Makes the upstream VibeThinker-3B reasoning model available as a public Mac-local conversion; historical GSM8K sanity slice was 40/40. | Add a pinned loader and conversion-parity receipt only if a real consumer adopts it. |
| `vibethinker-3b-agentic-distilled` | Unqualified distilled weights | `blocked` | Preserves an agentic distillation checkpoint while making the missing before/after eval explicit. | Run a frozen baseline/candidate agentic and reasoning-regression gate before any promotion. |
| `hf-specialist-model-archive-v1` | Model archive index | `report-only` | Links every unique local specialist/conversion artifact moved to Hugging Face, and records which plain upstream caches were deleted. | Use as the storage index; promote individual models only after eval/report/package evidence exists. |
| `qwen06-sql-routed-v1` | Routed SQL specialist POC | `report-ready-candidate` | Shows the factory/router pattern on SQL: public exact 0.531 and synthetic execution 0.860 using separate routed adapters. | Publish as report-only; package only after a public execution benchmark gate exists. |
| `factory-run-schema-v1` | Process artifact | `report-only` | Explains the repeatable `target -> data -> post-training -> eval -> package -> report` contract. | Use the SQL routed rendered run as the canonical example. |
| `browser-playground` | Demo artifact | `parked` | Public proof of the earlier browser/WASM/WebGPU learning track. | Keep parked unless it directly presents factory reports or artifacts. |

## Artifact Details

### `offhours-context-interference`

Status: `report-only`; experiment decision: `semantic-tension-null`

OffHours tests whether routine office-work quality changes when unresolved family
tension remains in an AI employee's context. The paired Devin study kept the
employee, work claims, event positions, response structure, and semantic payload
volume fixed. Clean qualification scored 198/200 decisions (99.0%) with 200/200
valid JSON outputs. Across 20%, 50%, and 80% narrative occupancy, unresolved
context did not reduce accuracy relative to matched resolved context.

The separate exact-word ladder found a reproducible operational boundary at
2,000 neutral words per event, or 8,000 submitted words across four workday
interruptions. The neutral arm scored 39/40 on both day 2 and its preregistered
day-3 adjudication, below the 98% per-day gate. This is evidence of raw-volume or
regular Devin context-management cost, not a family-obligation effect.

Public page: `/artifacts/offhours-context-interference`

Committed evidence:

- `evals/offhours/results/devin-context-saturation-2026-08-21-report.md`
- `evals/offhours/results/devin-context-saturation-2026-08-21.json`
- `evals/offhours/results/devin-glm52-semantic-occupancy-2026-08-21.html`
- `evals/offhours/README.md`

Release limitations:

| Limitation | Why it matters | Next action |
|---|---|---|
| No semantic mental-toll effect detected | The matched unresolved treatments did not degrade work quality. | Report the null; do not optimize treatment wording after seeing the result. |
| Devin raw-model provenance is incomplete | The regular workflow did not expose prompt-token counts, quantization, or a model-file hash. | Run the frozen protocol on local Qwen with complete provenance. |
| Saturation appeared in neutral context | The repeated boundary cannot be attributed to personal obligation. | Treat it as operational context-volume evidence unless a future matched design isolates another mechanism. |

### `pace-intent-router-v8`

Status: `release-ready-weights`; production decision: `reject-production-winner`

Committed surface:

- `specialists/pace-intent-router-v8/model_card.md`
- `specialists/pace-intent-router-v8/eval_report.json`
- `specialists/pace-intent-router-v8/tinygpt.lock.json`
- `specialists/pace-intent-router-v8/prompt.md`
- `specialists/registry.json`
- HF repo: `https://huggingface.co/posttrainllm/pace-intent-router-v8`

Measured evidence:

| Gate | Pace v8 | Qwen3 4B | Apple FM | Frontier |
|---|---:|---:|---:|---:|
| Source-matched synthetic holdout | 95.5% | not run | 76.5% on a separate 200-row source-matched slice | not run |
| Sealed V1 exact accuracy | 57.1% | 93.7% | 92.1% | 100% |
| Sealed V1 unknown recall | 55.6% | 77.8% | 77.8% | 100% |
| Mean warm latency | 3.8ms | 211ms | 522ms | batch timing not comparable |

The 63-instance sealed set was run twice per entry, passed the frontier-ceiling
gate, and had zero normalized exact overlap with the recorded training and
held-out corpora. The earlier 95.5% result remains valid only for the
source-matched generator distribution. It is not the production result.

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Fresh-distribution generalization failed | The source-matched score overstated readiness by 38.4 points. | Generate public development rows from failure themes, never sealed prompts. |
| Rejected as production winner | Both local generalists exceeded 92% on the same sealed ruler. | Require a successor to pass a newly generated sealed V2 before promotion. |

### `qwen3-4b-file-ops-distilled`

Status: `release-ready-weights`

Report card: `/report-cards/qwen3-4b-file-ops-distilled` — outcome
`routed-ship`, not fully verified (historical values; the breadth gate is derived
as failing).

Committed surface:

- `specialists/qwen3-4b-file-ops-distilled/model_card.md`
- `specialists/qwen3-4b-file-ops-distilled/eval_report.json`
- `specialists/qwen3-4b-file-ops-distilled/tinygpt.lock.json`
- `specialists/qwen3-4b-file-ops-distilled/prompt.md`
- `specialists/registry.json`
- HF repo: `https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled`
- HF staging command:
  `python3 scripts/plan_hf_artifact_upload.py specialists/qwen3-4b-file-ops-distilled --repo-id posttrainllm/qwen3-4b-file-ops-distilled`

Measured evidence:

| Gate | Stock | Specialist |
|---|---:|---:|
| File-ops hard gate | 0.58 | 1.00 |
| File-ops hardgen heldout | - | 0.95 |
| Out-of-domain breadth | 0.596 | 0.423 |

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Breadth regression is real | The model is unsafe as a general planner. | Keep routed-only positioning in all public copy. |
| Frontier/breadth caveat remains | The breadth suite is directly comparable but not fully frontier-validated. | Keep caveat in model card; do not oversell as general capability. |

### `qwen3-4b-rest-fused`

Status: `release-ready-weights`

Report card: `/report-cards/qwen3-4b-rest-fused` — outcome `routed-ship`,
not fully verified (historical values; latency, RAM, throughput, and timing are
reported as not recorded).

Committed surface:

- `specialists/qwen3-4b-rest-fused/model_card.md`
- `specialists/qwen3-4b-rest-fused/eval_report.json`
- `specialists/qwen3-4b-rest-fused/tinygpt.lock.json`
- `specialists/qwen3-4b-rest-fused/prompt.md`
- `specialists/registry.json`
- HF repo: `https://huggingface.co/posttrainllm/qwen3-4b-rest-fused`

Recorded evidence:

| Gate | Stock | ReST candidate |
|---|---:|---:|
| File-ops hard gate | 0.58 | 1.00 |
| Out-of-domain breadth | 0.596 | 0.65 |

Release decision: ship as a Mac-local research specialist package. Do not make
it the Pace default planner: Pace has a different intent envelope and ship
gate. The historical run did not preserve latency, RAM, tok/s, training time,
or raw predictions; the package reports those fields as unavailable rather
than estimating them.

### `qwen3-4b-multibackend-distilled`

Status: `report-only`; model decision: `reject`

HF repo: `https://huggingface.co/posttrainllm/qwen3-4b-multibackend-distilled`

Recorded evidence:

| Attempt | File-ops depth | Out-of-domain breadth | Decision |
|---|---:|---:|---|
| Stock Qwen3-4B | 58% | 59.6% | baseline |
| File-ops distillation | 100% | 42.3% | route only |
| Multibackend distillation | 100% | 31% | reject |
| Teacher-free ReST | 100% | 65% | research-only routed ship |

This is a negative-transfer case study. The additional multibackend teacher
data did not broaden the model; breadth fell another 11.3 points below the
already narrow file-ops distillation and 28.6 points below stock. The historical
result is exact in the attempt ledger, but raw predictions and a package-level
`eval_report.json` were not committed. Preserve the weights as failed evidence;
do not promote them.

### `vibethinker-3b-mlx`

Status: `report-only`; artifact decision: `conversion-only`

HF repo: `https://huggingface.co/posttrainllm/vibethinker-3b-mlx`

This is an MLX conversion of `WeiboAI/VibeThinker-3B`, not a model trained by
PostTrainLLM. A historical local GSM8K sanity screen scored 40/40, confirming a
useful reasoning signal on that small slice. No controlled upstream-vs-MLX
parity report was preserved, and the model has no validated native tool-calling
behavior. The case study therefore claims public Mac-local packaging, not a
quality improvement.

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Conversion parity not recorded | A 40-row sanity screen is not a numerical or broad benchmark parity proof. | Run paired upstream-vs-MLX checks only if a consumer adopts this artifact. |
| No native tool-calling gate | Reasoning strength does not make it a drop-in agent. | Treat it as a reasoning/runtime artifact until an adapted candidate clears an agentic gate. |

### `vibethinker-3b-agentic-distilled`

Status: `blocked`; model decision: `inconclusive`

HF repo: `https://huggingface.co/posttrainllm/vibethinker-3b-agentic-distilled`

The intended experiment was to distill agentic behavior into a reasoning-strong
3B base. The fused weights are public, but the repository does not preserve a
current matched baseline, candidate eval, reasoning/breadth regression result,
or ship decision. Public weights establish artifact existence, not success.

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Before/after agentic eval missing | There is no defensible tool-calling delta. | Freeze and run the same baseline/candidate gate before any new training. |
| Reasoning retention missing | Agentic adaptation may have damaged the base's reason for being. | Add a reasoning/breadth regression gate to the same evaluation. |
| No routing/package decision | There is no recorded safe-use envelope. | Package only after the frozen eval produces a ship, route, or reject decision. |

### `hf-specialist-model-archive-v1`

Status: `report-only`

Purpose: public storage index for model artifacts that were previously only
durable because they existed in the local Mac cache. Hugging Face is now the
public artifact store for unique posttrainllm weights and conversions; plain upstream
base-model caches should be deleted locally instead of re-uploaded under
posttrainllm.

Uploaded posttrainllm artifacts:

| Local cache | HF repo | Status | Evidence / readout |
|---|---|---|---|
| `pace-intent-router-v8` | `https://huggingface.co/posttrainllm/pace-intent-router-v8` | Public weights / rejected production winner | 57.1% sealed V1 accuracy at 3.8ms mean; the earlier 95.5% source-matched result did not generalize. |
| `mt4b_fused` | `https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled` | Release-ready specialist | File-ops hard gate 58% -> 100%; breadth regression disclosed. |
| `mt4b_rest_fused` | `https://huggingface.co/posttrainllm/qwen3-4b-rest-fused` | Release-ready research specialist | ReST breadth recovery variant: depth 100%, breadth 65% vs stock breadth 59.6%; missing historical performance evidence disclosed. |
| `mt4b_mb_fused` | `https://huggingface.co/posttrainllm/qwen3-4b-multibackend-distilled` | Archive / failed attempt | Negative-transfer artifact: depth 100%, breadth 31%. |
| `vibethinker-3b-mlx` | `https://huggingface.co/posttrainllm/vibethinker-3b-mlx` | Archive / conversion | Local MLX conversion of `WeiboAI/VibeThinker-3B`. |
| `vibe_distill_fused` | `https://huggingface.co/posttrainllm/vibethinker-3b-agentic-distilled` | Archive / needs eval promotion | posttrainllm distilled VibeThinker variant; do not treat as a shipped specialist until a current eval report exists. |

Deleted upstream caches:

| Local cache | Upstream repo | Reason |
|---|---|---|
| `mxbai-embed-large-v1` | `https://huggingface.co/mixedbread-ai/mxbai-embed-large-v1` | Public upstream model; no posttrainllm delta. |
| `qwen3-embedding-0.6b` | `https://huggingface.co/Qwen/Qwen3-Embedding-0.6B` | Public upstream model; no posttrainllm delta. |
| `qwen3-vl-2b-instruct` | `https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct` | Public upstream model; no posttrainllm delta. |

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Archive entries are not ship decisions | Public weights can be useful evidence without being selected for Pace or any product lane. | Promote only candidates with a current factory run, eval report, package metadata, and routed-use decision. |
| VibeThinker distilled eval needs promotion | The weights are preserved, but the public artifact should not imply a measured win yet. | Run the factory eval gate and publish a before/after report before using it as a specialist package. |

### `qwen06-sql-routed-v1`

Status: `report-ready-candidate`

Report card: `/report-cards/qwen06-sql-routed-v1` — outcome `report-only`
(`retry-eval`), measured baseline/candidate with three open blockers.

Current artifact shape:

- Public adapter:
  `runs/2026-07-02-sql-public-bmc2/qwen06-public-bmc2-v4-joinweighted.lora`
- Synthetic adapter:
  `runs/2026-07-02-sql-expanded-qwen06/qwen06-sql-expanded.lora`
- Router:
  `scripts/sql/run_sql_routed_generate.py`
- Router smoke:
  `evals/sql-routed-router-smoke.sh`
- Eval fixture:
  `evals/sql-routed-mixed-v1/`
- Report:
  `docs/specialists/b1-sql-poc.md`
- Canonical run renderer:
  `scripts/sql/render_sql_factory_run.py`
- Run smoke:
  `evals/sql-factory-run-smoke.sh`
- Public execution gate builder:
  `scripts/sql/build_sql_spider_execution_gate.py`
- Public execution gate smoke:
  `evals/sql-spider-execution-smoke.sh`

Measured evidence:

| Gate | Result |
|---|---:|
| Public b-mc2 exact, 64 rows | 0.531 |
| T5-small public baseline, same 64 rows | 0.484 |
| Synthetic SQLite execution, 50 rows | 0.860 |
| Synthetic SQLite exact, 50 rows | 0.840 |
| Label-free router smoke | 64 public / 50 synthetic, all high-confidence |

Competitive context:

| System | Metric | Score | Comparable? | Readout |
|---|---|---:|---|---|
| posttrainllm routed SQL v1 | b-mc2 exact / synthetic exec | 0.531 / 0.860 | Direct | Current local candidate. |
| T5-small local baseline | b-mc2 exact | 0.484 | Direct | Same 64-row public slice; posttrainllm is +4.7 points. |
| Defog SQLCoder-7B-2 | Defog SQL-Eval category scores | 77.1-96% | Directional | Strong public SQL specialist, but different benchmark and 7B size class. |
| Arctic-Text2SQL-R1-7B | BIRD execution accuracy | 68.47% | Not comparable | Public execution target class; posttrainllm needs BIRD/Spider execution before competing here. |
| Arctic-Text2SQL-R1-14B / 32B | BIRD execution accuracy | 70.04% / 71.83% | Not comparable | Current public high bar is execution accuracy, not exact string match. |

External source notes:

- `cssupport/t5-small-awesome-text-to-sql` is the direct local baseline model;
  the 0.484 score is our local rerun on the same 64-row b-mc2 slice.
- Defog SQLCoder-7B-2 reports category-level Defog SQL-Eval scores, not one
  aggregate score.
- Arctic-Text2SQL-R1 reports BIRD execution accuracy; use it as the public
  execution target lane, not as a direct comparison.
- BFCL-V4 market rows on the website use the LLM Stats July 2026 snapshot only
  as directional context because that page marks the rows as self-reported and
  unverified. The official BFCL page remains the methodology/source-of-truth
  benchmark reference.

Rejected alternatives:

| Attempt | Public exact | Synthetic execution | Decision |
|---|---:|---:|---|
| Single public v4 adapter | 0.531 | 0.240 | route required |
| Blended SFT v1 | 0.297 | 0.560 | reject |
| Best static LoRA composition tested | 0.516 | 0.460 | reject |
| BIRD+b-mc2 v5 | 0.438 | 0.280 | reject |

Release blockers:

| Blocker | Why it matters | Unblock action |
|---|---|---|
| Public execution benchmark missing | b-mc2 exact match is useful but not enough for a serious SQL model claim. | Add BIRD Mini-Dev SQLite or Spider SQLite execution gate once DBs are local. |
| Not packaged under `specialists/` | Current adapter paths are local `runs/` outputs, not package metadata. | Create a package only after `decision.json` is `ship`; until then publish as report-only/candidate. |
| Output hygiene is weak | Scorers extract the first `SELECT`; many completions still include prose after the query. | Clean-SQL metric exists (`scripts/sql/score_sql_clean_output.py`); first hygiene candidate (ref-free SimPO) collapsed and was decided retry-training (`runs/2026-07-03-sql-hygiene-dpo-qwen06/`). Retry with reference-anchored DPO. |
| Performance numbers missing | Public artifact should report latency, RAM, tok/s, and eval time. | Run `scripts/sql/measure_sql_routed_perf.py` on the routed setup (offline smoke: `evals/sql-perf-smoke.sh`) and paste the report. |
| Data provenance needs public copy | b-mc2 and BIRD-derived rows have different licenses/provenance surfaces. | Add dataset license/provenance notes to the public report. |

Next release action:

Publish `qwen06-sql-routed-v1` as a **public report artifact**, not a shipped
specialist package. The report should say: targeted 0.6B SQL adapter beats a
small T5 baseline on the frozen public exact slice, but the robust artifact is a
router over two specialists, and public execution benchmarking is the next gate.

Canonical local render:

```bash
python3 scripts/sql/render_sql_factory_run.py --out runs/2026-07-02-sql-routed-qwen06-v1
```

Spider execution gate once a local Spider bundle exists:

```bash
python3 scripts/sql/build_sql_spider_execution_gate.py \
  --spider-root /path/to/spider \
  --out evals/sql-spider-execution
```

Website page: `/artifacts/qwen06-sql-routed-v1`

## Release Priority

1. `qwen06-sql-routed-v1` report artifact: best current story for the factory
   thesis because it includes failed attempts, routing, blockers, and measured
   improvement.
2. `qwen3-4b-file-ops-distilled` weights artifact: strongest model win, but
   weight distribution and routed-only caveats must be handled carefully.
3. `hf-specialist-model-archive-v1`: keep public links to preserved weights and
   failed variants without over-promoting them as product models.
4. `factory-run-schema-v1`: publish as process proof using the SQL routed
   rendered run as the canonical example.
5. `browser-playground`: leave parked unless it becomes a report browser.
