#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/prompts.jsonl" <<'JSONL'
{"id":"q1","domain":"hr","prompt":"Schema: employees(id, name, department_id); departments(id, name). Question: List employee names with department names.","question":"List employee names with department names.","gold_sql":"SELECT employees.name, departments.name FROM employees JOIN departments ON employees.department_id = departments.id;"}
{"id":"q2","domain":"sales","prompt":"Schema: orders(id, amount, status). Question: Count shipped orders.","question":"Count shipped orders.","gold_sql":"SELECT count(*) FROM orders WHERE status = 'shipped';"}
JSONL

cat > "$TMP_DIR/sft.jsonl" <<'JSONL'
{"id":"q1","predicted_sql":"SELECT employees.name FROM employees;"}
{"id":"q2","predicted_sql":"SELECT count(*) FROM orders;"}
JSONL

cat > "$TMP_DIR/retry.jsonl" <<'JSONL'
{"id":"q1","predicted_sql":"SELECT employees.name, departments.name FROM employees JOIN departments ON employees.department_id = departments.id;"}
{"id":"q2","predicted_sql":"```sql\nSELECT count(*) FROM orders WHERE status = 'shipped';\n```"}
JSONL

python3 scripts/build_sql_candidate_choice.py \
  --prompts "$TMP_DIR/prompts.jsonl" \
  --candidate sft="$TMP_DIR/sft.jsonl" \
  --candidate retry="$TMP_DIR/retry.jsonl" \
  --out "$TMP_DIR/choices.jsonl" \
  --max-candidates 4

python3 - "$TMP_DIR/choices.jsonl" "$TMP_DIR/preds.jsonl" <<'PY'
import json, sys
choices = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
with open(sys.argv[2], "w") as f:
    for row in choices:
        f.write(json.dumps({"id": row["id"], "selected_id": row["answer_id"]}) + "\n")
PY

python3 scripts/score_sql_candidate_choice.py \
  --choices "$TMP_DIR/choices.jsonl" \
  --preds "$TMP_DIR/preds.jsonl" \
  --out "$TMP_DIR/scored.jsonl" > "$TMP_DIR/summary.json"

test "$(wc -l < "$TMP_DIR/scored.jsonl" | tr -d ' ')" = "2"
grep -q '"accuracy": 1.0' "$TMP_DIR/summary.json"
echo "sql-choice-smoke ok"
