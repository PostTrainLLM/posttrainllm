#!/usr/bin/env python3
"""Check whether a factory run folder has enough evidence to publish."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
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
ARTIFACT_KINDS = {"base-model", "adapter", "training-checkpoint", "deploy-package"}
ARTIFACT_RUNTIMES = {
    "native-tinygpt",
    "native-hf-load",
    "python-mlx",
    "mlx-lm",
    "ollama",
}
ARTIFACT_ACTIONS = {
    "resume-exactly",
    "warm-restart",
    "merge",
    "convert",
    "eval",
    "serve",
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


def safe_relative(value: Any) -> bool:
    if not nonempty(value):
        return False
    path = Path(str(value))
    return not path.is_absolute() and ".." not in path.parts


def iso8601(value: Any) -> bool:
    if not nonempty(value):
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def check_manifest_identity(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    resolved_artifact: Path,
    errors: list[str],
) -> tuple[dict[str, Any], Any]:
    require(
        manifest.get("schema_version") == 1,
        "artifact manifest schema_version must be 1",
        errors,
    )
    raw_identity = manifest.get("artifact")
    require(
        isinstance(raw_identity, dict),
        "artifact manifest artifact must be an object",
        errors,
    )
    identity = raw_identity if isinstance(raw_identity, dict) else {}
    require(
        nonempty(identity.get("id")),
        "artifact manifest artifact.id is required",
        errors,
    )
    require(
        identity.get("id") == artifact.get("artifact_id"),
        "artifact manifest id must match artifact.artifact_id",
        errors,
    )
    kind = manifest.get("kind")
    require(kind in ARTIFACT_KINDS, "artifact manifest kind is invalid", errors)
    require(
        kind == artifact.get("kind"),
        "artifact manifest kind must match artifact.kind",
        errors,
    )
    expected_path = "." if resolved_artifact.is_dir() else resolved_artifact.name
    require(
        manifest.get("artifact_path") == expected_path,
        f"artifact manifest artifact_path must be {expected_path}",
        errors,
    )
    raw_tokenizer = manifest.get("tokenizer")
    require(
        isinstance(raw_tokenizer, dict),
        "artifact manifest tokenizer must be an object",
        errors,
    )
    tokenizer = raw_tokenizer if isinstance(raw_tokenizer, dict) else {}
    require(
        nonempty(tokenizer.get("id")),
        "artifact manifest tokenizer.id is required",
        errors,
    )
    require(
        iso8601(manifest.get("created_at")),
        "artifact manifest created_at must be ISO-8601",
        errors,
    )
    return identity, kind


def check_manifest_history(manifest: dict[str, Any], errors: list[str]) -> None:
    history = manifest.get("history")
    require(
        isinstance(history, list) and 0 < len(history) <= 64,
        "artifact manifest history must contain 1-64 steps",
        errors,
    )
    blocked = (
        "bearer ",
        "token=",
        "password=",
        "secret=",
        "api_key=",
        "prompt=",
        "prompt:",
        "completion=",
        "completion:",
        "model_output",
        "model output",
    )
    for index, step in enumerate(history if isinstance(history, list) else []):
        if not isinstance(step, dict):
            errors.append(f"artifact manifest history[{index}] must be an object")
            continue
        require(
            nonempty(step.get("action")),
            f"artifact manifest history[{index}].action is required",
            errors,
        )
        require(
            nonempty(step.get("tool")),
            f"artifact manifest history[{index}].tool is required",
            errors,
        )
        detail = step.get("detail")
        if detail is None:
            continue
        detail_text = str(detail)
        require(
            len(detail_text) <= 512
            and "\n" not in detail_text
            and "\r" not in detail_text,
            f"artifact manifest history[{index}].detail must be one bounded line",
            errors,
        )
        require(
            not any(marker in detail_text.lower() for marker in blocked)
            and re.search(r"(?<![a-z0-9])hf_[a-z0-9]{16,}", detail_text.lower())
            is None,
            f"artifact manifest history[{index}].detail contains sensitive payload",
            errors,
        )


def check_manifest_receipts(manifest: dict[str, Any], errors: list[str]) -> None:
    receipts = manifest.get("receipts")
    require(
        isinstance(receipts, list) and len(receipts) <= 64,
        "artifact manifest receipts must contain at most 64 references",
        errors,
    )
    for index, receipt in enumerate(receipts if isinstance(receipts, list) else []):
        if not isinstance(receipt, dict):
            errors.append(f"artifact manifest receipts[{index}] must be an object")
            continue
        require(
            nonempty(receipt.get("kind")),
            f"artifact manifest receipts[{index}].kind is required",
            errors,
        )
        require(
            safe_relative(receipt.get("path")),
            f"artifact manifest receipts[{index}].path must be relative",
            errors,
        )


def check_manifest_binding(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    identity: dict[str, Any],
    kind: Any,
    action_values: list[Any],
    errors: list[str],
) -> None:
    raw_base = manifest.get("base")
    if raw_base is not None:
        require(
            isinstance(raw_base, dict),
            "artifact manifest base must be an object",
            errors,
        )
    base = raw_base if isinstance(raw_base, dict) else {}
    if kind == "adapter":
        require(
            nonempty(base.get("id")),
            "artifact manifest adapter base.id is required",
            errors,
        )
        require(
            nonempty(base.get("revision")) or nonempty(base.get("checkpoint")),
            "artifact manifest adapter base must pin revision or checkpoint",
            errors,
        )
    if nonempty(base.get("id")):
        require(
            base.get("id") == artifact.get("base_model"),
            "artifact manifest base must match artifact.base_model",
            errors,
        )
    if "resume-exactly" in action_values:
        raw_state = manifest.get("training_state")
        require(
            isinstance(raw_state, dict),
            "resume-exactly requires training_state",
            errors,
        )
        state = raw_state if isinstance(raw_state, dict) else {}
        require(
            nonempty(identity.get("checkpoint")),
            "resume-exactly requires artifact.checkpoint",
            errors,
        )
        require(
            all(state.get(key) is True for key in ("optimizer", "scheduler", "rng")),
            "resume-exactly requires optimizer, scheduler, and RNG state",
            errors,
        )


def check_manifest_uses(
    manifest: dict[str, Any],
    artifact: dict[str, Any],
    identity: dict[str, Any],
    kind: Any,
    errors: list[str],
) -> None:
    runtimes = manifest.get("runtimes")
    require(
        isinstance(runtimes, list) and bool(runtimes),
        "artifact manifest runtimes must not be empty",
        errors,
    )
    runtime_values = runtimes if isinstance(runtimes, list) else []
    require(
        all(
            isinstance(value, str) and value in ARTIFACT_RUNTIMES
            for value in runtime_values
        ),
        "artifact manifest runtime is invalid",
        errors,
    )
    actions = manifest.get("next")
    require(
        isinstance(actions, list) and bool(actions),
        "artifact manifest next must not be empty",
        errors,
    )
    action_values = actions if isinstance(actions, list) else []
    require(
        all(
            isinstance(value, str) and value in ARTIFACT_ACTIONS
            for value in action_values
        ),
        "artifact manifest next action is invalid",
        errors,
    )
    check_manifest_receipts(manifest, errors)
    check_manifest_binding(manifest, artifact, identity, kind, action_values, errors)


def check_artifact_lifecycle(
    run: Path, artifact: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    declared = artifact.get("lifecycle_manifest")
    raw_artifact_path = str(artifact.get("path", ""))
    resolved_artifact = Path(raw_artifact_path).expanduser()
    if not resolved_artifact.is_absolute():
        resolved_artifact = run / resolved_artifact
    expected_sidecar = (
        resolved_artifact / "artifact-manifest.json"
        if resolved_artifact.is_dir()
        else Path(str(resolved_artifact) + ".artifact-manifest.json")
    )
    if not nonempty(declared):
        if expected_sidecar.exists():
            errors.append(
                f"artifact.lifecycle_manifest must reference {expected_sidecar.name}"
            )
        else:
            warnings.append(
                "legacy artifact has no lifecycle manifest; lifecycle/base verification is unavailable"
            )
        return
    declared_path = Path(str(declared))
    require(
        safe_relative(declared) and len(declared_path.parts) == 1,
        "artifact.lifecycle_manifest must name the adjacent sidecar",
        errors,
    )
    require(
        declared_path.name == expected_sidecar.name,
        f"artifact.lifecycle_manifest must be {expected_sidecar.name}",
        errors,
    )
    if not expected_sidecar.is_file():
        errors.append(f"missing required file: {declared_path.name}")
        return
    try:
        manifest = load_json(expected_sidecar)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if not isinstance(manifest, dict):
        errors.append("artifact manifest must be a JSON object")
        return
    identity, kind = check_manifest_identity(
        manifest, artifact, resolved_artifact, errors
    )
    check_manifest_history(manifest, errors)
    check_manifest_uses(manifest, artifact, identity, kind, errors)


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
    warnings: list[str] = []
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
    if artifact is not None and not isinstance(artifact, dict):
        errors.append("artifact.json must contain a JSON object")
    if isinstance(artifact, dict):
        check_artifact_lifecycle(run, artifact, errors, warnings)

    require(nonempty(config.get("run_id")), "config.run_id is required", errors)
    require(nonempty(config.get("target")), "config.target is required", errors)
    require(
        nonempty(config.get("candidate", {}).get("method")),
        "config.candidate.method is required",
        errors,
    )
    require(
        nonempty(config.get("eval", {}).get("primary")),
        "config.eval.primary is required",
        errors,
    )

    counts = dataset.get("counts", {})
    require(
        counts.get("heldout_rows", 0) > 0,
        "dataset.counts.heldout_rows must be > 0",
        errors,
    )
    require(dataset.get("sources"), "dataset.sources must not be empty", errors)

    for label, payload in (("baseline", baseline), ("candidate", candidate)):
        require(
            nonempty(payload.get("model_id")), f"{label}.model_id is required", errors
        )
        require(nonempty(payload.get("suite")), f"{label}.suite is required", errors)
        require(
            isinstance(payload.get("score"), (int, float)),
            f"{label}.score must be numeric",
            errors,
        )
        require(
            nonempty(payload.get("command")), f"{label}.command is required", errors
        )

    decision_value = decision.get("decision")
    require(
        decision_value in ALLOWED_DECISIONS,
        f"decision.decision must be one of {sorted(ALLOWED_DECISIONS)}",
        errors,
    )
    require(nonempty(decision.get("reason")), "decision.reason is required", errors)
    require(
        nonempty(decision.get("next_action")),
        "decision.next_action is required",
        errors,
    )
    confidence = decision.get("failure_reason_confidence")
    require(
        confidence in ALLOWED_CONFIDENCE,
        "decision.failure_reason_confidence must be exact, inferred, missing-evidence, or not-applicable",
        errors,
    )
    if decision_value == "ship":
        require(
            confidence == "not-applicable",
            "ship decision must use decision.failure_reason_confidence=not-applicable",
            errors,
        )
    else:
        require(
            nonempty(decision.get("failure_reason")),
            "non-ship decision.failure_reason is required",
            errors,
        )
        require(
            nonempty(decision.get("lesson")),
            "non-ship decision.lesson is required",
            errors,
        )
        require(
            confidence != "not-applicable",
            "non-ship decision requires real failure_reason_confidence",
            errors,
        )
    evidence_sources = decision.get("evidence_sources")
    require(
        isinstance(evidence_sources, list) and bool(evidence_sources),
        "decision.evidence_sources must be a non-empty list",
        errors,
    )

    require(
        "overall" in slice_metrics, "slice-metrics.json must contain overall", errors
    )
    require("slices" in slice_metrics, "slice-metrics.json must contain slices", errors)
    require(
        "Trace Review" in trace or "trace review" in trace.lower(),
        "trace_review.md must be a trace review",
        errors,
    )
    require(
        nonempty(provenance.get("schema_version")),
        "provenance.schema_version is required",
        errors,
    )
    require(
        nonempty(provenance.get("renderer")), "provenance.renderer is required", errors
    )
    require(
        nonempty(provenance.get("git", {}).get("commit")),
        "provenance.git.commit is required",
        errors,
    )
    require(
        provenance.get("commands", {}).get("baseline") == baseline.get("command"),
        "provenance.commands.baseline must match eval-baseline.command",
        errors,
    )
    require(
        provenance.get("commands", {}).get("candidate") == candidate.get("command"),
        "provenance.commands.candidate must match eval-candidate.command",
        errors,
    )
    require(
        bool(provenance.get("datasets")),
        "provenance.datasets must not be empty",
        errors,
    )
    for idx, item in enumerate(provenance.get("datasets") or []):
        require(
            nonempty(item.get("path")),
            f"provenance.datasets[{idx}].path is required",
            errors,
        )
        require(
            nonempty(item.get("sha256")),
            f"provenance.datasets[{idx}].sha256 is required",
            errors,
        )

    for section in (
        "## Decision",
        "## Evidence / Exactness",
        "## Target",
        "## Data",
        "## Eval",
        "## Performance",
        "## Failures",
        "## Next Action",
    ):
        require(section in report, f"report.md missing section: {section}", errors)

    if decision_value == "ship":
        require(
            isinstance(artifact, dict), "ship decision requires artifact.json", errors
        )
        if isinstance(artifact, dict):
            require(
                bool(artifact.get("shipped")),
                "ship decision requires artifact.shipped=true",
                errors,
            )
            require(
                nonempty(artifact.get("package_dir")),
                "ship decision requires artifact.package_dir",
                errors,
            )
        require(
            not decision.get("blocked_by"),
            "ship decision must not have blockers",
            errors,
        )
    elif not args.allow_report_only:
        require(
            artifact is not None,
            "non-report-only publish requires artifact.json",
            errors,
        )

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    print(f"factory publish check ok: {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
