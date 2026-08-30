#!/usr/bin/env bash
# No-GPU smoke for the generic factory-run assembler bridge.
#
# Proves that scripts/factory/assemble_factory_run.py turns real train/eval fragments
# into a canonical run folder that passes BOTH:
#   1. check_factory_run_publish.py  (the publish gate), and
#   2. FactoryRunFolder.validate     (the typed Swift schema).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

RUN="$WORK/run"
mkdir -p "$RUN"

# Real dataset source files so provenance can hash them.
printf '{"q": "row %s"}\n' 1 2 3 4 5 6 7 8 9 10 >"$WORK/train.jsonl"
printf '{"q": "dev %s"}\n' 1 2 3 >"$WORK/dev.jsonl"

# Emit the fragments a real train/eval/decision run would drop into runs/<id>/.
python3 - "$RUN" "$WORK/train.jsonl" "$WORK/dev.jsonl" <<'PY'
import json, sys
run, train, dev = sys.argv[1], sys.argv[2], sys.argv[3]

def w(name, obj):
    with open(f"{run}/{name}", "w") as f:
        json.dump(obj, f, indent=2)

w("config.json", {
    "run_id": "2026-07-11-smoke-assemble-v1",
    "target": "smoke-assemble-target",
    "owner_goal": "Prove the generic assembler bridge without compute.",
    "base_model": {"id": "fixture-base", "revision": "abc123", "precision": "bf16"},
    "candidate": {"method": "sft-lora", "adapter_format": "tgla",
                  "training_command": "posttrainllm sft fixture-base --data train.jsonl"},
    "eval": {"primary": "fixture-gate", "regression": "fixture-breadth",
             "threshold": {"primary_min": 0.9, "breadth_drop_max_pp": 3}},
})
w("dataset.json", {
    "dataset_id": "smoke-assemble-dataset",
    "sources": [
        {"kind": "sft", "path": train, "rows": 10},
        {"kind": "heldout", "path": dev, "rows": 3},
    ],
    "processing": {"dedupe": True, "quality_filter": True, "heldout_split": "locked"},
    "counts": {"train_rows": 10, "heldout_rows": 3, "dropped_rows": 1},
})
w("eval-baseline.json", {
    "model_id": "fixture-base", "command": "posttrainllm eval-gate fixture-base",
    "suite": "fixture-gate", "score": 0.70, "passed": False, "date": "2026-07-11",
    "latency_ms": None, "peak_rss_mb": None, "tokens_per_second": None,
    "notes": "baseline fixture",
})
w("eval-candidate.json", {
    "model_id": "fixture-candidate", "command": "posttrainllm eval-gate fixture-candidate",
    "suite": "fixture-gate", "score": 0.93, "passed": True, "date": "2026-07-11",
    "latency_ms": 42, "peak_rss_mb": 128, "tokens_per_second": 77,
    "notes": "candidate fixture",
})
w("artifact.json", {
    "artifact_id": "smoke-assemble-adapter", "kind": "adapter",
    "path": "specialists/smoke-assemble-adapter", "base_model": "fixture-base",
    "format": "tgla", "package_dir": None, "shipped": False,
})
w("decision.json", {
    "decision": "retry-training",
    "reason": "Primary cleared threshold but this is a fixture, not a shipped package.",
    "failure_reason": "Fixture run; no real package gate was applied.",
    "failure_reason_confidence": "inferred",
    "lesson": "The assembler derives provenance and report from fragments only.",
    "next_action": "Wire the live train/eval commands to emit these fragments.",
    "evidence_sources": ["eval-candidate.json", "report.md"],
    "blocked_by": ["fixture-only run"],
})
w("slice-metrics.json", {
    "overall": {"rows": 3, "note": "fixture overall"},
    "slices": {
        "easy": {"rows": 2, "metric": "accuracy", "baseline": 0.80, "candidate": 0.95,
                 "delta": 0.15, "pass": True},
        "hard": {"rows": 1, "metric": "accuracy", "baseline": 0.50, "candidate": 0.80,
                 "delta": 0.30, "pass": True},
    },
})
with open(f"{run}/trace_review.md", "w") as f:
    f.write("# Fixture Trace Review\n\n## Trace Review\n\nNo real traces; fixture only.\n")
print("fragments written")
PY

# 1. Assemble + publish-check (report-only; artifact is unshipped).
python3 "$ROOT/scripts/factory/assemble_factory_run.py" "$RUN" --publish-check

# 2. Assert the assembler DERIVED the files (not authored by the fixture).
for f in provenance.json report.md train.log; do
  test -f "$RUN/$f" || { echo "SMOKE FAIL: assembler did not write $f" >&2; exit 1; }
done

# 3. Assert the report computed the eval delta (0.93 - 0.70 = 0.2300), not a typed value.
grep -q "| fixture-gate | 0.7000 | 0.9300 | 0.2300 | yes |" "$RUN/report.md" \
  || { echo "SMOKE FAIL: report.md missing computed eval delta row" >&2; exit 1; }
grep -q "## Evidence / Exactness" "$RUN/report.md" \
  || { echo "SMOKE FAIL: report.md missing Evidence / Exactness section" >&2; exit 1; }

# 4. Assert provenance carries a real dataset sha256 and the git commit.
python3 - "$RUN/provenance.json" <<'PY'
import json, sys
prov = json.load(open(sys.argv[1]))
assert prov["schema_version"] == 1, "schema_version"
assert prov["renderer"] == "scripts/factory/assemble_factory_run.py", "renderer"
assert prov["commands"]["baseline"] == "posttrainllm eval-gate fixture-base", "baseline cmd"
ds = prov["datasets"]
assert len(ds) == 2 and all(len(d["sha256"]) == 64 for d in ds), "dataset sha256"
assert ds[0]["rows"] == 10 and ds[1]["rows"] == 3, "dataset rows"
print("provenance ok")
PY

# 5. A failure after lifecycle creation records only a bounded sanitized state.
FAIL_RUN="$WORK/failing-run"
python3 - "$RUN" "$FAIL_RUN" <<'PY'
import json, pathlib, shutil, sys
source, target = map(pathlib.Path, sys.argv[1:])
shutil.copytree(source, target)
for name in ("run-status.json", "provenance.json", "report.md", "train.log"):
    (target / name).unlink(missing_ok=True)
config = json.load(open(target / "config.json"))
config["run_id"] = "2026-07-11-smoke-assembly-failure-v1"
json.dump(config, open(target / "config.json", "w"), indent=2)
dataset = json.load(open(target / "dataset.json"))
dataset["sources"][0]["path"] = "/private/path/that-must-not-leak/train.jsonl"
dataset["sources"][0].pop("sha256", None)
json.dump(dataset, open(target / "dataset.json", "w"), indent=2)
PY

if python3 "$ROOT/scripts/factory/assemble_factory_run.py" "$FAIL_RUN" >/dev/null 2>&1; then
  echo "SMOKE FAIL: invalid assembly unexpectedly succeeded" >&2
  exit 1
fi
python3 - "$FAIL_RUN/run-status.json" <<'PY'
import json, sys
status = json.load(open(sys.argv[1]))
assert status["phase"] == "failed"
assert status["failure"]["code"] == "assembly-failed"
assert "/private/path" not in status["failure"]["summary"]
print("sanitized assembly failure ok")
PY

# 6. Prove the fragments are valid against the typed Swift schema.
cat >"$WORK/main.swift" <<'SWIFT'
import Foundation

func assertTrue(_ condition: @autoclosure () -> Bool, _ msg: String) {
    if !condition() {
        fputs("SMOKE FAIL: \(msg)\n", stderr)
        exit(1)
    }
}

let run = URL(fileURLWithPath: CommandLine.arguments[1])
let bundle = try FactoryRunFolder.validate(directory: run)
let lifecycle = try FactoryRunLifecycle.readStatus(directory: run)
assertTrue(bundle.config.runId == "2026-07-11-smoke-assemble-v1", "run id")
assertTrue(bundle.baseline.score == 0.70, "baseline score")
assertTrue(bundle.candidate.score == 0.93, "candidate score")
assertTrue(bundle.decision.decision == .retryTraining, "decision")
assertTrue(lifecycle.phase == .decided, "lifecycle decided")
assertTrue(lifecycle.lastTransition.source == "python-assembler", "bridge source")
print("SMOKE OK: assembled folder validates against typed Swift schema")
SWIFT

CLANG_MODULE_CACHE_PATH="$WORK/clang-module-cache" swiftc \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRun.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift" \
  "$ROOT/native-mac/Sources/TinyGPTIO/FactoryRunFolder.swift" \
  "$WORK/main.swift" \
  -o "$WORK/factory-run-assemble-smoke"

"$WORK/factory-run-assemble-smoke" "$RUN"

echo "factory-run-assemble-smoke ok"
