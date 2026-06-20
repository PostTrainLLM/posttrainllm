#!/usr/bin/env bash
# evals/eval-sql-smoke.sh — B1 text-to-SQL execution-accuracy eval (no model).
#
# Builds a tiny SQLite DB + a predictions fixture (one exec-correct-but-
# differently-worded, one wrong, one identical) and asserts eval-sql's
# execution_accuracy / exact_match match the hand-computed values.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_tinygpt)" || fail "could not resolve tinygpt binary"
command -v sqlite3 >/dev/null || fail "sqlite3 not on PATH"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

sqlite3 "$TMP/test.db" "CREATE TABLE emp(id INTEGER, name TEXT, dept TEXT); \
  INSERT INTO emp VALUES (1,'Alice','eng'),(2,'Bob','sales'),(3,'Carol','eng');"

cat > "$TMP/preds.jsonl" <<'EOF'
{"predicted_sql":"select name from emp where dept='eng'","gold_sql":"SELECT name FROM emp WHERE dept = 'eng'","db":"test.db"}
{"predicted_sql":"select name from emp where dept='hr'","gold_sql":"select name from emp where dept='eng'","db":"test.db"}
{"predicted_sql":"select count(*) from emp","gold_sql":"select count(*) from emp","db":"test.db"}
EOF

out="$("$BIN" eval-sql "$TMP/preds.jsonl" --db-dir "$TMP")" || fail "eval-sql failed"
echo "  $out"
# row0 exec-match (same rows, diff text), row1 wrong, row2 match → exec 2/3
echo "$out" | grep -q "execution_accuracy=0.667" || fail "expected execution_accuracy 0.667, got: $out"
# only row2 is a normalized exact string match → 1/3
echo "$out" | grep -q "exact_match=0.333" || fail "expected exact_match 0.333, got: $out"
echo "SMOKE OK: eval-sql (B1)"
