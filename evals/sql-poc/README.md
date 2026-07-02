# SQL POC Fixture

Tiny, deterministic SQL specialist fixture for the first factory POC.

This is not Spider. It is a low-compute gate that proves the factory loop shape:

```text
data -> baseline eval -> candidate eval -> row failures -> report
```

Files:

- `company.sql` builds the SQLite database.
- `train.jsonl` is the SFT-shape training fixture.
- `dev.jsonl` is the frozen heldout eval set.
- `baseline-preds.jsonl` is a deliberately imperfect baseline prediction file.
- `candidate-preds.jsonl` is a deliberately improved candidate prediction file.

Run:

```bash
bash evals/sql-poc-smoke.sh
```

The real model POC replaces the two `*-preds.jsonl` files with generated output
from the base model and base+adapter, then stores the results under `runs/`.
