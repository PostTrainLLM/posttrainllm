#!/usr/bin/env python3
"""Fail-closed validator for Everyday Specialist Benchmark V1 artifacts.

The validator is stdlib-only and reads the contract catalog in
``configs/everyday-benchmark/contracts-v1.json``. It validates individual
artifacts and, when several paths are supplied, their cross-artifact identity
and same-instance compatibility.

Exit codes: 0 clean, 1 validation failure, 2 IO/usage failure.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs/everyday-benchmark/contracts-v1.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_contract() -> dict[str, Any]:
    value = load_json(CONTRACT_PATH)
    if not isinstance(value, dict):
        raise ValueError("contract catalog must be an object")
    return value


def add(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def expect_object(value: Any, path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        add(errors, path, "must be an object")
        return None
    return value


def expect_fields(
    value: Any,
    path: str,
    required: Iterable[str],
    errors: list[str],
    optional: Iterable[str] = (),
) -> dict[str, Any] | None:
    obj = expect_object(value, path, errors)
    if obj is None:
        return None
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(obj))
    unknown = sorted(set(obj) - allowed)
    if missing:
        add(errors, path, f"missing fields: {', '.join(missing)}")
    if unknown:
        add(errors, path, f"unknown fields: {', '.join(unknown)}")
    return obj


def expect_string(value: Any, path: str, errors: list[str], *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        add(errors, path, "must be a non-empty string")


def expect_bool(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        add(errors, path, "must be a boolean")


def expect_enum(value: Any, allowed: Iterable[str], path: str, errors: list[str]) -> None:
    if value not in set(allowed):
        add(errors, path, f"must be one of {sorted(allowed)}")


def expect_ref(value: Any, path: str, errors: list[str]) -> None:
    obj = expect_fields(value, path, ("id", "revision"), errors)
    if obj:
        expect_string(obj.get("id"), f"{path}.id", errors)
        expect_string(obj.get("revision"), f"{path}.revision", errors)


def validate_measurements(value: Any, contract: dict[str, Any], path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        add(errors, path, "must be an array")
        return
    required_names = set(contract["required_resource_measurements"])
    states = contract["enums"]["measurement_state"]
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item_path = f"{path}[{index}]"
        item = expect_fields(raw, item_path, ("name", "state", "value", "unit", "source"), errors)
        if not item:
            continue
        name = item.get("name")
        if name not in required_names:
            add(errors, f"{item_path}.name", "is not a required V1 measurement")
        elif name in seen:
            add(errors, f"{item_path}.name", "is duplicated")
        elif isinstance(name, str):
            seen.add(name)
        state = item.get("state")
        expect_enum(state, states, f"{item_path}.state", errors)
        value_field = item.get("value")
        if state in {"measured", "derived", "historical"}:
            if not is_number(value_field) or value_field < 0:
                add(errors, f"{item_path}.value", "must be a finite non-negative number for this state")
        elif state in {"skipped", "missing", "not-applicable"} and value_field is not None:
            add(errors, f"{item_path}.value", "must be null when no measurement exists")
        expect_string(item.get("unit"), f"{item_path}.unit", errors)
        expect_string(item.get("source"), f"{item_path}.source", errors, nullable=True)
    missing = sorted(required_names - seen)
    if missing:
        add(errors, path, f"missing required measurements: {', '.join(missing)}")


def validate_suite(value: dict[str, Any], _contract: dict[str, Any], errors: list[str]) -> None:
    expect_string(value.get("suite_id"), "$.suite_id", errors)
    expect_string(value.get("revision"), "$.revision", errors)
    expect_string(value.get("title"), "$.title", errors)
    refs = value.get("task_refs")
    if not isinstance(refs, list) or not refs:
        add(errors, "$.task_refs", "must be a non-empty array")
    else:
        seen: set[tuple[str, str]] = set()
        for index, raw in enumerate(refs):
            path = f"$.task_refs[{index}]"
            ref = expect_fields(raw, path, ("task_id", "revision", "path"), errors)
            if not ref:
                continue
            key = (ref.get("task_id"), ref.get("revision"))
            if key in seen:
                add(errors, path, "duplicates a task reference")
            seen.add(key)
            for field in ("task_id", "revision", "path"):
                expect_string(ref.get(field), f"{path}.{field}", errors)
    publication = expect_fields(
        value.get("publication"),
        "$.publication",
        ("minimum_qualified_task_families", "headline_requires_same_instance_set", "default_view", "composite_score_authoritative"),
        errors,
    )
    if publication:
        minimum = publication.get("minimum_qualified_task_families")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            add(errors, "$.publication.minimum_qualified_task_families", "must be a positive integer")
        expect_bool(publication.get("headline_requires_same_instance_set"), "$.publication.headline_requires_same_instance_set", errors)
        expect_string(publication.get("default_view"), "$.publication.default_view", errors)
        expect_bool(publication.get("composite_score_authoritative"), "$.publication.composite_score_authoritative", errors)


def validate_task(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    enums = contract["enums"]
    for field in ("task_id", "revision", "title"):
        expect_string(value.get(field), f"$.{field}", errors)
    expect_enum(value.get("status"), enums["task_status"], "$.status", errors)
    adapter = expect_fields(value.get("adapter"), "$.adapter", ("id", "revision", "instruction_ref", "input_field", "output_field"), errors)
    if adapter:
        for field in adapter:
            expect_string(adapter[field], f"$.adapter.{field}", errors)
    scorer = expect_fields(
        value.get("scorer"),
        "$.scorer",
        ("id", "revision", "authority", "primary_metric", "expected_field", "prediction_field"),
        errors,
        optional=("unknown_label",),
    )
    if scorer:
        for field, item in scorer.items():
            expect_string(item, f"$.scorer.{field}", errors, nullable=field == "unknown_label")
    instance_set = expect_fields(value.get("instance_set"), "$.instance_set", ("id", "revision", "path", "layer"), errors)
    if instance_set:
        for field in ("id", "revision", "path"):
            expect_string(instance_set.get(field), f"$.instance_set.{field}", errors)
        expect_enum(instance_set.get("layer"), enums["evaluation_layer"], "$.instance_set.layer", errors)
    official = expect_fields(
        value.get("official_instance_set"),
        "$.official_instance_set",
        ("id", "revision", "layer", "sha256", "count", "custody_receipt_ref"),
        errors,
    )
    if official:
        for field in ("id", "revision", "sha256", "custody_receipt_ref"):
            expect_string(official.get(field), f"$.official_instance_set.{field}", errors)
        if official.get("layer") != "sealed-official":
            add(errors, "$.official_instance_set.layer", "must be sealed-official")
        count = official.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            add(errors, "$.official_instance_set.count", "must be a positive integer")
        if value.get("status") == "qualified" and not re.fullmatch(r"[0-9a-f]{64}", str(official.get("sha256", ""))):
            add(errors, "$.official_instance_set.sha256", "must be a lowercase SHA-256 when the task is qualified")
    labels = value.get("labels")
    if not isinstance(labels, list) or any(not isinstance(item, str) for item in labels):
        add(errors, "$.labels", "must be a string array")
    elif len(labels) != len(set(labels)):
        add(errors, "$.labels", "must not contain duplicates")
    if value.get("task_id") == "pace-intent-routing" and set(labels or []) != set(enums["pace_intent_label"]):
        add(errors, "$.labels", "must exactly match the Pace seven-class taxonomy")
    slices = expect_fields(value.get("slices"), "$.slices", ("primary", "protected"), errors)
    if slices:
        for name in ("primary", "protected"):
            if not isinstance(slices.get(name), list) or not slices[name] or any(not isinstance(item, str) for item in slices[name]):
                add(errors, f"$.slices.{name}", "must be a non-empty string array")
    budgets = expect_fields(
        value.get("budgets"),
        "$.budgets",
        ("timeout_ms_per_instance", "max_input_bytes", "max_output_labels", "tool_surface", "environment"),
        errors,
    )
    if budgets:
        for field in ("timeout_ms_per_instance", "max_input_bytes", "max_output_labels"):
            number = budgets.get(field)
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                add(errors, f"$.budgets.{field}", "must be a positive integer")
        expect_string(budgets.get("tool_surface"), "$.budgets.tool_surface", errors)
        expect_string(budgets.get("environment"), "$.budgets.environment", errors)
    repetitions = value.get("repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        add(errors, "$.repetitions", "must be a positive integer")
    frontier = expect_fields(value.get("frontier_qualification"), "$.frontier_qualification", ("state", "threshold", "model", "score", "receipt_ref"), errors)
    if frontier:
        state = frontier.get("state")
        expect_enum(state, enums["frontier_state"], "$.frontier_qualification.state", errors)
        threshold = frontier.get("threshold")
        if not is_number(threshold) or not 0 <= threshold <= 1:
            add(errors, "$.frontier_qualification.threshold", "must be between 0 and 1")
        if state == "passed":
            expect_string(frontier.get("model"), "$.frontier_qualification.model", errors)
            expect_string(frontier.get("receipt_ref"), "$.frontier_qualification.receipt_ref", errors)
            score = frontier.get("score")
            if not is_number(score) or score < threshold:
                add(errors, "$.frontier_qualification.score", "must meet the threshold when state is passed")
        elif state == "failed":
            expect_string(frontier.get("model"), "$.frontier_qualification.model", errors)
            expect_string(frontier.get("receipt_ref"), "$.frontier_qualification.receipt_ref", errors)
            score = frontier.get("score")
            if not is_number(score) or not 0 <= score < threshold:
                add(errors, "$.frontier_qualification.score", "must be below the threshold when state is failed")
        elif any(frontier.get(field) is not None for field in ("model", "score", "receipt_ref")):
            add(errors, "$.frontier_qualification", "model, score, and receipt_ref must be null when qualification is missing")
    policy = expect_fields(
        value.get("publication_policy"),
        "$.publication_policy",
        ("raw_public_development_instances_allowed", "raw_sealed_instances_allowed", "raw_model_outputs_in_receipt_allowed", "official_ranking_allowed"),
        errors,
    )
    if policy:
        for field, item in policy.items():
            expect_bool(item, f"$.publication_policy.{field}", errors)
        qualified = value.get("status") == "qualified" and frontier and frontier.get("state") == "passed"
        if policy.get("official_ranking_allowed") and not qualified:
            add(errors, "$.publication_policy.official_ranking_allowed", "requires qualified status and passed frontier gate")


def validate_adapter(value: Any, contract: dict[str, Any], path: str, errors: list[str]) -> None:
    obj = expect_object(value, path, errors)
    if not obj:
        return
    kind = obj.get("kind")
    expect_enum(kind, contract["enums"]["adapter_kind"], f"{path}.kind", errors)
    fields_by_kind = {
        "local-package": ("kind", "package_id", "command"),
        "openai-compatible": ("kind", "base_url", "model", "credential_env"),
        "imported-predictions": ("kind", "format"),
        "capability-graph": ("kind", "graph_id", "graph_revision", "policy_revision", "format"),
    }
    fields = fields_by_kind.get(kind)
    if not fields:
        return
    expect_fields(obj, path, fields, errors)
    for field in fields:
        expect_string(obj.get(field), f"{path}.{field}", errors)
    if kind == "openai-compatible":
        parsed = urlsplit(obj.get("base_url", ""))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            add(errors, f"{path}.base_url", "must be an http(s) endpoint")
        if parsed.username or parsed.password:
            add(errors, f"{path}.base_url", "must not embed credentials")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", obj.get("credential_env", "")):
            add(errors, f"{path}.credential_env", "must name an environment variable, never a credential value")


def validate_entry(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    for field in ("entry_id", "revision", "title"):
        expect_string(value.get(field), f"$.{field}", errors)
    track = value.get("track")
    expect_enum(track, contract["enums"]["track"], "$.track", errors)
    validate_adapter(value.get("adapter"), contract, "$.adapter", errors)
    validate_measurements(value.get("resources"), contract, "$.resources", errors)
    disclosure_fields = {
        "generalist": ("base_model", "benchmark_data_access"),
        "adapted": ("base", "training_sources", "permitted_benchmark_split", "row_count", "method", "training_time", "compute_cost"),
        "system": ("components", "graph_revision", "policy_revision"),
    }
    required = disclosure_fields.get(track)
    if required:
        disclosure = expect_fields(value.get("disclosure"), "$.disclosure", required, errors)
        if disclosure:
            for field in required:
                item = disclosure.get(field)
                if field == "row_count":
                    if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                        add(errors, f"$.disclosure.{field}", "must be a non-negative integer")
                elif field in {"training_sources", "components"}:
                    if not isinstance(item, list) or not item or any(not isinstance(part, str) or not part for part in item):
                        add(errors, f"$.disclosure.{field}", "must be a non-empty string array")
                else:
                    expect_string(item, f"$.disclosure.{field}", errors)
    evidence = value.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        add(errors, "$.evidence", "must be a non-empty array")
    else:
        for index, raw in enumerate(evidence):
            path = f"$.evidence[{index}]"
            item = expect_fields(raw, path, ("kind", "ref"), errors)
            if item:
                expect_enum(
                    item.get("kind"),
                    ("model-card", "report-card", "receipt", "package", "source"),
                    f"{path}.kind",
                    errors,
                )
                expect_string(item.get("ref"), f"{path}.ref", errors)


def validate_instance_set(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    for field in ("instance_set_id", "revision"):
        expect_string(value.get(field), f"$.{field}", errors)
    expect_ref(value.get("task_ref"), "$.task_ref", errors)
    expect_enum(value.get("layer"), contract["enums"]["evaluation_layer"], "$.layer", errors)
    provenance = expect_fields(value.get("provenance"), "$.provenance", ("kind", "generator", "generated_at", "review_status"), errors)
    if provenance:
        for field in provenance:
            expect_string(provenance[field], f"$.provenance.{field}", errors)
        if provenance.get("review_status") not in {"candidate", "reviewed"}:
            add(errors, "$.provenance.review_status", "must be candidate or reviewed")
    instances = value.get("instances")
    if not isinstance(instances, list) or not instances:
        add(errors, "$.instances", "must be a non-empty array")
        return
    expected_fields = ("expected_label", "expected_text", "expected_verdict")
    labels = set(contract["enums"]["pace_intent_label"])
    seen: set[str] = set()
    for index, raw in enumerate(instances):
        path = f"$.instances[{index}]"
        item = expect_fields(
            raw,
            path,
            ("id", "input_text", "slices", "boundary_rationale"),
            errors,
            optional=expected_fields,
        )
        if not item:
            continue
        instance_id = item.get("id")
        expect_string(instance_id, f"{path}.id", errors)
        if isinstance(instance_id, str):
            if instance_id in seen:
                add(errors, f"{path}.id", "is duplicated")
            seen.add(instance_id)
        expect_string(item.get("input_text"), f"{path}.input_text", errors)
        present = [field for field in expected_fields if field in item]
        if len(present) != 1:
            add(errors, path, f"must contain exactly one expected output field from {list(expected_fields)}")
        elif present[0] == "expected_label":
            expect_enum(item.get("expected_label"), labels, f"{path}.expected_label", errors)
        else:
            expect_string(item.get(present[0]), f"{path}.{present[0]}", errors)
        slices = item.get("slices")
        if not isinstance(slices, list) or not slices or any(not isinstance(part, str) or not part for part in slices):
            add(errors, f"{path}.slices", "must be a non-empty string array")
        expect_string(item.get("boundary_rationale"), f"{path}.boundary_rationale", errors)


def validate_prediction_set(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    for field in ("prediction_set_id", "revision"):
        expect_string(value.get(field), f"$.{field}", errors)
    for field in ("task_ref", "entry_ref", "instance_set_ref"):
        expect_ref(value.get(field), f"$.{field}", errors)
    outputs = value.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        add(errors, "$.outputs", "must be a non-empty array")
        return
    labels = contract["enums"]["pace_intent_label"]
    prediction_fields = ("predicted_label", "predicted_text", "predicted_verdict")
    seen: set[tuple[str, int]] = set()
    for index, raw in enumerate(outputs):
        path = f"$.outputs[{index}]"
        item = expect_fields(
            raw,
            path,
            ("instance_id", "pass_index", "latency_ms", "error", "routing"),
            errors,
            optional=("decision_signals", *prediction_fields),
        )
        if not item:
            continue
        expect_string(item.get("instance_id"), f"{path}.instance_id", errors)
        pass_index = item.get("pass_index")
        if not isinstance(pass_index, int) or isinstance(pass_index, bool) or pass_index < 1:
            add(errors, f"{path}.pass_index", "must be a positive integer")
        key = (item.get("instance_id"), pass_index)
        if key in seen:
            add(errors, path, "duplicates instance_id/pass_index")
        seen.add(key)
        error = item.get("error")
        present = [field for field in prediction_fields if field in item]
        if error is None:
            if len(present) != 1:
                add(errors, path, f"must contain exactly one predicted output field from {list(prediction_fields)}")
            elif present[0] == "predicted_label":
                expect_enum(item.get("predicted_label"), labels, f"{path}.predicted_label", errors)
            else:
                expect_string(item.get(present[0]), f"{path}.{present[0]}", errors)
        else:
            expect_string(error, f"{path}.error", errors)
            if any(item.get(field) is not None for field in present):
                add(errors, path, "predicted output must be null or omitted when error is present")
        latency = item.get("latency_ms")
        if not is_number(latency) or latency < 0:
            add(errors, f"{path}.latency_ms", "must be a finite non-negative number")
        if item.get("routing") is not None and not isinstance(item.get("routing"), dict):
            add(errors, f"{path}.routing", "must be an object or null")
        if "decision_signals" in item:
            signals = expect_fields(
                item.get("decision_signals"),
                f"{path}.decision_signals",
                ("revision", "max_probability", "margin", "normalized_entropy", "ood_score"),
                errors,
            )
            if signals:
                expect_string(signals.get("revision"), f"{path}.decision_signals.revision", errors)
                for field in ("max_probability", "margin", "normalized_entropy"):
                    signal = signals.get(field)
                    if not is_number(signal) or not 0 <= signal <= 1:
                        add(errors, f"{path}.decision_signals.{field}", "must be between 0 and 1")
                if (
                    is_number(signals.get("margin"))
                    and is_number(signals.get("max_probability"))
                    and signals["margin"] > signals["max_probability"]
                ):
                    add(errors, f"{path}.decision_signals.margin", "cannot exceed max_probability")
                ood_score = signals.get("ood_score")
                if ood_score is not None and (not is_number(ood_score) or ood_score < 0):
                    add(errors, f"{path}.decision_signals.ood_score", "must be null or non-negative")


def validate_run(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    expect_string(value.get("run_id"), "$.run_id", errors)
    expect_string(value.get("revision"), "$.revision", errors)
    for field in ("suite_ref", "task_ref", "entry_ref"):
        expect_ref(value.get(field), f"$.{field}", errors)
    instance = expect_fields(value.get("instance_set"), "$.instance_set", ("id", "revision", "sha256", "count"), errors)
    if instance:
        for field in ("id", "revision", "sha256"):
            expect_string(instance.get(field), f"$.instance_set.{field}", errors)
        if not isinstance(instance.get("count"), int) or isinstance(instance.get("count"), bool) or instance.get("count", -1) < 1:
            add(errors, "$.instance_set.count", "must be a positive integer")
    for field in ("runner", "scorer"):
        expect_ref(value.get(field), f"$.{field}", errors)
    if not isinstance(value.get("budgets"), dict):
        add(errors, "$.budgets", "must be an object")
    repetitions = value.get("repetitions")
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
        add(errors, "$.repetitions", "must be a positive integer")
    for field in ("started_at", "completed_at"):
        expect_string(value.get(field), f"$.{field}", errors)
    expect_enum(value.get("status"), contract["enums"]["run_status"], "$.status", errors)


def _validate_score_row(value: Any, path: str, errors: list[str]) -> None:
    row = expect_fields(value, path, ("count", "correct", "accuracy"), errors)
    if not row:
        return
    count = row.get("count")
    correct = row.get("correct")
    accuracy = row.get("accuracy")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        add(errors, f"{path}.count", "must be a non-negative integer")
    if not isinstance(correct, int) or isinstance(correct, bool) or correct < 0 or (isinstance(count, int) and correct > count):
        add(errors, f"{path}.correct", "must be an integer between zero and count")
    expected = correct / count if isinstance(count, int) and count > 0 and isinstance(correct, int) else None
    if expected is None:
        if accuracy is not None:
            add(errors, f"{path}.accuracy", "must be null when count is zero")
    elif not is_number(accuracy) or not math.isclose(accuracy, expected, rel_tol=0, abs_tol=1e-12):
        add(errors, f"{path}.accuracy", "is inconsistent with correct/count")


def validate_result(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    expect_string(value.get("result_id"), "$.result_id", errors)
    expect_string(value.get("revision"), "$.revision", errors)
    for field in ("run_ref", "suite_ref", "task_ref", "entry_ref", "runner", "scorer"):
        expect_ref(value.get(field), f"$.{field}", errors)
    expect_enum(value.get("track"), contract["enums"]["track"], "$.track", errors)
    instance = expect_fields(value.get("instance_set"), "$.instance_set", ("id", "revision", "sha256", "count"), errors)
    if instance:
        for field in ("id", "revision", "sha256"):
            expect_string(instance.get(field), f"$.instance_set.{field}", errors)
    counts = expect_fields(value.get("counts"), "$.counts", ("instances", "outputs", "correct", "incorrect", "errors"), errors)
    if counts:
        for field, item in counts.items():
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                add(errors, f"$.counts.{field}", "must be a non-negative integer")
        if all(isinstance(counts.get(field), int) for field in ("correct", "incorrect", "errors", "outputs")):
            if counts["correct"] + counts["incorrect"] + counts["errors"] != counts["outputs"]:
                add(errors, "$.counts", "correct + incorrect + errors must equal outputs")
    scores = expect_fields(value.get("scores"), "$.scores", ("exact_accuracy", "unknown_recall", "confusion_matrix"), errors)
    if scores and counts and counts.get("outputs"):
        expected = counts.get("correct", 0) / counts["outputs"]
        if not is_number(scores.get("exact_accuracy")) or not math.isclose(scores["exact_accuracy"], expected, rel_tol=0, abs_tol=1e-12):
            add(errors, "$.scores.exact_accuracy", "is inconsistent with counts")
        unknown_recall = scores.get("unknown_recall")
        if unknown_recall is not None and (not is_number(unknown_recall) or not 0 <= unknown_recall <= 1):
            add(errors, "$.scores.unknown_recall", "must be null or between 0 and 1")
        confusion = scores.get("confusion_matrix")
        if not isinstance(confusion, dict) or not confusion:
            add(errors, "$.scores.confusion_matrix", "must be a non-empty object")
        else:
            matrix_total = 0
            for expected_label, predicted_counts in confusion.items():
                if not isinstance(predicted_counts, dict) or not predicted_counts:
                    add(errors, f"$.scores.confusion_matrix.{expected_label}", "must be a non-empty object")
                    continue
                for predicted_label, count in predicted_counts.items():
                    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                        add(errors, f"$.scores.confusion_matrix.{expected_label}.{predicted_label}", "must be a non-negative integer")
                    else:
                        matrix_total += count
            if matrix_total != counts["outputs"]:
                add(errors, "$.scores.confusion_matrix", "counts must sum to output count")
    slices = value.get("slices")
    if not isinstance(slices, dict) or not slices:
        add(errors, "$.slices", "must be a non-empty object")
    else:
        for name, row in slices.items():
            _validate_score_row(row, f"$.slices.{name}", errors)
    reliability = expect_fields(value.get("reliability"), "$.reliability", ("repetitions", "consistent_instances", "consistency_rate"), errors)
    if reliability:
        repetitions = reliability.get("repetitions")
        consistent = reliability.get("consistent_instances")
        total = counts.get("instances") if counts else None
        if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
            add(errors, "$.reliability.repetitions", "must be a positive integer")
        if not isinstance(consistent, int) or isinstance(consistent, bool) or consistent < 0 or (isinstance(total, int) and consistent > total):
            add(errors, "$.reliability.consistent_instances", "must be between zero and instance count")
        expected = consistent / total if isinstance(total, int) and total > 0 and isinstance(consistent, int) else None
        if expected is not None and (not is_number(reliability.get("consistency_rate")) or not math.isclose(reliability["consistency_rate"], expected, rel_tol=0, abs_tol=1e-12)):
            add(errors, "$.reliability.consistency_rate", "is inconsistent with consistent_instances/instances")
    validate_measurements(value.get("resources"), contract, "$.resources", errors)
    if value.get("track") == "system":
        metrics = expect_fields(
            value.get("system_metrics"),
            "$.system_metrics",
            (
                "false_accept_rate",
                "first_hop_acceptance_rate",
                "first_hop_accuracy",
                "escalation_rate",
                "route_accuracy",
                "route_regret",
                "escalation_precision",
                "escalation_recall",
                "over_escalation_rate",
                "hop_distribution",
                "final_tier_distribution",
                "typed_exhaustion",
                "resource_metrics",
            ),
            errors,
        )
        if metrics:
            for field in (
                "false_accept_rate",
                "first_hop_acceptance_rate",
                "first_hop_accuracy",
                "escalation_rate",
                "route_accuracy",
                "escalation_precision",
                "escalation_recall",
                "over_escalation_rate",
            ):
                item = metrics.get(field)
                if item is not None and (not is_number(item) or not 0 <= item <= 1):
                    add(errors, f"$.system_metrics.{field}", "must be null or between 0 and 1")
            regret = metrics.get("route_regret")
            if regret is not None and (not is_number(regret) or regret < 0):
                add(errors, "$.system_metrics.route_regret", "must be null or non-negative")
            for field in ("hop_distribution", "final_tier_distribution", "typed_exhaustion"):
                if not isinstance(metrics.get(field), dict):
                    add(errors, f"$.system_metrics.{field}", "must be an object")
            resource_metrics = metrics.get("resource_metrics")
            if resource_metrics is not None:
                resource_metrics = expect_fields(
                    resource_metrics,
                    "$.system_metrics.resource_metrics",
                    (
                        "latency_end_to_end_ms_mean", "latency_end_to_end_ms_max",
                        "latency_cold_end_to_end_ms_mean", "latency_warm_end_to_end_ms_mean",
                        "loaded_bytes_max", "peak_resident_bytes", "max_active_parameters",
                        "installed_bytes_touched_max", "shared_base_bytes_touched_max",
                        "adapter_bytes_touched_max", "external_calls", "external_cost_usd",
                    ),
                    errors,
                )
                if resource_metrics:
                    for field, item in resource_metrics.items():
                        if item is not None and (not is_number(item) or item < 0):
                            add(errors, f"$.system_metrics.resource_metrics.{field}", "must be null or non-negative")
    elif value.get("system_metrics") is not None:
        add(errors, "$.system_metrics", "must be null outside the system track")
    if not isinstance(value.get("errors"), list) or any(not isinstance(item, dict) for item in value.get("errors", [])):
        add(errors, "$.errors", "must be an array of objects")


def walk_receipt_privacy(value: Any, contract: dict[str, Any], path: str, errors: list[str]) -> None:
    denylist = contract["receipt_denylisted_field_fragments"]
    string_limit = contract["limits"]["receipt_string_bytes"]
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in denylist):
                add(errors, f"{path}.{key}", "denylisted from privacy-safe receipts")
            walk_receipt_privacy(item, contract, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_receipt_privacy(item, contract, f"{path}[{index}]", errors)
    elif isinstance(value, str) and len(value.encode("utf-8")) > string_limit:
        add(errors, path, f"string exceeds {string_limit} byte receipt limit")


def validate_receipt(value: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    expect_string(value.get("receipt_id"), "$.receipt_id", errors)
    expect_string(value.get("revision"), "$.revision", errors)
    expect_enum(value.get("evaluation_layer"), contract["enums"]["evaluation_layer"], "$.evaluation_layer", errors)
    for field in ("suite_ref", "task_ref", "entry_ref", "run_ref", "result_ref", "runner", "scorer"):
        expect_ref(value.get(field), f"$.{field}", errors)
    instance = expect_fields(value.get("instance_set"), "$.instance_set", ("id", "revision", "sha256", "count"), errors)
    if instance:
        for field in ("id", "revision", "sha256"):
            expect_string(instance.get(field), f"$.instance_set.{field}", errors)
    frontier = expect_fields(value.get("frontier_qualification"), "$.frontier_qualification", ("state", "threshold", "model", "score", "receipt_ref"), errors)
    if frontier:
        expect_enum(frontier.get("state"), contract["enums"]["frontier_state"], "$.frontier_qualification.state", errors)
    leakage = expect_fields(value.get("leakage"), "$.leakage", ("permitted_training_cutoff", "overlap_check", "overlap_count"), errors)
    if leakage:
        expect_string(leakage.get("permitted_training_cutoff"), "$.leakage.permitted_training_cutoff", errors)
        expect_string(leakage.get("overlap_check"), "$.leakage.overlap_check", errors)
        if not isinstance(leakage.get("overlap_count"), int) or isinstance(leakage.get("overlap_count"), bool) or leakage.get("overlap_count", -1) < 0:
            add(errors, "$.leakage.overlap_count", "must be a non-negative integer")
    custody = expect_fields(value.get("custody"), "$.custody", ("holder", "instance_material_committed", "replay_authority"), errors)
    if custody:
        expect_string(custody.get("holder"), "$.custody.holder", errors)
        expect_bool(custody.get("instance_material_committed"), "$.custody.instance_material_committed", errors)
        expect_string(custody.get("replay_authority"), "$.custody.replay_authority", errors)
        if value.get("evaluation_layer") == "sealed-official" and custody.get("instance_material_committed"):
            add(errors, "$.custody.instance_material_committed", "must be false for sealed official evaluation")
    aggregate = expect_fields(value.get("aggregate"), "$.aggregate", ("exact_accuracy", "unknown_recall", "instance_count", "output_count", "error_count", "result_sha256"), errors)
    if aggregate:
        for field in ("exact_accuracy", "unknown_recall"):
            item = aggregate.get(field)
            if item is not None and (not is_number(item) or not 0 <= item <= 1):
                add(errors, f"$.aggregate.{field}", "must be null or between 0 and 1")
        for field in ("instance_count", "output_count", "error_count"):
            item = aggregate.get(field)
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                add(errors, f"$.aggregate.{field}", "must be a non-negative integer")
        expect_string(aggregate.get("result_sha256"), "$.aggregate.result_sha256", errors)
    attestation = expect_fields(value.get("attestation"), "$.attestation", ("kind", "value"), errors)
    if attestation:
        expect_string(attestation.get("kind"), "$.attestation.kind", errors)
        expect_string(attestation.get("value"), "$.attestation.value", errors, nullable=True)
    expect_enum(value.get("publication_authority"), contract["enums"]["publication_authority"], "$.publication_authority", errors)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > contract["limits"]["receipt_bytes"]:
        add(errors, "$", f"receipt exceeds {contract['limits']['receipt_bytes']} byte limit")
    walk_receipt_privacy(value, contract, "$", errors)


VALIDATORS = {
    "suite": validate_suite,
    "task": validate_task,
    "entry": validate_entry,
    "instance_set": validate_instance_set,
    "prediction_set": validate_prediction_set,
    "run": validate_run,
    "result": validate_result,
    "receipt": validate_receipt,
}


def validate_artifact(value: Any, contract: dict[str, Any], errors: list[str], *, source: str = "$") -> None:
    obj = expect_object(value, source, errors)
    if obj is None:
        return
    artifact_type = obj.get("artifact_type")
    catalog = contract.get("artifact_types", {})
    if artifact_type not in catalog:
        add(errors, source, f"unknown artifact_type {artifact_type!r}")
        return
    required = catalog[artifact_type]["required_fields"]
    expect_fields(obj, source, required, errors)
    if obj.get("contract_version") != contract.get("contract_version"):
        add(errors, f"{source}.contract_version", f"must be {contract.get('contract_version')!r}")
    VALIDATORS[artifact_type](obj, contract, errors)


def _artifact_ref(value: dict[str, Any]) -> tuple[str, str] | None:
    artifact_type = value.get("artifact_type")
    id_field = {
        "suite": "suite_id",
        "task": "task_id",
        "entry": "entry_id",
        "instance_set": "instance_set_id",
        "prediction_set": "prediction_set_id",
        "run": "run_id",
        "result": "result_id",
        "receipt": "receipt_id",
    }.get(artifact_type)
    if not id_field:
        return None
    revision = value.get("revision", "1")
    return value.get(id_field), str(revision)


def validate_bundle(values: list[dict[str, Any]], contract: dict[str, Any], errors: list[str]) -> None:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for value in values:
        by_type.setdefault(value.get("artifact_type", "unknown"), []).append(value)

    tasks = {_artifact_ref(item): item for item in by_type.get("task", [])}
    entries = {_artifact_ref(item): item for item in by_type.get("entry", [])}
    instance_sets = {_artifact_ref(item): item for item in by_type.get("instance_set", [])}
    for prediction in by_type.get("prediction_set", []):
        refs = (("task_ref", tasks), ("entry_ref", entries), ("instance_set_ref", instance_sets))
        for field, index in refs:
            ref = prediction.get(field, {})
            key = (ref.get("id"), ref.get("revision"))
            if index and key not in index:
                add(errors, f"prediction_set:{prediction.get('prediction_set_id')}.{field}", f"dangling reference {key}")
        instance_ref = prediction.get("instance_set_ref", {})
        instance_set = instance_sets.get((instance_ref.get("id"), instance_ref.get("revision")))
        if instance_set:
            expected_ids = {item.get("id") for item in instance_set.get("instances", [])}
            output_ids = {item.get("instance_id") for item in prediction.get("outputs", [])}
            unknown_ids = sorted(output_ids - expected_ids)
            if unknown_ids:
                add(errors, f"prediction_set:{prediction.get('prediction_set_id')}.outputs", f"unknown instance ids: {', '.join(unknown_ids)}")
        task_ref = prediction.get("task_ref", {})
        task = tasks.get((task_ref.get("id"), task_ref.get("revision")))
        if task and instance_set:
            expected_field = task.get("scorer", {}).get("expected_field")
            prediction_field = task.get("scorer", {}).get("prediction_field")
            if any(expected_field not in item for item in instance_set.get("instances", [])):
                add(errors, f"instance_set:{instance_set.get('instance_set_id')}.instances", f"missing task expected field {expected_field!r}")
            if any(
                output.get("error") is None and prediction_field not in output
                for output in prediction.get("outputs", [])
            ):
                add(errors, f"prediction_set:{prediction.get('prediction_set_id')}.outputs", f"missing task prediction field {prediction_field!r}")

    result_groups: dict[tuple[str, str], set[tuple[str, str, str, int]]] = {}
    for result in by_type.get("result", []):
        task_ref = result.get("task_ref", {})
        suite_ref = result.get("suite_ref", {})
        instance = result.get("instance_set", {})
        key = (suite_ref.get("id"), task_ref.get("id"))
        identity = (instance.get("id"), instance.get("revision"), instance.get("sha256"), instance.get("count"))
        result_groups.setdefault(key, set()).add(identity)
    for key, identities in result_groups.items():
        if len(identities) > 1:
            add(errors, "bundle.results", f"headline-incompatible instance sets for suite/task {key}: {sorted(identities)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSON artifacts to validate together")
    args = parser.parse_args()
    try:
        contract = load_contract()
        values = [load_json(path) for path in args.paths]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"everyday-benchmark validator IO error: {exc}", file=sys.stderr)
        return 2
    errors: list[str] = []
    for path, value in zip(args.paths, values):
        local: list[str] = []
        validate_artifact(value, contract, local)
        errors.extend(f"{path}: {item}" for item in local)
    validate_bundle([value for value in values if isinstance(value, dict)], contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"everyday-benchmark: validated {len(values)} artifact(s) against {contract['contract_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
