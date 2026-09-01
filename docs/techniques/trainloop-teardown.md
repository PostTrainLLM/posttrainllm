# TrainLoop Teardown

This note records the useful techniques extracted from TrainLoop case studies
and maps them into posttrainllm recipes. The point is not to copy marketing language.
The point is to convert external evidence into local experiments.

This teardown is closed reference material. The three once-proposed SQL runs
now have final `rejected` dispositions in `docs/attempts.json` because their
targets were not frozen and later evidence made retrospective compute
unjustified. They remain useful recipe shapes for a genuinely fresh target.

## What We Learned

| External Technique | posttrainllm Translation | Status |
|---|---|---|
| Failed attempts are part of the artifact | Reports must include failed recipes and why they failed | Added to factory report template |
| Slice metrics matter more than headline score | SQL reports need join/filter/group/format/clean-output slices | Tooling added with `scripts/sql/score_sql_slices.py` |
| Trace review should inspect actual outputs | SQL reports need qualitative labels like hallucinated schema and format collapse | Tooling added with `scripts/sql/review_sql_trace.py` |
| Candidate selection can unlock sparse tasks | Train SQL model to choose among candidate queries before open generation | Closed/rejected without a frozen target |
| Batch-first post-training reduces moving-target instability | Generate rollouts, score offline, train one update, eval heldout | Closed/rejected without a frozen target |
| Policy lag can regularize RL-style updates | Avoid constantly refreshing the reference/rollout policy | Reference-only; no standalone run justified |
| LoRA geometry can explain adapter behavior | Inspect effective-update rank/norm/module concentration | Tooling added with `scripts/lora_geometry.py` |

## What Was New vs Existing Roadmap

Already present as broad methods:

- SFT
- DPO/SimPO
- LoRA/DoRA
- evals
- traces
- failure labels
- RLVR/ReST as future methods

New or sharpened as recipes:

- candidate-selection before open SQL generation
- one-step offline scored rollout loop
- policy-lag as a regularization idea
- controlled SQL rank sweep instead of unstructured rank changes
- LoRA effective-update geometry as a decision input
- release/report gates requiring slice metrics and trace review

## Retained Recipe Shapes

A fresh SQL training experiment should not be "try another DPO" by itself. If
the owner opens a new target, it can start from one of these recipe cards:

### Candidate Selection First

- Target: SQL specialist
- Method: supervised candidate selection, later RLVR/ReST if useful
- Failure mode addressed: sparse reward and fragile open generation
- Data: frozen SQL prompts plus candidates from incumbent, failed adapters, and
  gold SQL
- Eval gate: candidate-selection accuracy overall and by SQL slice
- Stop rule: continue only if selection accuracy is strong on join/filter slices

### Reference-Anchored Hygiene DPO

- Target: synthetic side of `qwen06-sql-routed-v1`
- Method: DPO with reference anchor
- Failure mode addressed: prose/fence wrapping without destroying SQL execution
- Data: existing 108 hygiene preference pairs
- Eval gate: synthetic execution >= `0.860` and clean-SQL raw-output lift
- Stop rule: reject if execution regresses or no clean-output lift appears

### Controlled LoRA Sweep

- Target: whichever SQL recipe is selected
- Method: LoRA/DoRA rank sweep
- Failure mode addressed: unknown adapter capacity and update concentration
- Data: one frozen dataset only
- Eval gate: same baseline/candidate/slice report for every rank
- Stop rule: pick the smallest rank that passes slice gates

## Documentation Standard

Every newly authorized external teardown should create one of:

- a recipe card in `docs/techniques/`
- an experiment row in the fresh target issue and attempt ledger
- a rejection note explaining why the technique does not apply

If it does not become one of those, it is not captured.
