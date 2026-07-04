#!/usr/bin/env python3
"""Check whether a factory run folder has enough evidence to publish."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "config.json",
    "dataset.json",
    "eval-baseline.json",
    "eval-candidate.json",
    "decision.json",
    "report.md",
    "train.log",
    "slice-metrics.json",
    "trace_review.md",
    "provenance.json",
]

ALLOWED_DECISIONS = {
    "ship",
    "reject",
    "retry-data",
    "retry-training",
    "retry-eval",
    "park",
}
ALLOWED_CONFIDENCE = {
    "exact",
    "inferred",
    "missing-evidence",
    "not-applicable",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - error path is printed for CLI use.
        raise ValueError(f"{path.name}: invalid JSON: {exc}") from exc


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir")
    p.add_argument(
        "--allow-report-only",
        action="store_true",
        help="Allow non-ship report artifacts with blockers. Ship decisions remain strict.",
    )
    args = p.parse_args()

    run = Path(args.run_dir)
    errors: list[str] = []
    require(run.is_dir(), f"{run}: not a directory", errors)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    for name in REQUIRED_FILES:
        require((run / name).is_file(), f"missing required file: {name}", errors)

    artifact_path = run / "artifact.json"
    if not args.allow_report_only:
        require(artifact_path.is_file(), "missing required file: artifact.json", errors)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    config = load_json(run / "config.json")
    dataset = load_json(run / "dataset.json")
    baseline = load_json(run / "eval-baseline.json")
    candidate = load_json(run / "eval-candidate.json")
    decision = load_json(run / "decision.json")
    slice_metrics = load_json(run / "slice-metrics.json")
    provenance = load_json(run / "provenance.json")
    report = (run / "report.md").read_text(encoding="utf-8")
    trace = (run / "trace_review.md").read_text(encoding="utf-8")
    artifact = load_json(artifact_path) if artifact_path.exists() else None

    require(nonempty(config.get("run_id")), "config.run_id is required", errors)
    require(nonempty(config.get("target")), "config.target is required", errors)
    require(nonempty(config.get("candidate", {}).get("method")), "config.candidate.method is required", errors)
    require(nonempty(config.get("eval", {}).get("primary")), "config.eval.primary is required", errors)

    counts = dataset.get("counts", {})
    require(counts.get("heldout_rows", 0) > 0, "dataset.counts.heldout_rows must be > 0", errors)
    require(dataset.get("sources"), "dataset.sources must not be empty", errors)

    for label, payload in (("baseline", baseline), ("candidate", candidate)):
        require(nonempty(payload.get("model_id")), f"{label}.model_id is required", errors)
        require(nonempty(payload.get("suite")), f"{label}.suite is required", errors)
        require(isinstance(payload.get("score"), (int, float)), f"{label}.score must be numeric", errors)
        require(nonempty(payload.get("command")), f"{label}.command is required", errors)

    decision_value = decision.get("decision")
    require(decision_value in ALLOWED_DECISIONS, f"decision.decision must be one of {sorted(ALLOWED_DECISIONS)}", errors)
    require(nonempty(decision.get("reason")), "decision.reason is required", errors)
    require(nonempty(decision.get("next_action")), "decision.next_action is required", errors)
    confidence = decision.get("failure_reason_confidence")
    require(confidence in ALLOWED_CONFIDENCE, "decision.failure_reason_confidence must be exact, inferred, missing-evidence, or not-applicable", errors)
    if decision_value == "ship":
        require(confidence == "not-applicable", "ship decision must use decision.failure_reason_confidence=not-applicable", errors)
    else:
        require(nonempty(decision.get("failure_reason")), "non-ship decision.failure_reason is required", errors)
        require(nonempty(decision.get("lesson")), "non-ship decision.lesson is required", errors)
        require(confidence != "not-applicable", "non-ship decision requires real failure_reason_confidence", errors)
    evidence_sources = decision.get("evidence_sources")
    require(isinstance(evidence_sources, list) and bool(evidence_sources), "decision.evidence_sources must be a non-empty list", errors)

    require("overall" in slice_metrics, "slice-metrics.json must contain overall", errors)
    require("slices" in slice_metrics, "slice-metrics.json must contain slices", errors)
    require("Trace Review" in trace or "trace review" in trace.lower(), "trace_review.md must be a trace review", errors)
    require(nonempty(provenance.get("schema_version")), "provenance.schema_version is required", errors)
    require(nonempty(provenance.get("renderer")), "provenance.renderer is required", errors)
    require(nonempty(provenance.get("git", {}).get("commit")), "provenance.git.commit is required", errors)
    require(provenance.get("commands", {}).get("baseline") == baseline.get("command"), "provenance.commands.baseline must match eval-baseline.command", errors)
    require(provenance.get("commands", {}).get("candidate") == candidate.get("command"), "provenance.commands.candidate must match eval-candidate.command", errors)
    require(bool(provenance.get("datasets")), "provenance.datasets must not be empty", errors)
    for idx, item in enumerate(provenance.get("datasets") or []):
        require(nonempty(item.get("path")), f"provenance.datasets[{idx}].path is required", errors)
        require(nonempty(item.get("sha256")), f"provenance.datasets[{idx}].sha256 is required", errors)

    for section in ("## Decision", "## Evidence / Exactness", "## Target", "## Data", "## Eval", "## Performance", "## Failures", "## Next Action"):
        require(section in report, f"report.md missing section: {section}", errors)

    if decision_value == "ship":
        require(artifact is not None, "ship decision requires artifact.json", errors)
        if artifact is not None:
            require(bool(artifact.get("shipped")), "ship decision requires artifact.shipped=true", errors)
            require(nonempty(artifact.get("package_dir")), "ship decision requires artifact.package_dir", errors)
        require(not decision.get("blocked_by"), "ship decision must not have blockers", errors)
    elif not args.allow_report_only:
        require(artifact is not None, "non-report-only publish requires artifact.json", errors)

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1

    print(f"factory publish check ok: {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
