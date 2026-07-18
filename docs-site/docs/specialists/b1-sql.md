---
title: "B1 — second specialist: text-to-SQL"
description: "Cookie-cuts the A1 recipe onto a second domain to prove platform generality."
---

# B1 — second specialist: text-to-SQL

Cookie-cuts the A1 recipe onto a second domain to prove platform generality.
**Domain decision (V1): SQL** (over shell) — SQLite gives a clean, dependency-
free execution-accuracy metric; shell needs sandboxing (deferred).

## Eval (shipped + verified)

`posttrainllm eval-sql` scores a predictions file by **execution accuracy** (run
predicted vs gold SQL on the DB, compare result sets order-insensitively) plus
normalized exact-match — the Spider metric, self-contained via `sqlite3`:

```bash
posttrainllm eval-sql preds.jsonl --db-dir ./dbs --out sql-rows.jsonl
# preds.jsonl rows: {predicted_sql, gold_sql, db}
```

Verified by `evals/eval-sql-smoke.sh` (exec 0.667 / exact 0.333 on a fixture).
Core comparison + aggregation are unit-tested (`SqlEvalTests`).

## Remaining (needs a GPU)

- **Training** — `posttrainllm sft <base> --data spider-sft.jsonl --llrd 0.9`
  (cookie-cut of A1's step 2), on a Spider/WikiSQL SFT export.
- **Generation** — produce `predicted_sql` for the dev set by serving the
  adapter and prompting; eval-sql then scores it. (A dedicated
  generate-then-score path like eval-bfcl's is the small follow-up; for now
  generate via `posttrainllm serve <base> --lora b1.lora` + a client.)
- **Gate** — `eval-gate` on execution-accuracy delta vs base.

## Status

**Eval infra + domain decision shipped (2026-06-20); training + generation
pending a GPU.** B1 was fully not-started; the scoring half now exists and is
the reusable piece (E0-schema rows feed `eval-compare`/`eval-gate`).
