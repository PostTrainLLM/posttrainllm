#!/usr/bin/env python3
"""Check that the TinyGPT docs golden path is present and wired."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED = {
    "docs/README.md": [
        "## Golden Path",
        "## Documentation Standard",
        "## Active vs Reference vs Archive",
        "attempt-ledger.md",
        "external-products-reviewed.md",
        "learning-pipeline.md",
        "learning-progress.md",
        "doc-status.md",
    ],
    "docs/doc-status.md": [
        "## Status Labels",
        "## Registry",
        "## Conflict Rule",
        "`active`",
        "`reference`",
        "`superseded`",
    ],
    "docs/attempt-ledger.md": [
        "## Status Vocabulary",
        "attempts.json",
        "## SQL Specialist Attempts",
        "Hygiene SimPO/DPO",
        "SQL candidate selection",
        "## Factory / Documentation Attempts",
    ],
    "docs/external-products-reviewed.md": [
        "## Review Standard",
        "## Reviewed Sources",
        "TrainLoop AI",
        "Baseten",
        "## Required Review Before A New Target",
    ],
    "docs/learning-pipeline.md": [
        "## Current Learning Sequence",
        "## Current Practical Curriculum",
        "Candidate Selection",
        "Preference Tuning Failure",
    ],
    "docs/learning-progress.md": [
        "## Modules",
        "Eval design",
        "RLVR / ReST / OAPL",
        "## Completion Criteria",
    ],
    "docs/docs-quality-audit.md": [
        "## Definition",
        "## Current State",
        "## Completion Audit",
        "## Future Hardening",
        "## Next Quality Gates",
    ],
    "docs/factory/enforcement.md": [
        "## Enforcement Layers",
        "## Publish Check",
        "tinygpt factory-run publish-check",
        "scripts/check_factory_run_publish.py",
    ],
    "docs/techniques/README.md": [
        "method -> recipe -> experiment -> result -> next recipe",
        "sql-technique-backlog.md",
        "../attempt-ledger.md",
    ],
    "docs/NEXT.md": [
        "docs/README.md",
        "docs/techniques/",
        "recipe",
        "slice-metrics.json",
        "trace_review.md",
    ],
    "PROJECT_STATUS.md": [
        "Docs hub",
        "Attempt ledger",
        "External review ledger",
        "Learning pipeline",
    ],
}


def main() -> int:
    errors: list[str] = []
    for rel, needles in REQUIRED.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"{rel}: missing {needle!r}")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("docs world-class check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
