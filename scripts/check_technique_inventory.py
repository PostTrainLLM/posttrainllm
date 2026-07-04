#!/usr/bin/env python3
"""Check that the audit technique inventory is internally consistent."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/techniques/audit-inventory.md"
AUDIT = ROOT / "docs/audit_2026.md"
COMPLETION = ROOT / "docs/exactness-completion-audit.md"

EXPECTED = {
    "Keep / Default Rows": ("Keep/default", 45),
    "Experimental Rows": ("Experimental", 8),
    "Flagged Rows": ("Flagged", 30),
    "Delete Rows": ("Delete", 0),
}


def table_count(text: str, heading: str) -> int:
    marker = f"## {heading}\n"
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"missing section {heading!r}")
    tail = text[start + len(marker) :]
    end = tail.find("\n## ")
    section = tail if end == -1 else tail[:end]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|")
        and "---" not in line
        and not line.startswith("| Area |")
        and not line.startswith("| Technique |")
    ]
    return len(rows)


def summary_count(text: str, label: str) -> int:
    match = re.search(rf"\| {re.escape(label)} \| (\d+) \|", text)
    if not match:
        raise ValueError(f"missing summary row {label!r}")
    return int(match.group(1))


def main() -> int:
    inventory = INVENTORY.read_text(encoding="utf-8")
    audit = AUDIT.read_text(encoding="utf-8")
    completion = COMPLETION.read_text(encoding="utf-8")
    errors: list[str] = []

    for heading, (label, expected) in EXPECTED.items():
        try:
            actual = table_count(inventory, heading)
            summary = summary_count(inventory, label)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if actual != expected:
            errors.append(f"{heading}: expected {expected} rows, found {actual}")
        if summary != actual:
            errors.append(f"{heading}: summary {summary} != table count {actual}")
        if f"| {label} | {actual} |" not in completion:
            errors.append(f"exactness completion audit has stale technique count for {label!r}")

    total = sum(count for _, count in EXPECTED.values())
    total_match = re.search(r"\| \*\*Tracked audit rows\*\* \| \*\*(\d+)\*\* \|", inventory)
    if not total_match:
        errors.append("missing tracked audit rows summary")
    elif int(total_match.group(1)) != total:
        errors.append(f"tracked audit rows summary {total_match.group(1)} != {total}")
    elif f"| Tracked audit rows | {total} |" not in completion:
        errors.append("exactness completion audit has stale tracked audit rows total")

    for needle in (
        "docs/techniques/audit-inventory.md",
        "83\ntracked audit rows",
        "docs/attempt-ledger.md",
    ):
        if needle not in audit:
            errors.append(f"docs/audit_2026.md missing exactness note needle {needle!r}")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("technique inventory check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
