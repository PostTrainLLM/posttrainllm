#!/usr/bin/env python3
"""Check that the posttrainllm docs golden path is present and wired."""

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
        "techniques/audit-inventory.md",
        "external-products-reviewed.md",
        "learning-pipeline.md",
        "learning-progress.md",
        "history-coverage-audit.md",
        "exactness-completion-audit.md",
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
        "## Evidence Standard",
        "## Status Vocabulary",
        "attempts.json",
        "## SQL Specialist Attempts",
        "## Pace Planner / Clarify Attempts",
        "Hygiene SimPO/DPO",
        "SQL candidate selection",
        "## Browser Product / Demo Attempts",
        "Browser WebGPU export serialization",
        "## Runtime / Browser / Architecture Attempts",
        "Speculative-decoding heads Medusa/EAGLE smoke",
        "Browser WebGPU training loop",
        "CPU speedup bundle",
        "StreamingLLM + KIVI cache compression",
        "## Factory / Documentation Attempts",
    ],
        "docs/history-coverage-audit.md": [
        "## Current Structured Coverage",
        "## Confidence Coverage",
        "## Classified Non-Ledger / Partial Surfaces",
        "## Classified Historical Sources",
        "## Backfill Rule",
        "Browser product",
        "docs/qa_log.md",
        "Runtime/perf",
        "MoE architecture smoke",
        "docs/cpu_speedup_results.md",
        "docs/streaming_llm_kivi.md",
        "docs/audit_2026.md",
        "docs/speculative_heads.md",
    ],
    "docs/external-products-reviewed.md": [
        "## Review Standard",
        "## Reviewed Sources",
        "TrainLoop AI",
        "Baseten",
        "## Required Review Before A New Target",
    ],
    "docs/learning-pipeline.md": [
        "## Ground-Up Master Roadmap",
        "## Factory-Attached Learning Sequence",
        "## Current Practical Curriculum",
        "math intuition -> tiny neural net -> training loop -> transformer",
        "Candidate Selection",
        "Preference Tuning Failure",
    ],
    "docs/learning-progress.md": [
        "## Ground-Up Roadmap Progress",
        "## Factory Lab Progress",
        "Eval design",
        "RLVR / ReST / OAPL",
        "## Completion Criteria",
    ],
    "docs/learn/curriculum.md": [
        "## 10/10 Bar",
        "## Master Roadmap",
        "## Checkpoint Template",
        "Mastery Gate",
        "self-improving factory",
    ],
    "docs/docs-quality-audit.md": [
        "## Definition",
        "## Current State",
        "## Completion Audit",
        "## Future Hardening",
        "## Next Quality Gates",
    ],
    "docs/exactness-completion-audit.md": [
        "## Completion Standard",
        "## Evidence",
        "## Current Counts",
        # Attempt counts are derived from docs/attempts.json below, not pinned
        # here -- three copies of the same number is three places to go stale.
        # check_attempt_ledger.py owns validating the audit tables themselves.
        "| Tracked audit rows | 83 |",
        "## Non-Blocking Future Hardening",
        "## Verification",
        "## Verdict",
    ],
    "docs/factory/enforcement.md": [
        "## Enforcement Layers",
        "## Publish Check",
        "posttrainllm factory-run publish-check",
        "scripts/check_factory_run_publish.py",
    ],
    "docs/factory/run-lifecycle.md": [
        "run-status.json",
        "decision.json",
        "expected-revision",
        "current-run.json",
        "latest-run.json",
        "active-with-warning",
        "--import-legacy",
        "reconcile --write",
    ],
    "docs/techniques/README.md": [
        "method -> recipe -> experiment -> result -> next recipe",
        "audit-inventory.md",
        "sql-technique-backlog.md",
        "../attempt-ledger.md",
    ],
    "docs/techniques/audit-inventory.md": [
        "## Inventory Standard",
        "## Coverage Summary",
        "| Keep/default | 45 |",
        "| Experimental | 8 |",
        "| Flagged | 30 |",
        "| Delete | 0 |",
        "| **Tracked audit rows** | **83** |",
        "## Duplicate / Overlap Notes",
        "YOCO",
        "BPE-dropout",
        "## Keep / Default Rows",
        "## Experimental Rows",
        "## Flagged Rows",
        "## Delete Rows",
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

    # Derive attempt counts from the structured index so they cannot go stale.
    import json
    from collections import Counter

    attempts = json.loads(
        (ROOT / "docs/attempts.json").read_text(encoding="utf-8")
    )["attempts"]
    completion_rel = "docs/exactness-completion-audit.md"
    completion = (ROOT / completion_rel).read_text(encoding="utf-8")
    exact = Counter(a["failure_reason_confidence"] for a in attempts)["exact"]
    for row in (
        f"| Total attempts | {len(attempts)} |",
        f"| Exact confidence | {exact} |",
    ):
        if row not in completion:
            errors.append(f"{completion_rel}: missing {row!r} (derived from attempts.json)")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("docs world-class check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
