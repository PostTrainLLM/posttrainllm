# B1 SQL POC

Status: expanded 0.6B factory POC complete; next step is preference tuning or a public benchmark slice.

## Target

First factory POC: a narrow text-to-SQL specialist.

The goal is not to solve Spider yet. The goal is to prove the factory loop on a
small deterministic task:

```text
target -> data -> baseline eval -> candidate eval -> row failures -> report
```

## Frozen Fixture

Fixture files live in `evals/sql-poc/`:

- `company.sql` — SQLite schema and rows.
- `train.jsonl` — SFT-shape training examples.
- `dev.jsonl` — heldout questions and gold SQL.
- `baseline-preds.jsonl` — deliberately imperfect baseline predictions.
- `candidate-preds.jsonl` — deliberately improved candidate predictions.

Smoke:

```bash
bash evals/sql-poc-smoke.sh
```

Expected dry-run scores:

| Model | Execution accuracy | Exact match | Rows |
|---|---:|---:|---:|
| Baseline fixture | 0.667 | 0.167 | 6 |
| Candidate fixture | 0.833 | 0.833 | 6 |

The smoke also checks row-level failure logging from `posttrainllm eval-sql --out`.

## Live POC Steps

1. Generate SQL from the base model on `evals/sql-poc/dev.jsonl`.
2. Score it with `posttrainllm eval-sql`.
3. Train the cheapest LoRA SFT candidate on `evals/sql-poc/train.jsonl`.
4. Generate SQL from base+adapter on the same frozen dev set.
5. Score candidate output with `posttrainllm eval-sql`.
6. Render a `runs/<date>-sql-poc/` folder with baseline, candidate, row traces,
   report, and decision.

## First Live POC Result

Run folder: `runs/2026-07-02-sql-poc-qwen06/` (local, gitignored).

Model:

- Base: `Qwen/Qwen3-0.6B`
- Candidate: DoRA/LoRA rank 4 adapter
- Training: 12 schema-aware prompt rows, plain template, 80 steps, batch 1

Result:

| Model | Execution accuracy | Exact match | Rows |
|---|---:|---:|---:|
| Qwen3-0.6B baseline | 0.167 | 0.000 | 6 |
| Qwen3-0.6B + SQL adapter | 0.833 | 0.833 | 6 |

Decision: `retry-data`.

Why: the run proves the factory mechanics and shows the 0.6B can be bent toward
SQL output quickly, but the toy fixture has train/eval overlap and the model
still sometimes emits prose around correct SQL. The next run needs
non-overlapping data and preference examples for SQL-only completions.

Operational note: the `metal` build blocker was CLT selection, not missing
Xcode. Use:

```bash
DEVELOPER_DIR=/Applications/Xcode-27.0.0-Beta.app/Contents/Developer \
  swift build --build-system native --product posttrainllm
```

## Expanded POC Result

Run folder: `runs/2026-07-02-sql-expanded-qwen06/` (local, gitignored).

Dataset:

- `evals/sql-poc-expanded/train.jsonl` — 108 non-overlapping train rows.
- `evals/sql-poc-expanded/dev.jsonl` — 50 heldout rows.
- `evals/sql-poc-expanded/preferences.jsonl` — 108 SQL-only preference pairs.
- Five SQLite domains: company, retail, library, school, clinic.

Result:

| Model | Execution accuracy | Exact match | Rows |
|---|---:|---:|---:|
| Qwen3-0.6B baseline | 0.160 | 0.140 | 50 |
| Qwen3-0.6B + expanded SQL adapter | 0.860 | 0.840 | 50 |

Failure taxonomy after SFT:

| Failure type | Count |
|---|---:|
| `sql_wrong_schema` | 3 |
| `sql_unneeded_join` | 2 |
| `sql_wrong_filter` | 1 |
| `sql_no_select` | 1 |

Generated follow-up data:

- `runs/2026-07-02-sql-expanded-qwen06/failure-labels.jsonl`
- `runs/2026-07-02-sql-expanded-qwen06/failure-preferences.jsonl`

Decision: `retry-data`. The loop works, but this is still synthetic fixture
data and has no breadth regression suite.

## Public Benchmark Probe

Run folder: `runs/2026-07-02-sql-public-bmc2/` (local, gitignored).

Public source:

- `b-mc2/sql-create-context` on Hugging Face.
- Slice: 24 single-table SELECT rows from `train[:2000]`.
- Builder: `scripts/build_sql_public_benchmark.py`.
- Scorer: `scripts/score_sql_public_exact.py`.

Metric: normalized exact SQL match. This is not execution accuracy because the
HF dataset ships `CREATE TABLE` context and gold SQL, not populated SQLite DBs.

| Model | Exact match | Rows |
|---|---:|---:|
| Qwen3-0.6B baseline | 0.042 | 24 |
| Qwen3-0.6B + expanded SQL adapter | 0.333 | 24 |
| `cssupport/t5-small-awesome-text-to-sql` | 0.458 | 24 |

Readout:

- The adapter does transfer beyond the synthetic domains: +29.1pp over base on a
  public schema-grounded slice.
- A tiny specialized public model still wins this narrow exact-match probe,
  which is useful pressure: the next local adapter needs more public-style data
  and fewer spurious joins.
- This does not replace Spider/BIRD execution benchmarking. It is a cheap
  public sanity check that can run before downloading full benchmark DB bundles.

HF specialized model scan:

| Candidate | Size / shape | Practical note |
|---|---:|---|
| `cssupport/t5-small-awesome-text-to-sql` | ~242 MB, T5 seq2seq | Small, public, strong cheap baseline; not posttrainllm-runtime compatible. |
| `prem-research/prem-1B-SQL` | ~1.35B params, Llama-family | Best next sub-4B SQL specialist to inspect/load; full download is multi-GB. |
| `Ellbendls/Qwen-2.5-3b-Text_to_SQL` | ~3.1B params, Qwen2 | Relevant under the "smaller than 4B" constraint, but still a larger candidate. |
| `defog/sqlcoder-7b-2` | ~6.7B params | Strong known specialist, but above the current smallest-model target. |

## Beat-The-Small-Baseline Plan

Immediate target: beat `cssupport/t5-small-awesome-text-to-sql` on a
non-overlapping public-style slice before moving to Spider execution.

Prepared data:

- `evals/sql-public-bmc2-train/train.jsonl` — 512 SFT rows from
  `b-mc2/sql-create-context`, starting at source index 2000.
- `evals/sql-public-bmc2-train/dev.jsonl` — 64 heldout rows from source index 0.
- `evals/sql-public-bmc2-train/preferences.jsonl` — 512 SQL-only preference
  pairs for a later DPO/RFT step.
- Builder: `scripts/build_sql_public_training.py`.
- Smoke: `evals/sql-public-training-smoke.sh`.

Curriculum mix:

| Bucket | Train rows | Dev rows |
|---|---:|---:|
| aggregate | 77 | 10 |
| filter | 90 | 12 |
| group/having | 71 | 7 |
| join | 203 | 23 |
| order/limit | 46 | 10 |
| projection | 25 | 2 |

Next run:

```bash
native-mac/.build/debug/posttrainllm sft \
  ~/.cache/huggingface/hub/models--Qwen--Qwen3-0.6B/snapshots/c1899de289a04d12100db370d81485cdf75e47ca \
  --data evals/sql-public-bmc2-train/train.jsonl \
  --template plain \
  --out runs/2026-07-02-sql-public-bmc2/qwen06-public-bmc2.lora \
  --rank 8 \
  --alpha 16 \
  --steps 300 \
  --batch 1 \
  --max-seq 512 \
  --metal-cache-gb 8 \
  --throttle 0.5
```

Measured external baseline:

| Model | Exact match | Rows |
|---|---:|---:|
| `cssupport/t5-small-awesome-text-to-sql` | 0.484 | 64 |

Gate:

- Beat T5-small public baseline: exact match > 0.484 on the 64-row public dev.
- Also rerun the synthetic 50-row execution fixture to catch regressions.
- If it fails, classify misses into the same failure taxonomy and generate the
  next 512 targeted rows.

## Beat-The-Small-Baseline Result

Run folder: `runs/2026-07-02-sql-public-bmc2/` (local, gitignored).

Fixed public dev: `evals/sql-public-bmc2-train-v2/dev.jsonl`, 64 rows from
`b-mc2/sql-create-context`.

| Attempt | Data / recipe | Public exact | Rows |
|---|---|---:|---:|
| `cssupport/t5-small-awesome-text-to-sql` | external specialized T5-small | 0.484 | 64 |
| v1 | 512 rows, source index >= 2000, rank 8, 300 steps, lr 1e-3 | 0.344 | 64 |
| v2 | 2048 rows, source index >= 64, rank 16, 1200 steps, lr 1e-3 | 0.031 | 64 |
| v3 | 2048 rows, source index >= 64, rank 8, 600 steps, lr 5e-4 | 0.422 | 64 |
| v4 | join/group weighted rows, rank 8, 700 steps, lr 5e-4 | **0.531** | 64 |

v4 curriculum readout:

| Bucket | v4 exact | T5-small exact |
|---|---:|---:|
| aggregate | 6/10 | 7/10 |
| filter | 7/12 | 6/12 |
| group/having | 6/7 | 5/7 |
| join | 3/23 | 5/23 |
| order/limit | 10/10 | 7/10 |
| projection | 2/2 | 1/2 |

Result: v4 beats the small public specialist on the fixed public exact gate
(34/64 vs 31/64), but it is **not shippable** as the SQL specialist.

Regression check:

| Model | Synthetic execution | Synthetic exact | Rows |
|---|---:|---:|---:|
| original expanded SQL adapter | 0.860 | 0.840 | 50 |
| public v4 adapter | 0.240 | 0.220 | 50 |

Failure taxonomy on the synthetic regression:

| Failure type | Count |
|---|---:|
| `sql_wrong_schema` | 19 |
| `sql_wrong_filter` | 10 |
| `sql_unneeded_join` | 9 |

Generated follow-up data:

- `runs/2026-07-02-sql-public-bmc2/qwen06-v4-synthetic50-failure-labels.jsonl`
- `runs/2026-07-02-sql-public-bmc2/qwen06-v4-synthetic50-failure-preferences.jsonl`
- `runs/2026-07-02-sql-public-bmc2/qwen06-v4-synthetic50-failure-summary.json`

Decision: `continue-training`, not `ship`. We proved the data loop can beat the
small external baseline on the public exact slice, but the adapter learned a
public Spider/WikiSQL style that over-joins and hallucinates schema links on the
synthetic execution fixture. The next loop should blend public weighted rows
with the synthetic execution rows, or train/merge separate public and synthetic
adapters, then require both gates to pass.

## Blend Experiment

Question: can a single 0.6B adapter hold both the public exact-match style and
the local synthetic execution style?

Blend data:

- Builder: `scripts/build_sql_blend_training.py`.
- Dataset: `evals/sql-blend-public-synthetic-v1/train.jsonl`.
- Public source: `evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl`
  repeated 1x.
- Synthetic source: `evals/sql-poc-expanded/train.jsonl` repeated 30x.
- Total: 8,807 SFT rows; 5,567 public, 3,240 synthetic.

Run:

- Adapter: `runs/2026-07-02-sql-public-bmc2/qwen06-sql-blend-v1.lora`
- Recipe: rank 8 DoRA, alpha 16, lr 5e-4, 800 steps, batch 1.

Result:

| Model | Public exact | Synthetic execution | Synthetic exact |
|---|---:|---:|---:|
| public v4 adapter | 0.531 | 0.240 | 0.220 |
| original synthetic adapter | not measured on 64-row public gate | 0.860 | 0.840 |
| blended v1 adapter | 0.297 | 0.560 | 0.520 |

Blend failure taxonomy on synthetic regression:

| Failure type | Count |
|---|---:|
| `sql_no_select` | 17 |
| `sql_prose_wrapped` | 3 |
| `sql_wrong_filter` | 2 |

Decision: `route-or-compose`. Naive mixture SFT partially recovers synthetic
execution but destroys the public exact gate, and its failure mode changes from
schema over-joining to not reliably emitting clean SQL. This is interference,
not just a weighting issue. The next push should keep the public and synthetic
adapters separate and test adapter merge or routing:

- **Route:** detect schema style / benchmark family, then pick public-v4 or
  synthetic-expanded adapter.
- **Merge:** combine same-base adapters with a small alpha sweep and score both
  gates.
- **Repair:** use the blend failures only as preference/retry data after a
  composition baseline exists.

## Adapter Composition Sweep

Implementation: `posttrainllm serve` and `posttrainllm generate` now accept repeatable
`--lora` plus `--lora-weight`, using the existing HF multi-LoRA stack injection.

Adapters:

- Public: `runs/2026-07-02-sql-public-bmc2/qwen06-public-bmc2-v4-joinweighted.lora`
- Synthetic: `runs/2026-07-02-sql-expanded-qwen06/qwen06-sql-expanded.lora`

Proxy sweep: 20 public rows + 20 synthetic rows.

| Public weight | Synthetic weight | Public exact | Synthetic exec | Synthetic exact |
|---:|---:|---:|---:|---:|
| 1.0 | 0.25 | 0.550 | 0.250 | 0.200 |
| 1.0 | 0.50 | 0.550 | 0.500 | 0.400 |
| 1.0 | 0.75 | 0.550 | 0.700 | 0.500 |
| 0.75 | 1.0 | 0.550 | 0.800 | 0.550 |
| 0.50 | 1.0 | 0.500 | 0.800 | 0.750 |

Full-gate checks:

| Public weight | Synthetic weight | Public exact | Synthetic exec | Synthetic exact | Decision |
|---:|---:|---:|---:|---:|---|
| 1.0 | 0.50 | 0.516 | 0.460 | 0.320 | public pass, synthetic fail |
| 1.0 | 0.75 | 0.469 | 0.640 | 0.360 | public fail, synthetic partial |
| 0.75 | 1.0 | 0.453 | 0.780 | 0.500 | public fail, synthetic partial |

Decision: `route`, not `compose`. Static adapter composition creates a smooth
tradeoff but no tested weight passes both gates. The right next attempt is a
router that chooses the public adapter for public Spider/WikiSQL-style schemas
and the synthetic adapter for local execution schemas, then reports routed
aggregate accuracy. This matches the empirical shape: each adapter is competent
in its own distribution, and mixing them blurs both.

## Routed Adapter Result

Implementation: `scripts/run_sql_routed_generate.py` routes each row to one
specialist adapter and recombines predictions in original order.

Route classifier:

- `db` field -> synthetic expanded adapter.
- `source=b-mc2/sql-create-context` -> public v4 adapter.
- `CREATE TABLE` schema without `db` -> public v4 adapter.
- compact local schema prompt with domain/question/gold -> synthetic adapter.

The old `route` field is now optional and only used with
`--trust-route-field`. The default classifier is label-free and emits
`_route`, `_route_reason`, and `_route_confidence` metadata.

Eval set:

- `evals/sql-routed-mixed-v1/public64.jsonl`
- `evals/sql-routed-mixed-v1/synthetic50.jsonl`
- `evals/sql-routed-mixed-v1/mixed114.jsonl`
- Router smoke: `bash evals/sql-routed-router-smoke.sh`

Result:

| Strategy | Public exact | Synthetic execution | Synthetic exact |
|---|---:|---:|---:|
| public v4 only | 0.531 | 0.240 | 0.220 |
| synthetic expanded only | not measured on 64-row public gate | 0.860 | 0.840 |
| blend v1 | 0.297 | 0.560 | 0.520 |
| best static composition tested | 0.516 | 0.460 | 0.320 |
| routed adapters | **0.531** | **0.860** | **0.840** |

Classifier rerun artifacts:

- `runs/2026-07-02-sql-routing/routed-mixed114-classifier-routes.jsonl`
- `runs/2026-07-02-sql-routing/routed-mixed114-classifier-preds.jsonl`
- `runs/2026-07-02-sql-routing/routed-public64-classifier-rows.jsonl`
- `runs/2026-07-02-sql-routing/routed-synthetic50-classifier-rows.jsonl`

Decision: `current-best-routed-artifact`. This is the first setup that passes
both current SQL gates, and it no longer depends on hand-authored route labels.
The next real benchmark step is to run BIRD Mini-Dev SQLite or Spider execution
fixtures once their DB bundles are local.

Public execution gate scaffolding:

- Builder: `scripts/build_sql_spider_execution_gate.py`.
- Smoke: `evals/sql-spider-execution-smoke.sh`.
- Input shape: local Spider bundle with `dev.json` and
  `database/<db_id>/<db_id>.sqlite`.
- Output: `dev.jsonl` rows compatible with `posttrainllm eval-sql --db-dir
  <spider-root>` after generation adds `predicted_sql`.

## BIRD-Augmented Public v5 Attempt

Question: can broader schema-rich public SQL data improve the public adapter's
hard join/generalization misses without collapsing the current b-mc2 gate?

Data:

- Builder: `scripts/build_sql_bird_public_training.py`.
- Dataset: `evals/sql-public-bird-bmc2-v5/train.jsonl`.
- Sources:
  - 4,096 rows from `evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl`.
  - 4,096 weighted SELECT-only rows from `xu3kev/BIRD-SQL-data-train`.
- Curriculum: 5,715 join rows, 906 group/having rows, 888 aggregate rows, plus
  smaller filter/order/projection/subquery coverage.

Run:

- Adapter: `runs/2026-07-02-sql-public-bmc2/qwen06-public-bird-bmc2-v5.lora`
- Recipe: rank 8 DoRA, alpha 16, lr 3e-4, 600 steps, max-seq 768.

Result:

| Model | Public exact | Synthetic execution | Synthetic exact |
|---|---:|---:|---:|
| public v4 adapter | **0.531** | 0.240 | 0.220 |
| BIRD+b-mc2 public v5 adapter | 0.438 | 0.280 | 0.320 |

Synthetic failure taxonomy for v5:

| Failure type | Count |
|---|---:|
| `sql_wrong_filter` | 13 |
| `sql_wrong_schema` | 10 |
| `sql_no_select` | 7 |
| `sql_unneeded_join` | 4 |
| `sql_missing_join` | 2 |

Decision: `reject-v5`. Broad BIRD augmentation was useful as a benchmark/data
probe, but it hurt the fixed b-mc2 public gate and did not recover synthetic
execution. The next push should avoid another broad SFT mixture. Better options:

- keep routed v4+synthetic as the current best artifact;
- add a schema/eval-family router smoke so routing is reproducible without
  hand labels;
- use BIRD Mini-Dev SQLite only after the DB package is local, so BIRD is an
  execution gate rather than noisy broad SFT data;
- target public join misses with narrower b-mc2-style hard negatives rather
  than mixing a different benchmark distribution into the public adapter.

## Gate

For the POC:

- Primary score: execution accuracy.
- Improvement threshold: candidate >= baseline + 3pp.
- Failure trace requirement: every failed row must include predicted SQL, gold
  SQL, exact/exec pass flags, and SQLite error/result mismatch details.

For a real B1 ship gate, move from this toy fixture to Spider or another
public text-to-SQL benchmark and keep the same factory artifact shape.
