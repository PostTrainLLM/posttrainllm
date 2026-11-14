"""Emit review decisions, not training data or proof of answer correctness."""

import json
import sys
from pathlib import Path

seen_ids = set()
seen_content = set()
count = 0
for number, line in enumerate(Path(sys.argv[1]).read_text().splitlines(), 1):
    row = json.loads(line)
    key = row.get("id")
    if not isinstance(key, str) or not key or key in seen_ids:
        raise ValueError(f"line {number}: missing or duplicate id")
    seen_ids.add(key)
    reasons = []
    for field in ("prompt", "response", "source", "teacher_revision"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            reasons.append(f"missing_{field}")
    for field in ("license_reviewed", "private_data_reviewed", "verified"):
        if row.get(field) is not True:
            reasons.append(f"needs_{field}")
    if row.get("split") != "train":
        reasons.append("outside_training_split")
    fingerprint = (row.get("prompt"), row.get("response"))
    if not reasons and fingerprint in seen_content:
        reasons.append("duplicate_accepted_example")
    if not reasons:
        seen_content.add(fingerprint)
    print(json.dumps({"id": key, "accepted": not reasons, "reasons": reasons}))
    count += 1
if not count:
    raise ValueError("empty input")
