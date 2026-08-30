#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/rows.jsonl" <<'JSONL'
{"id":"ok","domain":"hr","prompt":"Schema: employees(id, name). Question: List names.","question":"List names.","gold_sql":"SELECT name FROM employees;","predicted_sql":"SELECT name FROM employees;","exec_match":true,"exact_match":true,"clean":true}
{"id":"wrapped","domain":"sales","prompt":"Schema: orders(id, status). Question: Count shipped orders.","question":"Count shipped orders.","gold_sql":"SELECT count(*) FROM orders WHERE status = 'shipped';","predicted_sql":"```sql\nSELECT count(*) FROM orders WHERE status = 'shipped';\n```","exec_match":true,"exact_match":false,"clean":false}
{"id":"hallucinated","domain":"hr","prompt":"Schema: employees(id, name). Question: List salaries.","question":"List salaries.","gold_sql":"SELECT name FROM employees;","predicted_sql":"SELECT salary FROM employees;","scored_sql":"SELECT salary FROM employees;","exec_match":false,"exact_match":false,"clean":true}
{"id":"missing-join","domain":"hr","prompt":"Schema: employees(id, name, department_id); departments(id, name). Question: List employee names with department names.","question":"List employee names with department names.","gold_sql":"SELECT employees.name, departments.name FROM employees JOIN departments ON employees.department_id = departments.id;","predicted_sql":"SELECT employees.name FROM employees;","exec_match":false,"exact_match":false,"clean":true}
JSONL

python3 scripts/sql/score_sql_slices.py \
  "$TMP_DIR/rows.jsonl" \
  --out "$TMP_DIR/slices.json" >/dev/null

python3 scripts/sql/review_sql_trace.py \
  --rows "$TMP_DIR/rows.jsonl" \
  --out "$TMP_DIR/trace_review.md" >/dev/null

grep -q "SQL Trace Review" "$TMP_DIR/trace_review.md"
grep -q "hallucinated_schema" "$TMP_DIR/trace_review.md"
grep -q "missing_join" "$TMP_DIR/trace_review.md"
grep -q "overall" "$TMP_DIR/slices.json"
echo "sql-trace-review-smoke ok"
