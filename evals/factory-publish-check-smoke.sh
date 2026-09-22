#!/usr/bin/env bash
# No-MLX smoke for the stricter factory publish evidence check.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

python3 "$ROOT/scripts/sql/render_sql_factory_run.py" --out "$WORK/sql-run"
python3 "$ROOT/scripts/factory/check_factory_run_publish.py" "$WORK/sql-run" --allow-report-only

# A declared lifecycle sidecar is validated rather than treated as legacy.
python3 - "$WORK/sql-run" <<'PY'
import json
import pathlib
import sys

run = pathlib.Path(sys.argv[1])
artifact = json.loads((run / "artifact.json").read_text())
artifact["kind"] = "adapter"
artifact["path"] = "candidate.lora"
artifact["lifecycle_manifest"] = "candidate.lora.artifact-manifest.json"
(run / "artifact.json").write_text(json.dumps(artifact, indent=2))
(run / "candidate.lora").write_bytes(b"TGLA")
manifest = {
    "schema_version": 1,
    "artifact": {"id": artifact["artifact_id"]},
    "kind": "adapter",
    "artifact_path": "candidate.lora",
    "base": {"id": artifact["base_model"], "revision": "fixture-revision"},
    "tokenizer": {"id": artifact["base_model"], "revision": "fixture-revision"},
    "history": [{"action": "sft", "tool": "posttrainllm"}],
    "runtimes": ["native-hf-load"],
    "next": ["eval", "serve"],
    "receipts": [{"kind": "eval", "path": "receipts/eval.json"}],
    "created_at": "2026-09-23T00:00:00Z",
}
(run / artifact["lifecycle_manifest"]).write_text(json.dumps(manifest, indent=2))
PY
python3 "$ROOT/scripts/factory/check_factory_run_publish.py" "$WORK/sql-run" --allow-report-only
if [[ -n "${POSTTRAINLLM_BIN:-}" ]]; then
  "$POSTTRAINLLM_BIN" factory-run publish-check --allow-report-only "$WORK/sql-run"
fi

python3 - "$WORK/sql-run/candidate.lora.artifact-manifest.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
manifest = json.loads(path.read_text())
manifest["receipts"] = {}
path.write_text(json.dumps(manifest, indent=2))
PY
if python3 "$ROOT/scripts/factory/check_factory_run_publish.py" "$WORK/sql-run" --allow-report-only >/dev/null 2>&1; then
  echo "factory publish check accepted non-list lifecycle receipts" >&2
  exit 1
fi

python3 - "$WORK/sql-run/candidate.lora.artifact-manifest.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
manifest = json.loads(path.read_text())
manifest["receipts"] = []
manifest["next"] = []
path.write_text(json.dumps(manifest, indent=2))
PY
if python3 "$ROOT/scripts/factory/check_factory_run_publish.py" "$WORK/sql-run" --allow-report-only >/dev/null 2>&1; then
  echo "factory publish check accepted a malformed lifecycle manifest" >&2
  exit 1
fi

echo "factory-publish-check-smoke ok"
