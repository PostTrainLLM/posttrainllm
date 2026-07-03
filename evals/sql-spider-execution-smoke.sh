#!/usr/bin/env bash
# No-model smoke for the Spider-style public SQL execution gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v sqlite3 >/dev/null || { echo "SMOKE FAIL: sqlite3 not on PATH" >&2; exit 1; }

mkdir -p "$WORK/spider/database/company"
sqlite3 "$WORK/spider/database/company/company.sqlite" <<'SQL'
CREATE TABLE departments(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE employees(id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER, salary INTEGER);
INSERT INTO departments VALUES (1, 'engineering'), (2, 'finance');
INSERT INTO employees VALUES
  (1, 'Ada', 1, 130000),
  (2, 'Lin', 2, 90000),
  (3, 'Grace', 1, 125000);
SQL

python3 - "$WORK/spider/dev.json" <<'PY'
import json
import sys
rows = [
    {
        "db_id": "company",
        "question": "Which employees work in engineering?",
        "query": "select e.name from employees e join departments d on e.dept_id = d.id where d.name = 'engineering';",
    },
    {
        "db_id": "company",
        "question": "How many employees earn more than 100000?",
        "query": "select count(*) from employees where salary > 100000;",
    },
]
open(sys.argv[1], "w").write(json.dumps(rows))
PY

python3 "$ROOT/scripts/build_sql_spider_execution_gate.py" \
  --spider-root "$WORK/spider" \
  --out "$WORK/gate"

python3 - "$WORK/gate/dev.jsonl" "$WORK/gold-preds.jsonl" "$WORK/bad-preds.jsonl" <<'PY'
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
assert len(rows) == 2, len(rows)
assert all(row["source"] == "spider" for row in rows)
assert all(row["db"] == "database/company/company.sqlite" for row in rows)
assert "CREATE TABLE employees" in rows[0]["schema"]

with open(sys.argv[2], "w") as gold, open(sys.argv[3], "w") as bad:
    for idx, row in enumerate(rows):
        row["predicted_sql"] = row["gold_sql"]
        gold.write(json.dumps(row, separators=(",", ":")) + "\n")
        bad_row = dict(row)
        bad_row["predicted_sql"] = "select name from employees where salary < 0;"
        bad.write(json.dumps(bad_row, separators=(",", ":")) + "\n")
PY

cat >"$WORK/EvalHarnessSupport.swift" <<'SWIFT'
import Foundation

enum EvalHarnessSupport {
    static func resolveExecutable(_ name: String) -> URL? {
        let path = ProcessInfo.processInfo.environment["PATH"] ?? ""
        for dir in path.split(separator: ":") {
            let candidate = URL(fileURLWithPath: String(dir)).appendingPathComponent(name)
            if FileManager.default.isExecutableFile(atPath: candidate.path) {
                return candidate
            }
        }
        return nil
    }
}
SWIFT

cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

EvalSql.run(args: Array(CommandLine.arguments.dropFirst()))
SWIFT

swiftc -emit-module -emit-object -parse-as-library \
  -module-name TinyGPTModel \
  "$ROOT/native-mac/Sources/TinyGPTModel/SqlEval.swift" \
  -emit-module-path "$WORK/TinyGPTModel.swiftmodule" \
  -o "$WORK/SqlEval.o"

swiftc -I "$WORK" \
  "$WORK/SqlEval.o" \
  "$ROOT/native-mac/Sources/TinyGPT/EvalSql.swift" \
  "$WORK/EvalHarnessSupport.swift" \
  "$WORK/main.swift" \
  -o "$WORK/eval-sql"

gold="$("$WORK/eval-sql" "$WORK/gold-preds.jsonl" --db-dir "$WORK/spider" --out "$WORK/gold-rows.jsonl")"
bad="$("$WORK/eval-sql" "$WORK/bad-preds.jsonl" --db-dir "$WORK/spider" --out "$WORK/bad-rows.jsonl")"

echo "  gold: $gold"
echo "  bad:  $bad"

echo "$gold" | grep -q "execution_accuracy=1.000" || {
  echo "SMOKE FAIL: expected gold execution_accuracy=1.000" >&2; exit 1;
}
echo "$bad" | grep -q "execution_accuracy=0.000" || {
  echo "SMOKE FAIL: expected bad execution_accuracy=0.000" >&2; exit 1;
}
grep -q '"exec_match":false' "$WORK/bad-rows.jsonl" || {
  echo "SMOKE FAIL: expected bad row exec failure trace" >&2; exit 1;
}

echo "SMOKE OK: Spider-style SQL execution gate"
