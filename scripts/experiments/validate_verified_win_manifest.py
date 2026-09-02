#!/usr/bin/env python3
"""Validate a verified-win experiment manifest before design review or execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "posttrainllm.verified-win.v1"
LANES = {"webgpu", "parakeet-asr", "rest-requalification", "needle-successor"}
DECISIONS = {"promote", "reject", "retry-protocol", "advance-model-class"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("manifest root must be an object")
    return value


def validate_common(data: dict[str, Any], stage: str, errors: list[str]) -> None:
    # lizard forgive -- declarative schema assertions are intentionally exhaustive.
    require(
        data.get("schema_version") == SCHEMA_VERSION,
        f"schema_version must be {SCHEMA_VERSION}",
        errors,
    )
    require(nonempty(data.get("manifest_id")), "manifest_id is required", errors)
    require(data.get("lane") in LANES, f"lane must be one of {sorted(LANES)}", errors)
    require(
        data.get("status") in {"design-frozen", "run-frozen", "completed"},
        "status must be design-frozen, run-frozen, or completed",
        errors,
    )
    require(nonempty(data.get("hypothesis")), "hypothesis is required", errors)

    comparison = data.get("comparison", {})
    require(comparison.get("paired") is True, "comparison.paired must be true", errors)
    require(
        nonempty(comparison.get("experimental_unit")),
        "comparison.experimental_unit is required",
        errors,
    )
    require(
        nonempty(comparison.get("replicate_unit")),
        "comparison.replicate_unit is required",
        errors,
    )
    require(
        isinstance(comparison.get("blocked_by"), list) and comparison.get("blocked_by"),
        "comparison.blocked_by must be a non-empty list",
        errors,
    )
    randomization = comparison.get("randomization", {})
    require(
        nonempty(randomization.get("method")),
        "comparison.randomization.method is required",
        errors,
    )
    require(
        isinstance(randomization.get("seed"), int),
        "comparison.randomization.seed must be an integer",
        errors,
    )

    arms = data.get("arms")
    require(
        isinstance(arms, list) and len(arms) >= 2,
        "arms must contain at least two entries",
        errors,
    )
    arm_ids = [arm.get("id") for arm in arms or [] if isinstance(arm, dict)]
    require(len(arm_ids) == len(set(arm_ids)), "arm ids must be unique", errors)
    for idx, arm in enumerate(arms or []):
        require(isinstance(arm, dict), f"arms[{idx}] must be an object", errors)
        if not isinstance(arm, dict):
            continue
        require(nonempty(arm.get("id")), f"arms[{idx}].id is required", errors)
        require(nonempty(arm.get("role")), f"arms[{idx}].role is required", errors)
        require(
            nonempty(arm.get("revision")) or arm.get("revision") is None,
            f"arms[{idx}].revision must be a string or null",
            errors,
        )

    fixtures = data.get("fixtures")
    require(
        isinstance(fixtures, list) and fixtures,
        "fixtures must be a non-empty list",
        errors,
    )
    for idx, fixture in enumerate(fixtures or []):
        require(nonempty(fixture.get("id")), f"fixtures[{idx}].id is required", errors)
        require(
            nonempty(fixture.get("path")) or fixture.get("path") is None,
            f"fixtures[{idx}].path must be a string or null",
            errors,
        )
        digest = fixture.get("sha256")
        require(
            digest is None or bool(SHA256_RE.fullmatch(str(digest))),
            f"fixtures[{idx}].sha256 must be a lowercase SHA-256 or null",
            errors,
        )
        require(
            fixture.get("visibility")
            in {"public-dev", "sealed-test", "generated-train", "source-config"},
            f"fixtures[{idx}].visibility is invalid",
            errors,
        )

    metrics = data.get("metrics")
    require(
        isinstance(metrics, list) and metrics,
        "metrics must be a non-empty list",
        errors,
    )
    require(
        any(metric.get("kind") == "primary" for metric in metrics or []),
        "metrics must include a primary gate",
        errors,
    )
    require(
        any(metric.get("kind") == "safety" for metric in metrics or []),
        "metrics must include a safety gate",
        errors,
    )
    for idx, metric in enumerate(metrics or []):
        require(nonempty(metric.get("id")), f"metrics[{idx}].id is required", errors)
        require(
            metric.get("kind")
            in {"primary", "quality", "safety", "regression", "resource"},
            f"metrics[{idx}].kind is invalid",
            errors,
        )
        require(
            nonempty(metric.get("gate")), f"metrics[{idx}].gate is required", errors
        )

    resources = data.get("resource_envelope", {})
    require(
        isinstance(resources.get("limits"), list) and resources.get("limits"),
        "resource_envelope.limits must be non-empty",
        errors,
    )
    require(
        nonempty(resources.get("stop_rule")),
        "resource_envelope.stop_rule is required",
        errors,
    )
    require(
        data.get("allowed_decisions") == sorted(DECISIONS),
        f"allowed_decisions must equal {sorted(DECISIONS)}",
        errors,
    )
    require(
        nonempty(data.get("raw_receipt_dir")), "raw_receipt_dir is required", errors
    )

    freeze = data.get("freeze", {})
    require(
        freeze.get("state") in {"design-frozen", "run-frozen", "completed"},
        "freeze.state is invalid",
        errors,
    )
    require(
        nonempty(freeze.get("protocol_version")),
        "freeze.protocol_version is required",
        errors,
    )
    require(
        isinstance(freeze.get("commands"), list) and freeze.get("commands"),
        "freeze.commands must be non-empty",
        errors,
    )

    if stage == "run":
        require(
            data.get("status") in {"run-frozen", "completed"},
            "run stage requires status run-frozen or completed",
            errors,
        )
        require(
            freeze.get("state") in {"run-frozen", "completed"},
            "run stage requires freeze.state run-frozen or completed",
            errors,
        )
        for idx, arm in enumerate(arms or []):
            require(
                nonempty(arm.get("revision")),
                f"run stage requires arms[{idx}].revision",
                errors,
            )
        for idx, fixture in enumerate(fixtures or []):
            require(
                nonempty(fixture.get("path")),
                f"run stage requires fixtures[{idx}].path",
                errors,
            )
            require(
                bool(SHA256_RE.fullmatch(str(fixture.get("sha256", "")))),
                f"run stage requires fixtures[{idx}].sha256",
                errors,
            )
            fixture_path = Path(str(fixture.get("path", "")))
            require(
                fixture_path.is_file(),
                f"run stage fixture does not exist: {fixture_path}",
                errors,
            )
            if fixture_path.is_file():
                actual_digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
                require(
                    actual_digest == fixture.get("sha256"),
                    f"run stage fixture hash mismatch: {fixture_path}",
                    errors,
                )
        for idx, command in enumerate(freeze.get("commands") or []):
            require(
                nonempty(command) and not str(command).startswith("TBD"),
                f"run stage requires executable freeze.commands[{idx}]",
                errors,
            )
        require(
            not freeze.get("open_requirements"),
            "run stage requires freeze.open_requirements to be empty",
            errors,
        )


def validate_lane(data: dict[str, Any], errors: list[str]) -> None:
    # lizard forgive -- one explicit assertion table per closed experiment lane.
    lane = data.get("lane")
    arm_ids = {arm.get("id") for arm in data.get("arms", [])}
    metric_ids = {metric.get("id") for metric in data.get("metrics", [])}
    comparison = data.get("comparison", {})
    resources = data.get("resource_envelope", {})
    limits = {
        item.get("id"): item.get("maximum") for item in resources.get("limits", [])
    }

    if lane == "webgpu":
        require(
            arm_ids == {"wasm", "webgpu"}, "webgpu arms must be wasm and webgpu", errors
        )
        require(
            comparison.get("sequence") == ["wasm", "webgpu", "webgpu", "wasm"],
            "webgpu sequence must be an alternated ABBA pair",
            errors,
        )
        require(
            comparison.get("reject_software_adapter") is True,
            "webgpu must reject software adapters",
            errors,
        )
        require(
            {"median_speedup", "final_loss_drift", "adapter_is_hardware"} <= metric_ids,
            "webgpu metrics are incomplete",
            errors,
        )
        require(
            limits.get("steps_per_arm") == 200,
            "webgpu steps_per_arm maximum must be 200",
            errors,
        )
    elif lane == "parakeet-asr":
        require(
            arm_ids == {"parakeet-browser", "native-incumbent"},
            "parakeet arms must be browser and native incumbent",
            errors,
        )
        require(
            comparison.get("same_audio_and_reference") is True,
            "parakeet comparison must pair the same audio and reference",
            errors,
        )
        require(
            {
                "wer_delta_points",
                "warm_realtime_factor",
                "repetition_regression",
                "proper_noun_accuracy",
            }
            <= metric_ids,
            "parakeet metrics are incomplete",
            errors,
        )
        require(
            limits.get("audio_minutes") == 30,
            "parakeet audio_minutes maximum must be 30",
            errors,
        )
        require(
            limits.get("network_gib") == 1,
            "parakeet network_gib maximum must be 1",
            errors,
        )
    elif lane == "rest-requalification":
        require(
            arm_ids == {"stock-4b", "rest-4b"},
            "ReST arms must be stock-4b and rest-4b",
            errors,
        )
        require(
            comparison.get("same_runtime_instance") is True,
            "ReST comparison must use the same runtime instance",
            errors,
        )
        require(
            comparison.get("candidate_weights_unchanged") is True,
            "ReST candidate weights must remain unchanged",
            errors,
        )
        require(
            {
                "frontier_ceiling",
                "file_ops_depth",
                "heldout_breadth_delta",
                "safety_regressions",
            }
            <= metric_ids,
            "ReST metrics are incomplete",
            errors,
        )
        require(
            limits.get("training_steps") == 0,
            "ReST requalification must allow zero training steps",
            errors,
        )
    elif lane == "needle-successor":
        require(len(arm_ids) == 4, "Needle must contain four factorial arms", errors)
        require(
            comparison.get("design") == "2x2-factorial",
            "Needle must use a 2x2 factorial design",
            errors,
        )
        require(
            comparison.get("independent_training_seeds") == 3,
            "Needle must use three independent training seeds",
            errors,
        )
        require(
            comparison.get("sealed_test_access") == "after-dev-selection-only",
            "Needle sealed test must stay inaccessible until dev selection",
            errors,
        )
        factor_pairs = {
            (
                arm.get("factors", {}).get("distractor_data"),
                arm.get("factors", {}).get("safety_training"),
            )
            for arm in data.get("arms", [])
        }
        require(
            factor_pairs
            == {(False, False), (False, True), (True, False), (True, True)},
            "Needle arms must cover the full distractor x safety factorial",
            errors,
        )
        require(
            {
                "tiny_overfit",
                "paired_exact_delta",
                "destructive_bypasses",
                "out_of_scope_false_actions",
                "risk_coverage_dominance",
            }
            <= metric_ids,
            "Needle metrics are incomplete",
            errors,
        )
        require(
            limits.get("gpu_hours") == 3, "Needle gpu_hours maximum must be 3", errors
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--stage", choices=("design", "run"), default="design")
    args = parser.parse_args()

    failed = False
    for path in args.manifests:
        errors: list[str] = []
        try:
            data = load(path)
            validate_common(data, args.stage, errors)
            validate_lane(data, errors)
        except ValueError as exc:
            errors.append(str(exc))
        if errors:
            failed = True
            print(f"{path}:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"ok: {path} ({args.stage})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
