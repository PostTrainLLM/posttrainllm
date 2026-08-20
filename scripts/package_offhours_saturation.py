#!/usr/bin/env python3
"""Capture or verify the frozen OffHours Devin saturation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import offhours_core as core

CALIBRATIONS = core.ROOT / "evals" / "offhours" / "calibrations"
RECEIPT_PATH = CALIBRATIONS / "devin-glm-5.2-saturation-v1.json"
PASS_NAMES = ("pass1c", "pass2", "pass3")
ANSWER_PATHS = {
    name: CALIBRATIONS / f"devin-glm-5.2-pilot-v3-{name}-answers.json"
    for name in (*PASS_NAMES, "pass1b")
}
SOURCE_PATHS = {
    name: Path(f"/tmp/offhours-devin-v3-answers-{name}.json") for name in ANSWER_PATHS
}


def prompt_path(name: str) -> Path:
    return CALIBRATIONS / f"devin-glm-5.2-pilot-v3-{name}-prompt.md"


def relative(path: Path) -> str:
    return str(path.relative_to(core.ROOT))


def load_answers(path: Path) -> list[dict[str, Any]]:
    answers = core.load_json(path)
    if not isinstance(answers, list):
        raise TypeError(f"answer artifact must be an array: {path}")
    return answers


def grade(path: Path, claims: list[dict[str, Any]]) -> dict[str, Any]:
    answers = load_answers(path)
    by_id = {answer.get("claim_id"): answer for answer in answers}
    exact_schema = all(set(answer) == core.CLAIM_FIELDS for answer in answers)
    failures = []
    decision_correct = 0
    reason_correct = 0
    edge_correct = 0
    for row in claims:
        actual = by_id.get(row["task_id"])
        expected = row["expected"]
        decision_match = (
            actual is not None and actual.get("decision") == expected["decision"]
        )
        reason_match = (
            actual is not None and actual.get("reason_code") == expected["reason_code"]
        )
        decision_correct += decision_match
        reason_correct += reason_match
        edge_correct += row["edge_case"] and decision_match and reason_match
        if not decision_match or not reason_match:
            failures.append(
                {"task_id": row["task_id"], "expected": expected, "actual": actual}
            )
    malformed = (
        0
        if exact_schema and len(by_id) == len(answers) == len(claims)
        else len(answers)
    )
    return {
        "tasks": len(claims),
        "decision_correct": decision_correct,
        "decision_accuracy": decision_correct / len(claims),
        "reason_code_correct": reason_correct,
        "reason_code_accuracy": reason_correct / len(claims),
        "malformed": malformed,
        "edge_cases_correct": edge_correct,
        "edge_cases_total": sum(row["edge_case"] for row in claims),
        "failures": failures,
    }


def artifact(name: str) -> dict[str, Any]:
    answers = ANSWER_PATHS[name]
    prompt = prompt_path(name)
    return {
        "prompt_path": relative(prompt),
        "prompt_sha256": core.file_sha256(prompt),
        "answers_path": relative(answers),
        "answers_sha256": core.file_sha256(answers),
    }


def grade_passes(claims: list[dict[str, Any]]) -> tuple[list[dict], Counter]:
    passes: list[dict] = []
    failed_tasks: Counter[str] = Counter()
    for index, name in enumerate(PASS_NAMES, 1):
        result = grade(ANSWER_PATHS[name], claims)
        failed_tasks.update(item["task_id"] for item in result["failures"])
        passes.append(
            {
                "pass": index,
                "session_label": name,
                **artifact(name),
                **result,
                "passed_99_percent_gate": result["decision_accuracy"] >= 0.99
                and result["reason_code_accuracy"] >= 0.99
                and result["malformed"] == 0,
            }
        )
    return passes, failed_tasks


def aggregate(passes: list[dict]) -> dict[str, Any]:
    tasks = sum(item["tasks"] for item in passes)
    decisions = sum(item["decision_correct"] for item in passes)
    reasons = sum(item["reason_code_correct"] for item in passes)
    return {
        "tasks": tasks,
        "decision_correct": decisions,
        "decision_accuracy": decisions / tasks,
        "reason_code_correct": reasons,
        "reason_code_accuracy": reasons / tasks,
        "malformed": sum(item["malformed"] for item in passes),
        "edge_cases_correct": sum(item["edge_cases_correct"] for item in passes),
        "edge_cases_total": sum(item["edge_cases_total"] for item in passes),
        "sessions_passing_gate": sum(item["passed_99_percent_gate"] for item in passes),
        "sessions_failing_gate": sum(
            not item["passed_99_percent_gate"] for item in passes
        ),
    }


def excluded_attempts() -> list[dict[str, Any]]:
    invalid_schema = load_answers(ANSWER_PATHS["pass1b"])
    return [
        {
            "session_label": "pass1",
            "prompt_path": relative(prompt_path("pass1")),
            "prompt_sha256": core.file_sha256(prompt_path("pass1")),
            "outcome": "response_output_limit_before_answer_freeze",
            "answer_file_created": False,
        },
        {
            "session_label": "pass1b",
            **artifact("pass1b"),
            "outcome": "calibration_prompt_omitted_literal_output_field_names",
            "observed_fields": sorted(invalid_schema[0]),
            "use_for_saturation_decision": False,
        },
    ]


def build_receipt() -> dict[str, Any]:
    bundle = core.load_bundle(core.ROOT / "configs" / "offhours" / "pilot-v3.json")
    core.validate_bundle(bundle)
    passes, failed_tasks = grade_passes(bundle["claims"]["claims"])
    system_prompt = bundle["config"]["system_prompt"]
    return {
        "schema_version": "offhours/saturation-calibration/v1",
        "calibration_id": "devin-glm-5.2-v2-pass-v3-fail",
        "date": "2026-08-20",
        "calibrator": {
            "platform": "Devin CLI",
            "model": "glm-5.2",
            "reported_model": "GLM-5.2 High",
            "cli_version": "3000.4.25",
            "cli_revision": "7e8e528a",
        },
        "protocol": {
            "blind_before_freeze": True,
            "valid_sessions": 3,
            "tools_forbidden_before_freeze": True,
            "exact_output_fields": ["claim_id", "decision", "reason_code"],
            "session_gate": {
                "decision_accuracy_minimum": 0.99,
                "reason_code_accuracy_minimum": 0.99,
                "malformed_maximum": 0,
            },
            "hidden_reasoning_stored": False,
        },
        "passing_level": {
            "revision": "pilot-v2",
            "receipt_path": "evals/offhours/calibrations/devin-glm-5.2-pilot-v2.json",
            "config_sha256": core.file_sha256(
                core.ROOT / "configs" / "offhours" / "pilot-v2.json"
            ),
            "sessions_passed": 3,
            "sessions_total": 3,
            "decision_accuracy": 1.0,
            "reason_code_accuracy": 1.0,
        },
        "first_failing_level": {
            "revision": "pilot-v3",
            "benchmark_commit": "f945d758fdcbab1eebdbbb5e0a53ecbb357a28f7",
            "config_sha256": core.file_sha256(bundle["config_path"]),
            "claims_sha256": core.file_sha256(bundle["claims_path"]),
            "scenarios_sha256": core.file_sha256(bundle["scenarios_path"]),
            "system_prompt_sha256": hashlib.sha256(
                system_prompt.encode("utf-8")
            ).hexdigest(),
            "difficulty_increment": "foreign-currency receipt reconciliation, half-up integer conversion, tip eligibility, personal-share exclusion, and receipt-total guards",
            "passes": passes,
            "aggregate": aggregate(passes),
            "failed_task_frequency": dict(sorted(failed_tasks.items())),
        },
        "excluded_attempts": excluded_attempts(),
        "decision": {
            "status": "SATURATED_BOUNDARY_FOUND",
            "highest_reliable_revision": "pilot-v2",
            "first_reproducibly_failing_revision": "pilot-v3",
            "default_experiment_ruler": "pilot-v2",
            "advance_to_harder_level": False,
        },
    }


def capture() -> None:
    for name, source in SOURCE_PATHS.items():
        if not source.exists():
            raise ValueError(f"missing frozen source answer file: {source}")
        answers = load_answers(source)
        ANSWER_PATHS[name].write_text(
            json.dumps(answers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    RECEIPT_PATH.write_text(
        json.dumps(build_receipt(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check() -> None:
    actual = core.load_json(RECEIPT_PATH)
    expected = build_receipt()
    if actual != expected:
        raise ValueError(f"OffHours saturation receipt drift: {RECEIPT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    capture() if args.capture else check()
    print("OffHours saturation receipt: v2 passes, v3 fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
