#!/usr/bin/env bash
# No-MLX SQL factory POC smoke.
#
# Compiles only the SQL scorer + EvalSql CLI shim, builds the fixture SQLite DB,
# scores baseline/candidate predictions, and checks row-level failure logs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX="$ROOT/evals/sql-poc"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

command -v sqlite3 >/dev/null || { echo "SMOKE FAIL: sqlite3 not on PATH" >&2; exit 1; }

sqlite3 "$WORK/company.db" < "$FIX/company.sql"

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

baseline="$("$WORK/eval-sql" "$FIX/baseline-preds.jsonl" --db-dir "$WORK" --out "$WORK/baseline-rows.jsonl")"
candidate="$("$WORK/eval-sql" "$FIX/candidate-preds.jsonl" --db-dir "$WORK" --out "$WORK/candidate-rows.jsonl")"

echo "  baseline:  $baseline"
echo "  candidate: $candidate"

echo "$baseline" | grep -q "execution_accuracy=0.667" || {
  echo "SMOKE FAIL: expected baseline execution_accuracy=0.667" >&2; exit 1;
}
echo "$candidate" | grep -q "execution_accuracy=0.833" || {
  echo "SMOKE FAIL: expected candidate execution_accuracy=0.833" >&2; exit 1;
}
grep -q '"exec_match":false' "$WORK/baseline-rows.jsonl" || {
  echo "SMOKE FAIL: expected baseline row-level exec failure" >&2; exit 1;
}
grep -q '"predicted_error"' "$WORK/baseline-rows.jsonl" || {
  echo "SMOKE FAIL: expected baseline sqlite error capture" >&2; exit 1;
}
grep -q '"question":"List employee names with salary below 90000."' "$WORK/candidate-rows.jsonl" || {
  echo "SMOKE FAIL: expected question copied into row trace" >&2; exit 1;
}

echo "SMOKE OK: SQL POC fixture + row-level eval traces"
