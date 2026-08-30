#!/usr/bin/env python3
"""No-model tests for selective Pace cascade calibration and composition."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# scripts/ is grouped into topic subdirs; each is a flat import surface.
for _d in [
    ROOT / "scripts",
    *sorted(p for p in (ROOT / "scripts").iterdir() if p.is_dir()),
]:
    sys.path.insert(0, str(_d))

import calibrate_selective_cascade as cascade  # noqa: E402
import check_everyday_benchmark as checker  # noqa: E402
import run_everyday_benchmark as benchmark  # noqa: E402
import run_pace_intent_predictions as pace_predictions  # noqa: E402

POLICY_PATH = ROOT / "configs/everyday-benchmark/policies/pace-intent-selective-v1.json"
TASK_PATH = ROOT / "configs/everyday-benchmark/tasks/pace-intent-routing-v1.json"
SUITE_PATH = ROOT / "configs/everyday-benchmark/suite-v1.json"
INSTANCES_PATH = (
    ROOT / "evals/everyday-benchmark/fixtures/pace-intent-public-dev-v1.json"
)
SYSTEM_ENTRY_PATH = (
    ROOT / "configs/everyday-benchmark/entries/pace-intent-v8-qwen-cascade-v1.json"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wrong_label(expected: str, labels: list[str]) -> str:
    return next(label for label in labels if label != expected)


def prediction_set(
    instances: dict,
    *,
    entry_id: str,
    specialist_correct: int,
    separable_signals: bool,
) -> dict:
    labels = checker.load_contract()["enums"]["pace_intent_label"]
    outputs = []
    for index, instance in enumerate(instances["instances"]):
        is_correct = index < specialist_correct or entry_id != "pace-intent-router-v8"
        predicted = (
            instance["expected_label"]
            if is_correct
            else wrong_label(instance["expected_label"], labels)
        )
        for pass_index in (1, 2):
            output = {
                "instance_id": instance["id"],
                "pass_index": pass_index,
                "predicted_label": predicted,
                "latency_ms": 4.0 if entry_id == "pace-intent-router-v8" else 200.0,
                "error": None,
                "routing": None,
            }
            if entry_id == "pace-intent-router-v8":
                high = is_correct or not separable_signals
                output["decision_signals"] = {
                    "revision": "pace-softmax-summary-v1",
                    "max_probability": 0.99 if high else 0.4,
                    "margin": 0.98 if high else 0.01,
                    "normalized_entropy": 0.02 if high else 0.9,
                    "ood_score": None,
                }
            outputs.append(output)
    return {
        "artifact_type": "prediction_set",
        "contract_version": "everyday-benchmark/v1",
        "prediction_set_id": f"{entry_id}-fixture-predictions",
        "revision": "1",
        "task_ref": instances["task_ref"],
        "entry_ref": {"id": entry_id, "revision": "1"},
        "instance_set_ref": {
            "id": instances["instance_set_id"],
            "revision": instances["revision"],
        },
        "outputs": outputs,
    }


def inputs(*, specialist_correct: int, separable_signals: bool = True):
    policy = load(POLICY_PATH)
    task = load(TASK_PATH)
    instances = load(INSTANCES_PATH)
    system_entry = load(SYSTEM_ENTRY_PATH)
    specialist = prediction_set(
        instances,
        entry_id="pace-intent-router-v8",
        specialist_correct=specialist_correct,
        separable_signals=separable_signals,
    )
    fallback = prediction_set(
        instances,
        entry_id="qwen3-4b-instruct-2507-4bit",
        specialist_correct=len(instances["instances"]),
        separable_signals=True,
    )
    return policy, task, instances, specialist, fallback, system_entry


def validate(value: dict) -> list[str]:
    errors: list[str] = []
    checker.validate_artifact(value, checker.load_contract(), errors)
    return errors


def calibrate_fixture(*, specialist_correct: int, separable_signals: bool = True):
    policy, task, instances, specialist, fallback, system_entry = inputs(
        specialist_correct=specialist_correct,
        separable_signals=separable_signals,
    )
    cascade.validate_policy(policy)
    cascade.assert_identity(policy, task, instances, specialist, fallback, system_entry)
    local = cascade.collapse_predictions(specialist, require_signals=True)
    broad = cascade.collapse_predictions(fallback, require_signals=False)
    report = cascade.calibrate(policy, instances, local, broad)
    return policy, task, instances, specialist, fallback, system_entry, report


def test_softmax_summary_is_bounded_and_complete():
    probabilities = [0.7, 0.2, 0.05, 0.025, 0.015, 0.007, 0.003]
    rows = [
        {"tool": label, "prob": probability}
        for label, probability in zip(pace_predictions.LABELS, probabilities)
    ]
    signals = pace_predictions.summarize_specialist_predictions(rows)
    assert signals["revision"] == "pace-softmax-summary-v1"
    assert signals["max_probability"] == 0.7
    assert abs(signals["margin"] - 0.5) < 1e-12
    assert 0 <= signals["normalized_entropy"] <= 1
    assert signals["ood_score"] is None


def test_prediction_signal_contract_is_optional_but_fail_closed_when_present():
    _, _, _, specialist, _, _ = inputs(specialist_correct=26)
    assert not validate(specialist), validate(specialist)
    broken = copy.deepcopy(specialist)
    broken["outputs"][0]["decision_signals"]["max_probability"] = 1.1
    assert any("max_probability" in error for error in validate(broken))
    del specialist["outputs"][0]["decision_signals"]
    assert not validate(specialist), validate(specialist)


def test_feasible_policy_composes_graph_compatible_system_predictions():
    policy, task, instances, specialist, fallback, system_entry, report = (
        calibrate_fixture(specialist_correct=26)
    )
    assert report["decision"] == "calibrated"
    assert report["selected_policy"] is not None
    selected_metrics = report["selected_policy"]["metrics"]
    assert selected_metrics["specialist_accuracy"] == 26 / 28
    assert selected_metrics["first_hop_acceptance_rate"] == 26 / 28
    assert selected_metrics["first_hop_accuracy"] == 1.0
    assert selected_metrics["escalation_recall"] == 1.0
    assert selected_metrics["final_accuracy"] == 1.0
    assert report["component_metrics"]["specialist"]["accuracy"] == 26 / 28
    assert report["component_metrics"]["fallback"]["accuracy"] == 1.0
    assert report["component_metrics"]["perfect_router_oracle_accuracy"] == 1.0
    predictions = cascade.compose_system_predictions(
        policy, report, instances, specialist, fallback, system_entry
    )
    assert not validate(predictions), validate(predictions)
    assert {row["routing"]["hops"] for row in predictions["outputs"]} == {1, 2}
    suite = load(SUITE_PATH)
    _, result, _ = benchmark.score(
        suite,
        task,
        system_entry,
        instances,
        predictions,
        "selective-cascade-fixture",
        "2026-08-04T00:00:00Z",
    )
    metrics = result["system_metrics"]
    assert metrics["first_hop_acceptance_rate"] == 26 / 28
    assert metrics["first_hop_accuracy"] == 1.0
    assert metrics["escalation_rate"] == 2 / 28
    assert metrics["escalation_recall"] == 1.0
    assert result["scores"]["exact_accuracy"] == 1.0
    assert not validate(result), validate(result)


def test_infeasible_policy_reports_reject_and_emits_no_composition():
    policy, _, instances, specialist, fallback, system_entry, report = (
        calibrate_fixture(
            specialist_correct=14,
            separable_signals=False,
        )
    )
    assert report["decision"] == "no-feasible-policy"
    assert report["selected_policy"] is None
    assert report["selective_gate_candidate_count"] == 0
    assert "specialist_accuracy_min" in report["best_observed"]["gate_failures"]
    try:
        cascade.compose_system_predictions(
            policy, report, instances, specialist, fallback, system_entry
        )
    except ValueError as exc:
        assert "without a feasible policy" in str(exc)
    else:
        raise AssertionError("infeasible policy produced system predictions")


def test_calibration_refuses_sealed_layer():
    policy, task, instances, specialist, fallback, system_entry = inputs(
        specialist_correct=26
    )
    instances["layer"] = "sealed-official"
    try:
        cascade.assert_identity(
            policy, task, instances, specialist, fallback, system_entry
        )
    except ValueError as exc:
        assert "refuses non-public" in str(exc)
    else:
        raise AssertionError("sealed-official calibration was accepted")


def test_cli_writes_report_and_predictions_without_models():
    policy, task, instances, specialist, fallback, system_entry = inputs(
        specialist_correct=26
    )
    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        paths = {}
        for name, value in {
            "policy": policy,
            "task": task,
            "instances": instances,
            "specialist": specialist,
            "fallback": fallback,
            "system": system_entry,
        }.items():
            path = tmp / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        report_path = tmp / "report.json"
        predictions_path = tmp / "predictions.json"
        command = [
            sys.executable,
            str(ROOT / "scripts/research/calibrate_selective_cascade.py"),
            "--policy",
            str(paths["policy"]),
            "--task",
            str(paths["task"]),
            "--instances",
            str(paths["instances"]),
            "--specialist-predictions",
            str(paths["specialist"]),
            "--fallback-predictions",
            str(paths["fallback"]),
            "--system-entry",
            str(paths["system"]),
            "--out-report",
            str(report_path),
            "--out-predictions",
            str(predictions_path),
        ]
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
        assert completed.returncode == 0, completed.stderr
        report = load(report_path)
        assert report["decision"] == "calibrated"
        assert len(report["prediction_inputs"]) == 2
        assert all(len(item["sha256"]) == 64 for item in report["prediction_inputs"])
        assert not validate(load(predictions_path)), validate(load(predictions_path))


def main() -> int:
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"selective-cascade tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
