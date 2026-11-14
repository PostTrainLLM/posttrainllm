"""Check manifest grouping and exact event duplicates; no semantic deduplication."""

import hashlib
import json
import sys
from pathlib import Path

seen_ids = set()
groups = {}
fingerprints = {}
counts = {}
for number, line in enumerate(Path(sys.argv[1]).read_text().splitlines(), 1):
    row = json.loads(line)
    for field in ("id", "source_group", "task_family"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise ValueError(f"line {number}: missing {field}")
    if row["id"] in seen_ids:
        raise ValueError(f"duplicate id {row['id']}")
    seen_ids.add(row["id"])
    split = row.get("split")
    if split not in {"train", "valid", "test"}:
        raise ValueError(f"{row['id']}: invalid split")
    events = row.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError(f"{row['id']}: empty events")
    for event in events:
        if not isinstance(event, dict) or event.get("type") not in {
            "observation",
            "tool_call",
            "tool_result",
            "final",
        }:
            raise ValueError(f"{row['id']}: invalid event type")
        if not isinstance(event.get("payload"), dict):
            raise ValueError(f"{row['id']}: event payload must be an object")
    for field in ("source_group", "task_family"):
        key = (field, row[field])
        if key in groups and groups[key] != split:
            raise ValueError(f"{field} {row[field]} crosses splits")
        groups[key] = split
    fingerprint = hashlib.sha256(
        json.dumps(events, sort_keys=True).encode()
    ).hexdigest()
    if fingerprint in fingerprints:
        raise ValueError(
            f"exact duplicate episodes: {fingerprints[fingerprint]} and {row['id']}"
        )
    fingerprints[fingerprint] = row["id"]
    counts[split] = counts.get(split, 0) + 1
if set(counts) != {"train", "valid", "test"}:
    raise ValueError("all three splits must be nonempty")
print(json.dumps({"episodes": len(seen_ids), "splits": counts, "group_overlap": 0}))
