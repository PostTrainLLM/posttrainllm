# Learning Pipeline

The owner's learning track is now explicitly ground-up. It still reinforces the
posttrainllm factory, but it does not start with post-training jargon.

Primary path:

```text
math intuition -> tiny neural net -> training loop -> transformer
-> LLM behavior -> post-training -> evals -> self-improving factory
```

Learning is not separate from building; every module should eventually make the
next run better.

**Start each session at [Next Session](learning-progress.md#next-session).**
It holds the one current module, one exercise, one owner explanation, and due
recall checks. That tracker is the only active study queue.

The [Learning Loop](learning-progress.md#learning-loop) defines advancement:
exercise plus immediate gate → `applied`; closed-book checks at +2 and +7 days
→ `verified`. Record actual answers, errors, and dates. Existing lessons and
agent-written explanations do not establish owner mastery.

All [articles and artifacts](learning-progress.md#preserved-learning-library)
remain available. The sequences below are reference maps from which a session
is selected; they do not create additional active assignments.

## Principle

```text
concept -> toy implementation -> posttrainllm anchor -> recipe improvement
```

If a learning topic does not improve target selection, data, post-training,
eval, packaging, or reporting, park it until it does.

## Ground-Up Master Roadmap

The canonical roadmap is [`docs/learn/curriculum.md`](learn/curriculum.md).

It defines the 10-module path:

1. functions, data, parameters
2. loss and gradient descent
3. vectors, matrices, tensors
4. non-linear neural nets and backprop
5. ML paradigms and scaling
6. tokenization, embeddings, language modeling
7. attention and transformer blocks
8. training mechanics
9. post-training: SFT, LoRA, preference tuning
10. evals, rewards, and self-improvement

The SQL factory is the lab, not the starting point. Do not skip the foundation
unless the module mastery gate can be passed out loud.

All ten modules now have a polished session. For the guarantee that every
shipped subsystem (post-training internals, quantization, serving,
interpretability, WASM/WebGPU, VLM, the factory loop) also has a learning
anchor, see [`docs/learn/coverage-map.md`](learn/coverage-map.md).

## Applied Systems Reading

The [industry learning roadmap](industry_learning_roadmap.md) holds source
reviews, exercises, and mastery gates. Match each reading to its prerequisites.

**Inside vLLM**, by Aleksa Gordić, belongs after transformer foundations in the
inference/runtime path. Work through request scheduling and KV memory first,
then advanced decoding and caching, then the single-machine-to-cluster boundary.
The exercise is a hand-simulated request trace and performance prediction table;
it needs no GPU run. See the [case study](industry_learning_roadmap.md#case-study---inside-vllm-inference-systems-and-scaling-boundaries)
and record progress in [the tracker](learning-progress.md).

**Splash**, by Inco AI, follows Inside vLLM as the Mac-specific specialization
case. Separate the shared scheduler/cache/API from the per-model packed weights,
Metal kernels, DFlash 2 draft, and memory plan. Its exercise designs a same-Mac
comparison across cold and cached TTFT, prefill, decode, concurrency, memory,
output validity, and task completion; the source review does not authorize an
install or benchmark. See the [case study](industry_learning_roadmap.md#case-study---splash-model-specific-mac-inference).

## Factory-Attached Learning Sequence

| Order | Topic | Why Now | Project Work It Unlocks | Primary Docs |
|---:|---|---|---|---|
| 1 | Eval design | Bad evals create fake progress | frozen gates, slice metrics, leakage checks, regression gates | [`docs/factory/eval-protocol.md`](factory/eval-protocol.md), [`docs/learn/eval-methodology-2026-06-08.md`](learn/eval-methodology-2026-06-08.md) |
| 2 | Data for post-training | Most improvement is data/reward shape, not optimizer novelty | SFT rows, preference pairs, candidate sets, synthetic data, trace-to-data | [`docs/factory/post-training-factory.md`](factory/post-training-factory.md), [`docs/recipes/from-traces.md`](recipes/from-traces.md) |
| 3 | SFT + LoRA mechanics | Current SQL wins came from SFT/LoRA; failures need adapter diagnosis | rank/layer sweeps, LoRA geometry, overfit checks | [`docs/training/sft.md`](training/sft.md), [`docs/techniques/lora_guide.md`](techniques/lora_guide.md), [`docs/factory/lora-geometry.md`](factory/lora-geometry.md) |
| 4 | Preference tuning | Hygiene SimPO collapsed; need to understand why | reference-anchored DPO retry, length-balanced negatives, KL/reference anchoring | [`docs/training/dpo.md`](training/dpo.md), [`docs/techniques/method-vs-recipe.md`](techniques/method-vs-recipe.md) |
| 5 | Verifiable rewards | SQL/tool-calling improvement needs executable rewards | SQL execution reward, BFCL AST reward, unit-test rewards | [`docs/techniques/sql-technique-backlog.md`](techniques/sql-technique-backlog.md), [`docs/learn/tool-calling-frontier-parity.md`](learn/tool-calling-frontier-parity.md) |
| 6 | RLVR / ReST / OAPL | Only useful after reward surfaces are clean | batch rollouts, offline scoring, policy lag, candidate selection | [`docs/factory/batch-posttraining.md`](factory/batch-posttraining.md), [`docs/learn/advanced-llm-training.md`](learn/advanced-llm-training.md) |
| 7 | Failure analysis | Failed runs must become data | trace review, failure taxonomy, targeted retry data | [`docs/factory/reports.md`](factory/reports.md), [`docs/attempt-ledger.md`](attempt-ledger.md) |
| 8 | Public reporting | Public artifacts are a product surface | case-study reports, blockers, competition comparison, reproduction notes | [`docs/factory/case-study-template.md`](factory/case-study-template.md), [`docs/factory/public-artifacts.md`](factory/public-artifacts.md) |

## Current Practical Curriculum

This is the ready project lab sequence for the owner's learning phase. Select a lab
from it when the current module and prerequisites make it useful; it does not
create a second active study queue or represent unfinished AI work. Any
exercise that trains a new model begins a fresh experiment with a new issue and
frozen gate.

### Module 1 — SQL Eval Quality

Goal: know when a SQL improvement claim is real.

Do:

- Read the SQL attempt ledger.
- Compare exact match vs execution accuracy.
- Study why public b-mc2 exact is not enough.
- Build or run the Spider/BIRD-style execution gate when DBs are local.

Deliverable:

- A short note in the next SQL report explaining which metric is trusted and
  which metric is only directional.

### Module 2 — Candidate Selection

Goal: understand why "choose the best answer" can be easier than open
generation.

Do:

- Read `docs/techniques/trainloop-teardown.md`.
- Inspect `scripts/sql/build_sql_candidate_choice.py`.
- Generate candidate-choice rows from existing SQL predictions.
- Train/eval a small candidate-selection adapter only after the recipe card is
  written.

Deliverable:

- Candidate-selection accuracy overall and by slice.

### Module 3 — Preference Tuning Failure

Goal: explain the failed hygiene SimPO run without hand-waving.

Do:

- Read the hygiene run report.
- Compare ref-free SimPO vs reference-anchored DPO.
- Inspect degenerate predictions and trace review.
- Define a safer retry recipe.

Deliverable:

- A recipe card that predicts how the retry avoids collapse.

### Module 4 — Adapter Geometry

Goal: see whether adapter failures are capacity, targeting, or optimization
problems.

Do:

- Run `scripts/lora_geometry.py` on successful and failed SQL adapters.
- Compare rank, stable rank, Frobenius norm, and top modules.
- Attach `lora-geometry.json` to the next run.

Deliverable:

- One paragraph in the report explaining whether the adapter update looked
  concentrated, diffuse, too small, or too large.

## Learning Is Complete For A Topic When

The owner has completed the exercise, explained the concept and its repo
connection, and passed both delayed recall checks with recorded evidence in
[the tracker](learning-progress.md#checkpoints-and-recall-queue). A toy exercise
or inspection can be sufficient; new training or production changes are not
required for learning completion. Actual experiments retain their own gates.
