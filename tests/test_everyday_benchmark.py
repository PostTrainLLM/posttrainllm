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
AUTOCORRECT_TASK_PATH = ROOT / "configs/everyday-benchmark/tasks/text-correction-preservation-v1.json"
AUTOCORRECT_INSTANCES_PATH = ROOT / "evals/everyday-benchmark/fixtures/autocorrect-public-dev-v1.json"
FILE_OPS_TASK_PATH = ROOT / "configs/everyday-benchmark/tasks/local-file-operations-v1.json"
FILE_OPS_INSTANCES_PATH = ROOT / "evals/everyday-benchmark/fixtures/file-ops-public-dev-v1.json"
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


def test_three_qualified_task_families_validate():
    suite = load(SUITE_PATH)
    pairs = [
        (load(TASK_PATH), load(INSTANCES_PATH)),
        (load(AUTOCORRECT_TASK_PATH), load(AUTOCORRECT_INSTANCES_PATH)),
        (load(FILE_OPS_TASK_PATH), load(FILE_OPS_INSTANCES_PATH)),
    ]
    assert len(suite["task_refs"]) == suite["publication"]["minimum_qualified_task_families"] == 3
    for task, instances in pairs:
        assert task["status"] == "qualified"
        assert task["frontier_qualification"]["state"] == "passed"
        assert not validate(task), validate(task)
        assert not validate(instances), validate(instances)


def test_generic_text_and_verdict_outputs_use_the_declared_scorer_fields():
    suite = load(SUITE_PATH)
    entry = load(ENTRY_DIR / "generalist-fixture-v1.json")
    for task_path, instances_path in (
        (AUTOCORRECT_TASK_PATH, AUTOCORRECT_INSTANCES_PATH),
        (FILE_OPS_TASK_PATH, FILE_OPS_INSTANCES_PATH),
    ):
        task = load(task_path)
        instances = load(instances_path)
        expected_field = task["scorer"]["expected_field"]
        prediction_field = task["scorer"]["prediction_field"]
        predictions = {
            "artifact_type": "prediction_set",
            "contract_version": "everyday-benchmark/v1",
            "prediction_set_id": f"{task['task_id']}-fixture-predictions",
            "revision": "1",
            "task_ref": {"id": task["task_id"], "revision": task["revision"]},
            "entry_ref": {"id": entry["entry_id"], "revision": entry["revision"]},
            "instance_set_ref": {"id": instances["instance_set_id"], "revision": instances["revision"]},
            "outputs": [
                {
                    "instance_id": instance["id"],
                    "pass_index": 1,
                    prediction_field: instance[expected_field],
                    "latency_ms": 1.0,
                    "error": None,
                    "routing": None,
                }
                for instance in instances["instances"]
            ],
        }
        assert not validate(predictions), validate(predictions)
        runner.assert_identity(suite, task, entry, instances, predictions)
        runner.assert_complete_predictions(task, instances, predictions)
        _, result, receipt = runner.score(
            suite,
            task,
            entry,
            instances,
            predictions,
            f"{task['task_id']}-fixture-run",
            "2026-08-09T00:00:00Z",
        )
        assert result["scores"]["exact_accuracy"] == 1.0
        assert result["scores"]["unknown_recall"] is None
        assert receipt["aggregate"]["exact_accuracy"] == 1.0
        errors: list[str] = []
        checker.validate_bundle([suite, task, entry, instances, predictions], CONTRACT, errors)
        assert not errors, errors


def test_sealed_identity_and_privacy_safe_receipt():
    suite, task, public_instances, _, adapted, _ = fixtures()
    instances = copy.deepcopy(public_instances)
    instances["instance_set_id"] = task["official_instance_set"]["id"]
    instances["revision"] = task["official_instance_set"]["revision"]
    instances["layer"] = "sealed-official"
    task["official_instance_set"]["sha256"] = runner.sha256_json(instances)
    task["official_instance_set"]["count"] = len(instances["instances"])
    predictions = prediction_set(adapted, instances)
    runner.assert_identity(suite, task, adapted, instances, predictions)
    metadata = {
        "permitted_training_cutoff": "before sealed-set generation",
        "overlap_check": "normalized exact match against training corpus",
        "overlap_count": 0,
        "holder": "maintainer-local-custody",
        "replay_authority": "maintainer",
        "attestation": {"kind": "maintainer-review-v1", "value": "reviewed"},
    }
    _, _, receipt = runner.score(
        suite, task, adapted, instances, predictions, "sealed-fixture-run", "2026-08-04T00:00:00Z", metadata
    )
    assert receipt["evaluation_layer"] == "sealed-official"
    assert receipt["custody"]["instance_material_committed"] is False
    assert receipt["leakage"]["overlap_count"] == 0
    assert not validate(receipt), validate(receipt)
    task["official_instance_set"]["sha256"] = "wrong"
    assert any("lowercase SHA-256" in error for error in validate(task))
    try:
        runner.assert_identity(suite, task, adapted, instances, predictions)
    except ValueError as exc:
        assert "frozen hash/count" in str(exc)
    else:
        raise AssertionError("mismatched sealed instance set was accepted")


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
    assert metrics["first_hop_acceptance_rate"] == 48 / 56
    assert metrics["first_hop_accuracy"] == 1.0
    assert metrics["escalation_rate"] == 8 / 56
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
