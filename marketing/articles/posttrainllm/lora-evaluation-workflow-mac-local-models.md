# A Practical LoRA Evaluation Workflow for Mac-Local Models

**Slug:** `lora-evaluation-workflow-mac-local-models`
**Target Query:** lora evaluation workflow mac local models
**Search Intent:** Informational / Practical Developer Guide. AI developers and engineers fine-tuning local models on macOS seeking a rigorous evaluation harness, benchmark calibration, regression gates, and report card protocols for LoRA adapters.
**Meta Title:** LoRA Evaluation Workflow for Mac-Local LLMs: A Practical Guide
**Meta Description:** Learn how to evaluate Mac-local LoRA adapters using frozen baselines, frontier calibration, AST matching, regression gates, and automated report cards.

---

## Outline

1. **Introduction: The Evaluation Deficit in Local Fine-Tuning**
   - The trap of relying on training loss curves.
   - Why local model evaluation requires strict baseline freezing and task-based gates.
2. **Evaluation Philosophy: Frontier Models as Calibration Anchors**
   - The frontier-ceiling gate: why a frontier model must score ~100% on a benchmark before using it as a ruler.
   - Unmasking benchmark traps: exact string matching vs. groundable AST evaluation (BFCL vs. hermes-fc).
3. **The Two-Dimensional Evaluation Framework: Depth vs. Breadth**
   - Targeted task depth: measuring specialized capability improvements.
   - Out-of-domain breadth regression: detecting catastrophic interference and negative transfer.
4. **Step-by-Step LoRA Evaluation Workflow**
   - Step 1: Baseline re-stamping and environment pinning.
   - Step 2: Executing deterministic evaluation gates (`eval-gate` and `eval-sql`).
   - Step 3: Extracting slice metrics and trace reviews.
   - Step 4: Compiling immutable fine-tune report cards (`report-card.json`).
5. **Real Local Case Studies: Evaluation Dispositions**
   - Case study 1: `qwen3-4b-file-ops-distilled` (Depth 100%, Breadth 42.3% -> `routed-ship`).
   - Case study 2: `qwen3-4b-rest-fused` (Depth 12/12, Breadth 25/45 -> `routed-ship` retained, rejected as general successor).
   - Case study 3: `qwen06-sql-hygiene-dpo-v1` (SimPO collapse vs. DPO ref-anchored -> `retry-data`).
6. **Decision Authority and Release Governance**
   - Distinguishing explicit terminal decisions: `ship`, `routed-ship`, `retry-data`, `reject`.
7. **Conclusion & Practical Implementation Checklist**

---

## Article Content

### Introduction: The Evaluation Deficit in Local Fine-Tuning

In local machine learning development on Apple Silicon, training a Low-Rank Adaptation (LoRA) adapter is often the easiest part of the pipeline. Tools like MLX and PyTorch MPS make it straightforward to run Supervised Fine-Tuning (SFT) or Direct Preference Optimization (DPO) on small base models. The true bottleneck is evaluation: knowing whether a fine-tuned adapter actually improved task capability, created subtle regressions, or simply memorized the training set.

Relying on training loss curves is a common pitfall. A LoRA adapter can achieve a low training loss (e.g., 0.001) while completely collapsing on out-of-domain tasks, unhandled edge cases, or format constraints. A practical evaluation workflow for Mac-local models requires frozen baselines, frontier-calibrated benchmark gates, automated regression checks, and explicit decision boundaries.

When structuring evaluation documentation, it is critical to maintain four distinct levels of detail:
- **General Guidance:** Conceptual principles of local model evaluation.
- **Recipe Contracts:** Frozen evaluation parameters, dataset versions, and decision thresholds.
- **Public Artifacts:** Verifiable report cards and benchmark trace JSONs.
- **Actual Runs:** Empirical outcomes, score deltas, and failure dispositions from real local evaluations.

---

### Evaluation Philosophy: Frontier Models as Calibration Anchors

An evaluation metric is only as good as the ruler used to measure it. When evaluating small Mac-local models (0.6B to 4B parameters), frontier models (such as Claude 3.5 Sonnet or GPT-4o / Codex) serve as the **calibration anchor** for every benchmark.

#### The Frontier-Ceiling Gate
Before any benchmark is used to grade local Mac models, a top-tier frontier model must score approximately **~100%** on it. If a frontier model cannot ace a benchmark, the benchmark itself is broken—containing ungroundable golds, ambiguous prompts, or broken exact-match constraints.

**Rule:** Never report local model accuracy on a benchmark that fails the frontier-ceiling gate.

```text
[ Proposed Benchmark ] ──> [ Run Frontier Model ] ──> Score < 95%? ──> [ FIX or DROP Benchmark ]
                                                 │
                                                 └── Score ~100% ──> [ APPROVED Benchmark Gate ]
```

#### Groundable AST Matching vs. Exact-String Traps
A concrete example of benchmark failure is the `hermes-fc` tool-calling dataset. When tested against frontier models, exact-match scoring produced a ~12% ceiling because ~29% of target gold answers contained ungroundable placeables (e.g., random transaction IDs, synthetic device IDs, or literal `"unique_nft_identifier"` placeholders missing from the prompt context). Frontier models generated valid, contextually grounded answers that were penalized by exact string matching. Consequently, `hermes-fc` was reclassified as training-only data and rejected as an evaluation metric.

In contrast, benchmarks like the Berkeley Function Calling Leaderboard (BFCL) rely on Abstract Syntax Tree (AST) matching, semantic argument verification, and groundable golds. Frontier models reach ~99% accuracy on BFCL multi-turn slices, making it a valid, calibrated gate for local model evaluation.

---

### The Two-Dimensional Evaluation Framework: Depth vs. Breadth

A single accuracy score is insufficient to evaluate a LoRA adapter. Small language models operating under tight parameter constraints frequently suffer from negative transfer or catastrophic forgetting. Evaluation must track two distinct dimensions:

```text
               ┌─────────────────────────────────────────────────┐
               │              Targeted Task Depth                │
               │   (e.g., File-Ops / SQL Execution Accuracy)    │
               └────────────────────────┬────────────────────────┘
                                        │
                                        ▼
               ┌─────────────────────────────────────────────────┐
               │           Out-of-Domain Breadth Gate            │
               │    (e.g., General Planning / Reason Slices)     │
               └─────────────────────────────────────────────────┘
```

1. **Targeted Task Depth:** Measures specific performance gains in the target domain (e.g., executing file management tool calls or generating executable SQLite queries).
2. **Out-of-Domain Breadth:** Measures potential degradation across general capabilities (e.g., multi-turn conversational planning or general reasoning).

An adapter that achieves 100% depth but degrades out-of-domain breadth by 20% cannot be released as a general model replacement; it must either be rejected or deployed as a **routed specialist**.

---

### Step-by-Step LoRA Evaluation Workflow

A reproducible evaluation pipeline on macOS follows four automated steps:

```text
[ 1. Re-Stamp Baseline ] ──> [ 2. Execute Eval Gates ] ──> [ 3. Extract Slices ] ──> [ 4. Build Report Card ]
```

#### Step 1: Baseline Re-Stamping and Environment Pinning
Before running evaluation on a newly trained adapter, re-evaluate the stock base model on the exact same hardware and harness version. Record the exact commit hash, MLX/PyTorch runtime version, seed, and temperature parameters.

#### Step 2: Executing Deterministic Evaluation Gates
Run target-specific evaluation scripts using native Mac tools:
- **`posttrainllm eval-gate`:** Executes standardized multi-turn tool-calling and planning suites.
- **`posttrainllm eval-sql`:** Executes generated SQL queries against isolated SQLite database instances (`.sqlite` files) to measure true execution accuracy rather than string exact-match.

#### Step 3: Extracting Slice Metrics and Trace Reviews
Generate granular slice metrics to identify where errors occur. For example, in SQL evaluation, categorize performance into single-table queries, multi-table joins, `GROUP BY` aggregations, and output format hygiene (detecting unwanted prose wrappers around raw SQL).

#### Step 4: Compiling Immutable Fine-Tune Report Cards
Compile all evaluation artifacts into a versioned, portable JSON record (`report-card.json`) and static HTML summary page using automated scripts (`scripts/factory/build_fine_tune_report_card.py`).

Every field in the report card carries an explicit measurement state (`measured`, `derived`, `historical`, or `skipped`).

---

### Real Local Case Studies: Evaluation Dispositions

Reviewing real evaluation records from the posttrainllm repository illustrates how this workflow governs model deployment:

#### Case Study 1: `qwen3-4b-file-ops-distilled`
- **Base Model:** Qwen3-4B-Instruct.
- **Depth Result:** File-operations hard gate improved from 58.0% (stock) to **100.0%**.
- **Breadth Result:** Out-of-domain general planning breadth regressed from 59.6% down to **42.3%**.
- **Evaluation Disposition:** `routed-ship`. The adapter was packaged strictly for routed deployment behind an intent classifier; general replacement was blocked.

#### Case Study 2: `qwen3-4b-rest-fused`
- **Base Model:** Qwen3-4B-Instruct + ReST synthetic fusion.
- **Depth Result:** Re-qualification confirmed file-ops depth moved from 9/12 to **12/12** (100%), with side-effect errors reduced and execution speed increasing by 2.42×.
- **Breadth Result:** Frontier-qualified general breadth dropped from 30/45 down to **25/45**.
- **Evaluation Disposition:** `routed-ship` retained as a routed specialist; rejected as a general model successor.

#### Case Study 3: `qwen06-sql-hygiene-dpo-v1`
- **Base Model:** Qwen3-0.6B + SFT DoRA adapter.
- **SimPO Experiment:** Reference-free SimPO preference loss caused policy collapse (execution dropped from 86.0% to 8.0%).
- **DPO Ref-Anchored Retry:** Reference-anchored DPO ($\beta=0.3$) recovered and improved execution accuracy to **92.0%**, but failed the raw format hygiene requirement (`clean-SQL` rate remained 0.000).
- **Evaluation Disposition:** `retry-data`. The evaluation proved that format hygiene on this base model required SFT generation-strength steering or constrained decoding rather than preference updates.

---

### Decision Authority and Release Governance

An evaluation workflow must culminate in an unambiguous, terminal decision. The posttrainllm framework recognizes four formal disposition categories:

| Decision | Criteria & Conditions | Next Action |
| :--- | :--- | :--- |
| **`ship`** | Passes target depth gate AND shows zero significant breadth regression. | Package as general model replacement. |
| **`routed-ship`** | Reaches target depth gate BUT exhibits out-of-domain breadth regression. | Package strictly behind domain-specific router. |
| **`retry-data`** | Fails target depth or hygiene gate due to data/prompt formatting limitations. | Re-design training data or SFT recipe; do not adjust eval gates. |
| **`reject`** | Fails safety, accuracy, or capacity constraints without clear recovery path. | Archive experiment as failed attempt; release no artifact. |

---

### Internal-Link Suggestions

- Examine full experiment disposition records in [`docs/attempt-ledger.md`](../../../docs/attempt-ledger.md).
- Review fine-tune report card schema definitions in [`docs/factory/report-card.md`](../../../docs/factory/report-card.md).
- Read the tool-calling evaluation strategy in [`docs/learn/small-model-tool-calling-playbook.md`](../../../docs/learn/small-model-tool-calling-playbook.md).
- Learn about baseline stamping protocols in [`docs/factory/run-schema.md`](../../../docs/factory/run-schema.md).

---

### Clear Next Action

To implement this evaluation workflow for your Mac-local LoRA adapters:
1. Establish a frozen baseline evaluation run for your base model using `posttrainllm eval-gate --save-baseline`.
2. Validate your evaluation benchmark against a frontier API (or Codex CLI) to confirm a ~100% ceiling.
3. Train your LoRA adapter and run `posttrainllm eval-gate` alongside your out-of-domain regression suite.
4. Execute `python3 scripts/factory/build_fine_tune_report_card.py --run-dir <path>` to generate a `report-card.json`.
5. Assign a formal terminal decision (`ship`, `routed-ship`, `retry-data`, or `reject`) based on the depth vs. breadth outcome.

---

### Source Notes (Non-Publishable)

*Supporting repository files:*
- `AGENTS.md` (Eval philosophy, frontier-ceiling gate, BFCL vs. hermes-fc analysis).
- `PROJECT_STATUS.md` (Specialist package records, ReST requalification results).
- `docs/attempt-ledger.md` (Recorded evaluation dispositions for 76 attempts).
- `docs/factory/report-card.md` (Report card JSON schema and publication rules).
- `scripts/factory/build_fine_tune_report_card.py` (Report card compiler implementation).
- `scripts/sql/score_sql_clean_output.py` (SQL format hygiene evaluation script).

*Limitations & Scope Boundary:*
- Review-only draft. No codebase dependencies, configuration, or website routes were modified.
- All evaluation scores, case studies, and hardware benchmarks reflect retained repository empirical evidence without fabrication or external extrapolation.
