#!/usr/bin/env python3
"""Focused stdlib tests for the Everyday Specialist Benchmark foundation."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_everyday_benchmark as checker  # noqa: E402
import run_everyday_benchmark as runner  # noqa: E402

CONTRACT = checker.load_contract()
SUITE_PATH = ROOT / "configs/everyday-benchmark/suite-v1.json"
TASK_PATH = ROOT / "configs/everyday-benchmark/tasks/pace-intent-routing-v1.json"
INSTANCES_PATH = ROOT / "evals/everyday-benchmark/fixtures/pace-intent-public-dev-v1.json"
ENTRY_DIR = ROOT / "evals/everyday-benchmark/fixtures/entries"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fixtures():
    return (
        load(SUITE_PATH),
        load(TASK_PATH),
        load(INSTANCES_PATH),
        load(ENTRY_DIR / "generalist-fixture-v1.json"),
        load(ENTRY_DIR / "adapted-fixture-v1.json"),
        load(ENTRY_DIR / "system-fixture-v1.json"),
    )


def prediction_set(entry: dict, instances: dict, *, system: bool = False) -> dict:
    outputs = []
    for instance in instances["instances"]:
        for pass_index in (1, 2):
            routing = None
            if system:
                should_escalate = instance["expected_label"] == "unknown"
                routing = {
                    "eligible_nodes": ["fixture-specialist@1", "fixture-generalist@1"],
                    "selected_node": "fixture-generalist@1" if should_escalate else "fixture-specialist@1",
                    "best_eligible_node": "fixture-generalist@1" if should_escalate else "fixture-specialist@1",
                    "accepted": True,
                    "escalated": should_escalate,
                    "should_escalate": should_escalate,
                    "route_regret": 0.0,
                    "hops": 2 if should_escalate else 1,
                    "final_tier": "generalist" if should_escalate else "specialist",
                    "exhaustion": None,
                }
            outputs.append(
                {
                    "instance_id": instance["id"],
                    "pass_index": pass_index,
                    "predicted_label": instance["expected_label"],
                    "latency_ms": 2.5,
                    "error": None,
                    "routing": routing,
                }
            )
    return {
        "artifact_type": "prediction_set",
        "contract_version": "everyday-benchmark/v1",
        "prediction_set_id": f"{entry['entry_id']}-predictions",
        "revision": "1",
        "task_ref": {"id": "pace-intent-routing", "revision": "1"},
        "entry_ref": {"id": entry["entry_id"], "revision": entry["revision"]},
        "instance_set_ref": {"id": instances["instance_set_id"], "revision": instances["revision"]},
        "outputs": outputs,
    }


def validate(value: dict) -> list[str]:
    errors: list[str] = []
    checker.validate_artifact(value, CONTRACT, errors)
    return errors


def valid_artifacts(entry_kind: str = "adapted"):
    suite, task, instances, generalist, adapted, system = fixtures()
    entry = {"generalist": generalist, "adapted": adapted, "system": system}[entry_kind]
    predictions = prediction_set(entry, instances, system=entry_kind == "system")
    runner.assert_identity(suite, task, entry, instances, predictions)
    runner.assert_complete_predictions(task, instances, predictions)
    artifacts = runner.score(
        suite,
        task,
        entry,
        instances,
        predictions,
        "fixture-run",
        "2026-08-04T00:00:00Z",
    )
    return suite, task, instances, entry, predictions, artifacts


def test_committed_contracts_and_all_tracks_validate():
    suite, task, instances, generalist, adapted, system = fixtures()
    for artifact in (suite, task, instances, generalist, adapted, system):
        assert not validate(artifact), (artifact.get("artifact_type"), validate(artifact))
    assert {generalist["track"], adapted["track"], system["track"]} == {"generalist", "adapted", "system"}
    assert Counter(item["expected_label"] for item in instances["instances"]) == Counter({label: 4 for label in task["labels"]})


def test_fail_closed_unknown_field_and_missing_adapted_disclosure():
    _, _, _, generalist, adapted, _ = fixtures()
    generalist["surprise"] = True
    assert any("unknown fields" in error for error in validate(generalist))
    del adapted["disclosure"]["training_sources"]
    assert any("training_sources" in error for error in validate(adapted))


def test_adapter_contracts_reject_embedded_credentials():
    _, _, _, generalist, _, _ = fixtures()
    generalist["adapter"] = {
        "kind": "openai-compatible",
        "base_url": "https://user:password@example.invalid/v1",
        "model": "fixture-model",
        "credential_env": "BENCHMARK_API_KEY",
    }
    errors = validate(generalist)
    assert any("must not embed credentials" in error for error in errors), errors


def test_all_four_adapter_interfaces_validate_without_invocation():
    suite, task, instances, generalist, _, _ = fixtures()
    adapters = [
        {"kind": "local-package", "package_id": "fixture-local@1", "command": "fixture-local --json"},
        {"kind": "openai-compatible", "base_url": "http://127.0.0.1:8080/v1", "model": "fixture-model", "credential_env": "BENCHMARK_API_KEY"},
        {"kind": "imported-predictions", "format": "everyday-benchmark/predictions-v1"},
        {"kind": "capability-graph", "graph_id": "fixture-graph", "graph_revision": "1", "policy_revision": "1", "format": "everyday-benchmark/predictions-v1"},
    ]
    for index, adapter in enumerate(adapters):
        entry = copy.deepcopy(generalist)
        entry["entry_id"] = f"adapter-fixture-{index}"
        entry["adapter"] = adapter
        assert not validate(entry), (adapter["kind"], validate(entry))
        predictions = prediction_set(entry, instances)
        runner.assert_identity(suite, task, entry, instances, predictions)
        artifacts = runner.score(suite, task, entry, instances, predictions, f"adapter-run-{index}", "2026-08-04T00:00:00Z")
        assert all(not validate(artifact) for artifact in artifacts)


def test_runner_requires_every_instance_and_repetition():
    suite, task, instances, entry, predictions, _ = valid_artifacts()
    predictions["outputs"].pop()
    try:
        runner.assert_complete_predictions(task, instances, predictions)
    except ValueError as exc:
        assert "coverage mismatch" in str(exc)
    else:
        raise AssertionError("incomplete repeated-pass predictions were accepted")
    runner.assert_identity(suite, task, entry, instances, prediction_set(entry, instances))


def test_score_is_deterministic_and_records_resource_math():
    _, _, _, _, _, artifacts = valid_artifacts()
    _, _, _, _, _, second = valid_artifacts()
    assert [runner.canonical_bytes(item) for item in artifacts] == [runner.canonical_bytes(item) for item in second]
    run, result, receipt = artifacts
    for artifact in artifacts:
        assert not validate(artifact), validate(artifact)
    assert run["status"] == "completed"
    assert result["scores"]["exact_accuracy"] == 1.0
    assert result["scores"]["unknown_recall"] == 1.0
    assert result["reliability"]["consistency_rate"] == 1.0
    assert result["scores"]["confusion_matrix"]["unknown"] == {"unknown": 8}
    resources = {item["name"]: item for item in result["resources"]}
    assert resources["latency_warm_end_to_end_ms"]["value"] == 2.5
    assert resources["evaluation_time_seconds"]["value"] == 0.14
    assert "outputs" not in receipt and "predictions" not in receipt


def test_result_rejects_inconsistent_derived_metrics():
    _, _, _, _, _, (_, result, _) = valid_artifacts()
    result["scores"]["exact_accuracy"] = 0.5
    result["slices"]["core"]["accuracy"] = 0.25
    errors = validate(result)
    assert any("inconsistent with counts" in error for error in errors), errors
    assert any("inconsistent with correct/count" in error for error in errors), errors


def test_receipt_rejects_private_or_credential_payloads():
    _, _, _, _, _, (_, _, receipt) = valid_artifacts()
    receipt["aggregate"]["raw_output"] = "private model material"
    errors = validate(receipt)
    assert any("denylisted from privacy-safe receipts" in error for error in errors), errors


def test_same_headline_rejects_incompatible_instance_sets():
    _, _, _, _, _, (_, first, _) = valid_artifacts("adapted")
    _, _, _, _, _, (_, second, _) = valid_artifacts("generalist")
    second["instance_set"]["sha256"] = "different"
    errors: list[str] = []
    checker.validate_bundle([first, second], CONTRACT, errors)
    assert any("headline-incompatible" in error for error in errors), errors


def test_system_trace_metrics_are_aggregated_and_validated():
    _, _, _, _, _, (_, result, _) = valid_artifacts("system")
    metrics = result["system_metrics"]
    assert metrics["false_accept_rate"] == 0.0
    assert metrics["route_accuracy"] == 1.0
    assert metrics["route_regret"] == 0.0
    assert metrics["escalation_precision"] == 1.0
    assert metrics["escalation_recall"] == 1.0
    assert metrics["hop_distribution"] == {"1": 48, "2": 8}
    assert not validate(result), validate(result)


def test_cli_writes_only_validated_no_model_artifacts():
    suite, task, instances, entry, predictions, _ = valid_artifacts()
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        predictions_path = tmp / "predictions.json"
        predictions_path.write_text(json.dumps(predictions), encoding="utf-8")
        out_dir = tmp / "out"
        command = [
            sys.executable,
            str(ROOT / "scripts/run_everyday_benchmark.py"),
            "--suite", str(SUITE_PATH),
            "--task", str(TASK_PATH),
            "--entry", str(ENTRY_DIR / "adapted-fixture-v1.json"),
            "--instances", str(INSTANCES_PATH),
            "--predictions", str(predictions_path),
            "--run-id", "fixture-cli-run",
            "--timestamp", "2026-08-04T00:00:00Z",
            "--out-dir", str(out_dir),
        ]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        generated = [load(out_dir / name) for name in ("run.json", "result.json", "receipt.json")]
        assert all(not validate(artifact) for artifact in generated)
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        assert second.returncode == 1
        assert "refusing to overwrite" in second.stderr
        assert suite and task and instances and entry


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"everyday-benchmark tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
