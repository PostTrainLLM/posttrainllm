"""Check one retained harness run structurally, without loading a model."""

import json
import sys
from pathlib import Path

root, task, expected = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
if expected <= 0:
    raise ValueError("expected sample count must be positive")
results = list(root.rglob("results_*.json"))
samples = list(root.rglob(f"samples_{task}_*.jsonl"))
if len(results) != 1 or len(samples) != 1:
    raise ValueError(
        "choose one run directory with exactly one result and task sample file"
    )
result = json.loads(results[0].read_text())
metrics = result.get("results", {}).get(task)
if not isinstance(metrics, dict) or not metrics:
    raise ValueError("task metrics missing")
seen = set()
for number, line in enumerate(samples[0].read_text().splitlines(), 1):
    row = json.loads(line)
    key = row.get("doc_id")
    if type(key) is not int or key in seen:
        raise ValueError(f"sample {number}: missing or duplicate integer doc_id")
    if not isinstance(row.get("resps"), list) or not row["resps"]:
        raise ValueError(f"sample {number}: missing raw responses")
    if not isinstance(row.get("filtered_resps"), list) or not row["filtered_resps"]:
        raise ValueError(f"sample {number}: missing filtered responses")
    seen.add(key)
if len(seen) != expected:
    raise ValueError(f"expected {expected} samples, found {len(seen)}")
print(
    json.dumps(
        {
            "task": task,
            "samples": len(seen),
            "metric_keys": sorted(metrics),
            "result": str(results[0]),
            "samples_file": str(samples[0]),
        }
    )
)
