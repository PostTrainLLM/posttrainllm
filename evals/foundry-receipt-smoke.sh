#!/usr/bin/env bash
# No-GPU smoke for the Foundry evidence receipt pipeline.
#
# Proves:
#   1. scripts/foundry_receipt.py emits a schema-valid receipt from the
#      real repo state (registry, git, public-site files, nightly markers).
#   2. scripts/check_foundry_receipt.py accepts it.
#   3. A receipt built from a fixture factory run folder (with private
#      fragments) is sanitized: the private fragments never appear in the
#      receipt, and the validator still accepts it.
#   4. A hand-crafted receipt with a denylisted field is rejected.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== [1/4] emit receipt from real repo state (no CI) =="
python3 "$ROOT/scripts/foundry_receipt.py" --no-ci --out "$WORK/receipt.json"
python3 "$ROOT/scripts/check_foundry_receipt.py" "$WORK/receipt.json"

echo "== [2/4] receipt carries no private fields =="
if python3 -c "
import json, sys
r = json.load(open('$WORK/receipt.json'))
blob = json.dumps(r).lower()
bad = ['prompt', 'completion', 'gold', 'prediction', 'checkpoint', 'api_key', 'token', 'secret']
hits = [b for b in bad if b in blob]
# 'token' appears in 'tokenizer' legitimately; allow only that substring form.
hits = [b for b in hits if not (b == 'token' and 'tokenizer' in blob)]
sys.exit(1 if hits else 0)
"; then
  echo "  ok: no denylisted field names in real receipt"
else
  echo "  FAIL: denylisted field names found in real receipt" >&2
  exit 1
fi

echo "== [3/4] fixture run with private fragments is sanitized =="
RUNS="$WORK/runs"
RUN="$RUNS/2026-07-19-fixture-private"
mkdir -p "$RUN"

# Real dataset source so provenance can hash it.
printf '{"q": "row %s"}\n' 1 2 3 4 5 6 7 8 9 10 >"$WORK/train.jsonl"
printf '{"q": "dev %s"}\n' 1 2 3 >"$WORK/dev.jsonl"

python3 - "$RUN" "$WORK/train.jsonl" "$WORK/dev.jsonl" <<'PY'
import json, sys
run, train, dev = sys.argv[1], sys.argv[2], sys.argv[3]
def w(name, obj):
    with open(f"{run}/{name}", "w") as f:
        json.dump(obj, f, indent=2)
w("config.json", {
    "run_id": "2026-07-19-fixture-private",
    "target": "fixture-private",
    "owner_goal": "Prove sanitization.",
    "base_model": {"id": "fixture-base", "revision": "abc123", "precision": "bf16"},
    "candidate": {"method": "sft-lora", "adapter_format": "tgla",
                  "training_command": "posttrainllm sft fixture-base --data train.jsonl"},
    "eval": {"primary": "fixture-gate", "regression": "fixture-breadth",
             "threshold": {"primary_min": 0.9, "breadth_drop_max_pp": 3}},
})
w("dataset.json", {
    "sources": [
        {"kind": "sft", "path": train, "rows": 10},
        {"kind": "heldout", "path": dev, "rows": 3},
    ],
    "processing": {"dedupe": True, "quality_filter": True, "heldout_split": "locked"},
    "counts": {"train_rows": 10, "heldout_rows": 3, "dropped_rows": 0},
})
w("eval-baseline.json", {
    "model_id": "fixture-base", "command": "posttrainllm eval-gate fixture-base",
    "suite": "fixture-gate", "score": 0.50, "passed": False, "date": "2026-07-19",
    "latency_ms": None, "peak_rss_mb": None, "tokens_per_second": None,
    "notes": "baseline fixture",
})
w("eval-candidate.json", {
    "model_id": "fixture-candidate", "command": "posttrainllm eval-gate fixture-candidate",
    "suite": "fixture-gate", "score": 0.90, "passed": True, "date": "2026-07-19",
    "latency_ms": 42, "peak_rss_mb": 128, "tokens_per_second": 77,
    "notes": "candidate fixture",
})
w("decision.json", {
    "decision": "retry-training",
    "reason": "Fixture for sanitization smoke; not a real ship.",
    "failure_reason": "Fixture run; no real package gate was applied.",
    "failure_reason_confidence": "inferred",
    "lesson": "The receipt must sanitize private fragments from the run folder.",
    "next_action": "Verify the receipt carries no private fields.",
    "evidence_sources": ["eval-candidate.json", "report.md"],
    "blocked_by": ["fixture-only run"],
})
w("slice-metrics.json", {
    "overall": {"rows": 10, "note": "fixture overall"},
    "slices": {
        "easy": {"rows": 5, "metric": "accuracy", "baseline": 0.80, "candidate": 0.95,
                 "delta": 0.15, "pass": True},
        "hard": {"rows": 5, "metric": "accuracy", "baseline": 0.20, "candidate": 0.85,
                 "delta": 0.65, "pass": True},
    },
})
with open(f"{run}/trace_review.md", "w") as f:
    f.write("# Trace review (fixture)\n\nNo real traces; fixture for sanitization smoke.\n")
# Private fragments that MUST NOT leak into the receipt.
w("prompt.json", {"prompt": "PRIVATE PROMPT TEXT THAT MUST NOT LEAK"})
w("completion.json", {"completion": "PRIVATE COMPLETION TEXT THAT MUST NOT LEAK"})
w("checkpoint.json", {"checkpoint_bytes": "PRIVATE CHECKPOINT BYTES", "weights": "PRIVATE WEIGHTS"})
with open(f"{run}/train.log", "w") as f:
    f.write("PRIVATE TRAINING LOG CONTENT WITH prompt gold completion prediction\n")
PY

# Assemble so provenance.json exists (required for the receipt's dataset hash).
python3 "$ROOT/scripts/assemble_factory_run.py" "$RUN" --publish-check >/dev/null

python3 "$ROOT/scripts/foundry_receipt.py" --no-ci --runs "$RUNS" --out "$WORK/run-receipt.json"
python3 "$ROOT/scripts/check_foundry_receipt.py" "$WORK/run-receipt.json"

if grep -E "PRIVATE (PROMPT|COMPLETION|CHECKPOINT|WEIGHTS|TRAINING LOG)" "$WORK/run-receipt.json"; then
  echo "  FAIL: private fixture text leaked into receipt" >&2
  exit 1
fi
# Check for denylisted JSON keys (not values — "weights-published" is a legit
# storage status string, not a private weight payload). Python exits 1 when
# a denylisted key is found; bash enters the fail block on non-zero exit.
if ! python3 -c "
import json, sys
r = json.load(open('$WORK/run-receipt.json'))
bad_keys = ('prompt', 'completion', 'gold', 'prediction', 'checkpoint', 'weights', 'weights_bytes', 'adapter_bytes', 'optimizer_state', 'api_key', 'secret', 'password', 'credential')
def walk(v, path=''):
    if isinstance(v, dict):
        for k, val in v.items():
            kl = str(k).lower()
            if any(kl == b or kl.endswith('_' + b) for b in bad_keys):
                print(f'  denylisted key: {path}.{k}', file=sys.stderr)
                return True
            if walk(val, f'{path}.{k}'):
                return True
    elif isinstance(v, list):
        for i, val in enumerate(v):
            if walk(val, f'{path}[{i}]'):
                return True
    return False
sys.exit(1 if walk(r) else 0)
"; then
  echo "  FAIL: denylisted field name leaked into receipt" >&2
  exit 1
fi
echo "  ok: fixture run receipt is sanitized and valid"

echo "== [4/4] validator rejects a receipt with a denylisted field =="
python3 - <<'PY' >"$WORK/bad-receipt.json"
import json
r = {
    "schema_version": 1,
    "project": "posttrainllm",
    "generated_at": "2026-07-19T00:00:00+00:00",
    "source_revision": {"commit": "abc", "branch": "main", "dirty": False},
    "ci": {"status": "not-applicable"},
    "public_site": {"build": "pass", "live": "pass", "indexing": "pass", "freshness_window_days": 14},
    "playground": {"bundle": "pass", "activation_event": "playground_loaded", "failure_event": "foundry_page_crash"},
    "artifacts": [],
    "local_runs": [],
    "nightly": [],
    "publication_authority": "manual",
    "accepted_exceptions": [],
    "blocked": [],
    "prompt": "PRIVATE PROMPT THAT MUST BE REJECTED",
}
print(json.dumps(r, indent=2))
PY

if python3 "$ROOT/scripts/check_foundry_receipt.py" "$WORK/bad-receipt.json" 2>/dev/null; then
  echo "  FAIL: validator accepted a receipt with a denylisted field" >&2
  exit 1
fi
echo "  ok: validator rejected denylisted field"

echo
echo "foundry-receipt-smoke: all checks passed"
