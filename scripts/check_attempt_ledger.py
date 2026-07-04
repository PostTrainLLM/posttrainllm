#!/usr/bin/env python3
"""Check that docs/attempt-ledger.md covers structured attempt metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUSES = {
    "worked",
    "worked-with-caveat",
    "failed",
    "regressed",
    "inconclusive",
    "not-tried",
}


def main() -> int:
    attempts_path = ROOT / "docs/attempts.json"
    ledger_path = ROOT / "docs/attempt-ledger.md"
    payload = json.loads(attempts_path.read_text(encoding="utf-8"))
    ledger = ledger_path.read_text(encoding="utf-8")
    errors: list[str] = []

    if payload.get("schema_version") != 1:
        errors.append("docs/attempts.json schema_version must be 1")

    seen: set[str] = set()
    for idx, attempt in enumerate(payload.get("attempts") or []):
        attempt_id = attempt.get("id")
        name = attempt.get("name")
        status = attempt.get("status")
        evidence = attempt.get("evidence")
        source = attempt.get("source")
        if not attempt_id or attempt_id in seen:
            errors.append(f"attempt[{idx}] has missing or duplicate id")
        seen.add(attempt_id)
        if status not in ALLOWED_STATUSES:
            errors.append(f"{attempt_id}: invalid status {status!r}")
        for field, value in (("name", name), ("evidence", evidence), ("source", source)):
            if not value:
                errors.append(f"{attempt_id}: missing {field}")
        if name and name not in ledger:
            errors.append(f"{attempt_id}: ledger missing name {name!r}")
        if status and f"`{status}`" not in ledger:
            errors.append(f"{attempt_id}: ledger missing status {status!r}")
        if evidence and evidence not in ledger:
            errors.append(f"{attempt_id}: ledger missing evidence {evidence!r}")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("attempt ledger check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
