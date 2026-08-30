# Batch-First Post-Training

Batch-first post-training is the factory default for Mac-local work:

```text
freeze prompts -> generate rollouts -> score offline -> train one adapter ->
eval -> trace review -> decision
```

This is cheaper and easier to audit than an online loop. It also matches the
artifact contract: every batch has a fixed prompt hash, rollout count, score
file, train log, eval report, and decision.

## Required Files

```text
runs/<id>/
  batch-posttrain-plan.json
  rollouts.jsonl
  scores.jsonl
  preferences.jsonl or rewards.jsonl
  train.log
  eval-candidate.json
  slice-metrics.json
  trace_review.md
  decision.json
```

Use:

```bash
python3 scripts/render_batch_posttrain_plan.py \
  --run-id <id> \
  --target <target> \
  --prompts <prompts.jsonl> \
  --base-model <base> \
  --out-dir runs/<id> \
  --rollouts-per-prompt 4
```

## SQL Candidate-Selection Curriculum

For sparse-reward SQL, first train/evaluate the model on selecting the best
query among candidates:

```bash
python3 scripts/sql/build_sql_candidate_choice.py \
  --prompts evals/sql-poc-expanded/dev.jsonl \
  --candidate sft=runs/2026-07-02-sql-expanded-qwen06/candidate-preds.jsonl \
  --candidate failed-dpo=runs/2026-07-03-sql-hygiene-dpo-qwen06/candidate-preds.jsonl \
  --out /tmp/sql-choice-dev.jsonl
```

This creates rows with `choices`, `answer_index`, `answer_id`, and `slices`.
A candidate-selection model can learn the verifier behavior before we ask it to
emit bare SQL from scratch.

## Decision Rule

Do not ship a batch-trained adapter unless:

- the frozen baseline is recorded
- slice metrics are attached
- `trace_review.md` exists
- failed attempts are listed
- the next blocker is explicit
