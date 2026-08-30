# Recipe - Pace Planner Eval Protocol

Use this when a Pace planner candidate needs an unhappy-path score that is
publishable or comparable across runs. Model selection itself is locked in
`docs/sessions/planner-lock-2026-06-19.md`; this recipe is for measuring concrete
candidate changes, not reopening the base-model search.

## K=3 Unhappy-Path Run

Start the candidate behind an OpenAI-compatible `/v1/chat/completions` endpoint,
then run each unhappy-path dimension with the fixed B23 protocol:

```bash
python3 scripts/eval_pace_unhappy.py \
  --fixtures-dir evals/fm-fixtures-oos-h2 \
  --serve-url http://127.0.0.1:8765/v1/chat/completions \
  --model-id qwen3-4b-instruct-2507 \
  --sys-prompt grammars/pace-system-prompt-v10-actions.txt \
  --passes 3 \
  --budget evals/sample-budget.json \
  --out /tmp/pace-oos-k3.json
```

Repeat for:

```text
evals/fm-fixtures-ambig-h2
evals/fm-fixtures-destructive-h2
```

For final/public numbers, run the `*-h2-ext` suites too. The output JSON keeps
the old one-pass fields for `--passes 1`; for `--passes K`, it adds:

- `protocol`: fixed pass count and budget metadata.
- `pass_stats`: trial scores, mean, stdev, stderr, and 95% CI.
- `trials`: the raw per-pass results, including failure patterns and rows.

## Cheap Protocol Smoke

This exercises the aggregation path without a model:

```bash
python3 scripts/eval_pace_unhappy.py \
  --fixtures-dir evals/fm-fixtures-oos-h2 \
  --skip-model \
  --passes 3 \
  --budget evals/sample-budget.json \
  --out /tmp/pace-oos-skip-k3.json
```

Strict scorer audit:

```bash
python3 scripts/eval_pace_unhappy.py --self-test
```
