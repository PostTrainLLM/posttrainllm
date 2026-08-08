#!/usr/bin/env python3
"""Run the no-model Everyday Specialist Benchmark path.

V1 foundation execution accepts imported predictions for a local package,
OpenAI-compatible endpoint, standalone imported entry, or capability graph. It
never invokes those backends, reads credentials, loads a model, or trains. Live
execution remains an explicit future adapter mode; this script defines and
validates all four entry contracts while scoring only caller-supplied outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import check_everyday_benchmark as checker

RUNNER_REF = {"id": "everyday-benchmark-no-model-runner", "revision": "1"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def ref(identifier: str, revision: str) -> dict[str, str]:
    return {"id": identifier, "revision": revision}


def load_and_validate(path: Path, expected_type: str, contract: dict[str, Any]) -> dict[str, Any]:
    value = checker.load_json(path)
    errors: list[str] = []
    checker.validate_artifact(value, contract, errors)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    if value.get("artifact_type") != expected_type:
        raise ValueError(f"{path}: expected {expected_type}, found {value.get('artifact_type')!r}")
    return value


def assert_identity(
    suite: dict[str, Any],
    task: dict[str, Any],
    entry: dict[str, Any],
    instances: dict[str, Any],
    predictions: dict[str, Any],
) -> None:
    task_key = (task["task_id"], task["revision"])
    suite_tasks = {(item["task_id"], item["revision"]) for item in suite["task_refs"]}
    if task_key not in suite_tasks:
        raise ValueError(f"task {task_key} is not referenced by suite")
    expected_task_ref = ref(*task_key)
    expected_entry_ref = ref(entry["entry_id"], entry["revision"])
    expected_instance_ref = ref(instances["instance_set_id"], instances["revision"])
    if instances["task_ref"] != expected_task_ref:
        raise ValueError("instance set task_ref does not match the selected task")
    if predictions["task_ref"] != expected_task_ref:
        raise ValueError("prediction task_ref does not match the selected task")
    if predictions["entry_ref"] != expected_entry_ref:
        raise ValueError("prediction entry_ref does not match the selected entry")
    if predictions["instance_set_ref"] != expected_instance_ref:
        raise ValueError("prediction instance_set_ref does not match the selected instance set")
    task_instance = task["instance_set"] if instances["layer"] == "public-development" else task["official_instance_set"]
    if (task_instance["id"], task_instance["revision"], task_instance["layer"]) != (
        instances["instance_set_id"],
        instances["revision"],
        instances["layer"],
    ):
        raise ValueError("task and instance-set identity are incompatible")
    if instances["layer"] == "sealed-official":
        actual_hash = sha256_json(instances)
        if task_instance["sha256"] != actual_hash or task_instance["count"] != len(instances["instances"]):
            raise ValueError("sealed instance set does not match the task's frozen hash/count")


def assert_complete_predictions(task: dict[str, Any], instances: dict[str, Any], predictions: dict[str, Any]) -> None:
    repetitions = task["repetitions"]
    expected = {
        (instance["id"], pass_index)
        for instance in instances["instances"]
        for pass_index in range(1, repetitions + 1)
    }
    actual = {(output["instance_id"], output["pass_index"]) for output in predictions["outputs"]}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(f"prediction coverage mismatch: missing={missing}, extra={extra}")
    maximum = task["budgets"]["max_input_bytes"]
    oversize = [
        instance["id"]
        for instance in instances["instances"]
        if len(instance["input_text"].encode("utf-8")) > maximum
    ]
    if oversize:
        raise ValueError(f"instances exceed max_input_bytes={maximum}: {oversize}")


def with_derived_resources(resources: list[dict[str, Any]], outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    copied = [dict(item) for item in resources]
    by_name = {item["name"]: item for item in copied}
    latencies = [float(item["latency_ms"]) for item in outputs]
    by_name["latency_warm_end_to_end_ms"].update(
        state="derived",
        value=statistics.fmean(latencies),
        unit="ms",
        source="imported per-output latency mean",
    )
    by_name["evaluation_time_seconds"].update(
        state="derived",
        value=sum(latencies) / 1000.0,
        unit="seconds",
        source="sum of imported per-output latency",
    )
    return copied


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def system_metrics(outputs: list[dict[str, Any]], expected_by_id: dict[str, str]) -> dict[str, Any]:
    false_accepts = 0
    accepted = 0
    first_hop_accepted = 0
    first_hop_correct = 0
    route_matches = 0
    regrets: list[float] = []
    escalated = 0
    should_escalate = 0
    escalation_true_positive = 0
    over_escalated = 0
    hops: Counter[str] = Counter()
    tiers: Counter[str] = Counter()
    exhaustion: Counter[str] = Counter()
    resource_rows: list[dict[str, Any]] = []
    for output in outputs:
        routing = output.get("routing")
        required = {
            "eligible_nodes",
            "selected_node",
            "best_eligible_node",
            "accepted",
            "escalated",
            "should_escalate",
            "route_regret",
            "hops",
            "final_tier",
            "exhaustion",
        }
        optional = {"binding", "resource_evidence"}
        if not isinstance(routing, dict) or not required.issubset(routing) or set(routing) - required - optional:
            raise ValueError(f"system output {output['instance_id']} must provide the exact routing trace contract")
        if not isinstance(routing["eligible_nodes"], list) or not routing["eligible_nodes"]:
            raise ValueError(f"system output {output['instance_id']} eligible_nodes must be non-empty")
        if routing["selected_node"] not in routing["eligible_nodes"] or routing["best_eligible_node"] not in routing["eligible_nodes"]:
            raise ValueError(f"system output {output['instance_id']} selected/best node is not eligible")
        if not checker.is_number(routing["route_regret"]) or routing["route_regret"] < 0:
            raise ValueError(f"system output {output['instance_id']} route_regret must be non-negative")
        if not isinstance(routing["hops"], int) or isinstance(routing["hops"], bool) or routing["hops"] < 1:
            raise ValueError(f"system output {output['instance_id']} hops must be positive")
        if not all(isinstance(routing[field], bool) for field in ("accepted", "escalated", "should_escalate")):
            raise ValueError(f"system output {output['instance_id']} routing flags must be booleans")
        if "binding" in routing:
            binding = routing["binding"]
            required_binding = {
                "graph_id", "graph_revision", "graph_sha256", "policy_id",
                "policy_revision", "policy_sha256", "trace_contract_version",
                "invoked_node_ids", "invoked_package_ids", "verifier_ids",
            }
            if not isinstance(binding, dict) or set(binding) != required_binding:
                raise ValueError(f"system output {output['instance_id']} graph binding is invalid")
            if not isinstance(binding["invoked_node_ids"], list) or not binding["invoked_node_ids"]:
                raise ValueError(f"system output {output['instance_id']} invoked_node_ids must be non-empty")
            if not isinstance(binding["invoked_package_ids"], list) or len(binding["invoked_package_ids"]) != len(binding["invoked_node_ids"]):
                raise ValueError(f"system output {output['instance_id']} invoked_package_ids must align with invoked_node_ids")
            if not isinstance(binding["verifier_ids"], list):
                raise ValueError(f"system output {output['instance_id']} verifier_ids must be an array")
        if "resource_evidence" in routing:
            resource_evidence = routing["resource_evidence"]
            required_resources = {
                "latency_end_to_end_ms", "latency_mode", "loaded_bytes", "peak_resident_bytes",
                "max_active_parameters", "installed_bytes_touched", "shared_base_bytes_touched",
                "adapter_bytes_touched", "external_calls", "external_cost_usd",
            }
            if not isinstance(resource_evidence, dict) or set(resource_evidence) != required_resources:
                raise ValueError(f"system output {output['instance_id']} resource_evidence is invalid")
            if resource_evidence["latency_mode"] not in {"cold", "warm"}:
                raise ValueError(f"system output {output['instance_id']} resource_evidence.latency_mode must be cold or warm")
            nullable_resources = {"loaded_bytes", "peak_resident_bytes", "max_active_parameters", "shared_base_bytes_touched"}
            for field in required_resources - {"latency_mode"} - nullable_resources:
                if not checker.is_number(resource_evidence[field]) or resource_evidence[field] < 0:
                    raise ValueError(f"system output {output['instance_id']} resource_evidence.{field} must be non-negative")
            for field in nullable_resources:
                if resource_evidence[field] is not None and (
                    not checker.is_number(resource_evidence[field]) or resource_evidence[field] < 0
                ):
                    raise ValueError(f"system output {output['instance_id']} resource_evidence.{field} must be null or non-negative")
            resource_rows.append(resource_evidence)
        prediction_field = next(
            (field for field in ("predicted_label", "predicted_text", "predicted_verdict") if field in output),
            None,
        )
        correct = (
            output["error"] is None
            and prediction_field is not None
            and output[prediction_field] == expected_by_id[output["instance_id"]]
        )
        accepted += int(routing["accepted"])
        false_accepts += int(routing["accepted"] and not correct)
        first_hop_accepted += int(not routing["escalated"] and routing["accepted"])
        first_hop_correct += int(not routing["escalated"] and routing["accepted"] and correct)
        route_matches += int(routing["selected_node"] == routing["best_eligible_node"])
        regrets.append(float(routing["route_regret"]))
        escalated += int(routing["escalated"])
        should_escalate += int(routing["should_escalate"])
        escalation_true_positive += int(routing["escalated"] and routing["should_escalate"])
        over_escalated += int(routing["escalated"] and not routing["should_escalate"])
        hops[str(routing["hops"])] += 1
        tiers[str(routing["final_tier"])] += 1
        if routing["exhaustion"] is not None:
            exhaustion[str(routing["exhaustion"])] += 1
    resource_metrics = None
    if resource_rows:
        cold_latencies = [row["latency_end_to_end_ms"] for row in resource_rows if row["latency_mode"] == "cold"]
        warm_latencies = [row["latency_end_to_end_ms"] for row in resource_rows if row["latency_mode"] == "warm"]
        resource_metrics = {
            "latency_end_to_end_ms_mean": statistics.fmean(row["latency_end_to_end_ms"] for row in resource_rows),
            "latency_end_to_end_ms_max": max(row["latency_end_to_end_ms"] for row in resource_rows),
            "latency_cold_end_to_end_ms_mean": statistics.fmean(cold_latencies) if cold_latencies else None,
            "latency_warm_end_to_end_ms_mean": statistics.fmean(warm_latencies) if warm_latencies else None,
            "peak_resident_bytes": max((row["peak_resident_bytes"] for row in resource_rows if row["peak_resident_bytes"] is not None), default=None),
            "max_active_parameters": max((row["max_active_parameters"] for row in resource_rows if row["max_active_parameters"] is not None), default=None),
            "loaded_bytes_max": max((row["loaded_bytes"] for row in resource_rows if row["loaded_bytes"] is not None), default=None),
            "installed_bytes_touched_max": max(row["installed_bytes_touched"] for row in resource_rows),
            "shared_base_bytes_touched_max": max((row["shared_base_bytes_touched"] for row in resource_rows if row["shared_base_bytes_touched"] is not None), default=None),
            "adapter_bytes_touched_max": max(row["adapter_bytes_touched"] for row in resource_rows),
            "external_calls": sum(row["external_calls"] for row in resource_rows),
            "external_cost_usd": sum(row["external_cost_usd"] for row in resource_rows),
        }
    return {
        "false_accept_rate": safe_ratio(false_accepts, accepted),
        "first_hop_acceptance_rate": safe_ratio(first_hop_accepted, len(outputs)),
        "first_hop_accuracy": safe_ratio(first_hop_correct, first_hop_accepted),
        "escalation_rate": safe_ratio(escalated, len(outputs)),
        "route_accuracy": safe_ratio(route_matches, len(outputs)),
        "route_regret": statistics.fmean(regrets) if regrets else None,
        "escalation_precision": safe_ratio(escalation_true_positive, escalated),
        "escalation_recall": safe_ratio(escalation_true_positive, should_escalate),
        "over_escalation_rate": safe_ratio(over_escalated, len(outputs)),
        "hop_distribution": dict(sorted(hops.items())),
        "final_tier_distribution": dict(sorted(tiers.items())),
        "typed_exhaustion": dict(sorted(exhaustion.items())),
        "resource_metrics": resource_metrics,
    }


def score(
    suite: dict[str, Any],
    task: dict[str, Any],
    entry: dict[str, Any],
    instances: dict[str, Any],
    predictions: dict[str, Any],
    run_id: str,
    timestamp: str,
    official_metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    instance_hash = sha256_json(instances)
    instance_identity = {
        "id": instances["instance_set_id"],
        "revision": instances["revision"],
        "sha256": instance_hash,
        "count": len(instances["instances"]),
    }
    suite_ref = ref(suite["suite_id"], suite["revision"])
    task_ref = ref(task["task_id"], task["revision"])
    entry_ref = ref(entry["entry_id"], entry["revision"])
    scorer_ref = ref(task["scorer"]["id"], task["scorer"]["revision"])
    expected_field = task["scorer"]["expected_field"]
    prediction_field = task["scorer"]["prediction_field"]
    expected_by_id = {instance["id"]: instance[expected_field] for instance in instances["instances"]}
    slices_by_id = {instance["id"]: instance["slices"] for instance in instances["instances"]}

    correct = 0
    incorrect = 0
    output_errors: list[dict[str, Any]] = []
    slice_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    unknown_total = 0
    unknown_correct = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    predictions_by_instance: dict[str, list[str | None]] = defaultdict(list)
    for output in predictions["outputs"]:
        instance_id = output["instance_id"]
        expected = expected_by_id[instance_id]
        predicted = output.get(prediction_field)
        failed = output["error"] is not None
        is_correct = not failed and predicted == expected
        if task["labels"]:
            confusion[expected][predicted if not failed else "__error__"] += 1
        else:
            confusion["expected-output"]["__error__" if failed else ("match" if is_correct else "mismatch")] += 1
        correct += int(is_correct)
        incorrect += int(not failed and not is_correct)
        predictions_by_instance[instance_id].append(predicted if not failed else None)
        if failed:
            output_errors.append({
                "instance_id": instance_id,
                "pass_index": output["pass_index"],
                "type": "adapter-error",
                "message": output["error"],
            })
        for slice_name in slices_by_id[instance_id]:
            slice_counts[slice_name][0] += 1
            slice_counts[slice_name][1] += int(is_correct)
        if task["scorer"].get("unknown_label") is not None and expected == task["scorer"]["unknown_label"]:
            unknown_total += 1
            unknown_correct += int(is_correct)

    output_count = len(predictions["outputs"])
    consistent = sum(1 for labels in predictions_by_instance.values() if len(set(labels)) == 1)
    resources = with_derived_resources(entry["resources"], predictions["outputs"])
    counts = {
        "instances": len(instances["instances"]),
        "outputs": output_count,
        "correct": correct,
        "incorrect": incorrect,
        "errors": len(output_errors),
    }
    result_id = f"{run_id}-result"
    run = {
        "artifact_type": "run",
        "contract_version": task["contract_version"],
        "run_id": run_id,
        "revision": "1",
        "suite_ref": suite_ref,
        "task_ref": task_ref,
        "entry_ref": entry_ref,
        "instance_set": instance_identity,
        "runner": RUNNER_REF,
        "scorer": scorer_ref,
        "budgets": task["budgets"],
        "repetitions": task["repetitions"],
        "started_at": timestamp,
        "completed_at": timestamp,
        "status": "completed" if not output_errors else "failed",
    }
    result = {
        "artifact_type": "result",
        "contract_version": task["contract_version"],
        "result_id": result_id,
        "revision": "1",
        "run_ref": ref(run_id, "1"),
        "suite_ref": suite_ref,
        "task_ref": task_ref,
        "entry_ref": entry_ref,
        "track": entry["track"],
        "instance_set": instance_identity,
        "runner": RUNNER_REF,
        "scorer": scorer_ref,
        "counts": counts,
        "scores": {
            "exact_accuracy": correct / output_count,
            "unknown_recall": safe_ratio(unknown_correct, unknown_total),
            "confusion_matrix": {
                expected: dict(sorted(predicted.items()))
                for expected, predicted in sorted(confusion.items())
            },
        },
        "slices": {
            name: {
                "count": row[0],
                "correct": row[1],
                "accuracy": row[1] / row[0] if row[0] else None,
            }
            for name, row in sorted(slice_counts.items())
        },
        "reliability": {
            "repetitions": task["repetitions"],
            "consistent_instances": consistent,
            "consistency_rate": consistent / len(instances["instances"]),
        },
        "resources": resources,
        "system_metrics": system_metrics(predictions["outputs"], expected_by_id) if entry["track"] == "system" else None,
        "errors": output_errors,
    }
    result_hash = sha256_json(result)
    if instances["layer"] == "sealed-official":
        if official_metadata is None:
            raise ValueError("sealed official scoring requires --official-metadata")
        leakage = {
            "permitted_training_cutoff": official_metadata["permitted_training_cutoff"],
            "overlap_check": official_metadata["overlap_check"],
            "overlap_count": official_metadata["overlap_count"],
        }
        custody = {
            "holder": official_metadata["holder"],
            "instance_material_committed": False,
            "replay_authority": official_metadata["replay_authority"],
        }
        attestation = official_metadata["attestation"]
    else:
        leakage = {
            "permitted_training_cutoff": "public-development fixtures are visible",
            "overlap_check": "not-applicable-public-development",
            "overlap_count": 0,
        }
        custody = {
            "holder": "repository-public-fixture",
            "instance_material_committed": True,
            "replay_authority": "maintainer",
        }
        attestation = {"kind": "none-public-development", "value": None}
    receipt = {
        "artifact_type": "receipt",
        "contract_version": task["contract_version"],
        "receipt_id": f"{run_id}-receipt",
        "revision": "1",
        "evaluation_layer": instances["layer"],
        "suite_ref": suite_ref,
        "task_ref": task_ref,
        "entry_ref": entry_ref,
        "run_ref": ref(run_id, "1"),
        "result_ref": ref(result_id, "1"),
        "instance_set": instance_identity,
        "runner": RUNNER_REF,
        "scorer": scorer_ref,
        "frontier_qualification": task["frontier_qualification"],
        "leakage": leakage,
        "custody": custody,
        "aggregate": {
            "exact_accuracy": result["scores"]["exact_accuracy"],
            "unknown_recall": result["scores"]["unknown_recall"],
            "instance_count": counts["instances"],
            "output_count": counts["outputs"],
            "error_count": counts["errors"],
            "result_sha256": result_hash,
        },
        "attestation": attestation,
        "publication_authority": "manual",
    }
    return run, result, receipt


def write_outputs(out_dir: Path, artifacts: tuple[dict[str, Any], ...]) -> None:
    paths = [out_dir / name for name in ("run.json", "result.json", "receipt.json")]
    if any(path.exists() for path in paths):
        raise ValueError(f"refusing to overwrite benchmark artifacts in {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    for path, artifact in zip(paths, artifacts):
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_official_metadata(path: Path | None, layer: str) -> dict[str, Any] | None:
    if layer != "sealed-official":
        if path is not None:
            raise ValueError("--official-metadata is only valid for sealed-official runs")
        return None
    if path is None:
        raise ValueError("sealed-official runs require --official-metadata")
    value = checker.load_json(path)
    required = {
        "permitted_training_cutoff",
        "overlap_check",
        "overlap_count",
        "holder",
        "replay_authority",
        "attestation",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{path}: official metadata must contain exactly {sorted(required)}")
    for field in required - {"overlap_count", "attestation"}:
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{path}: {field} must be a non-empty string")
    if not isinstance(value["overlap_count"], int) or isinstance(value["overlap_count"], bool) or value["overlap_count"] < 0:
        raise ValueError(f"{path}: overlap_count must be a non-negative integer")
    attestation = value["attestation"]
    if not isinstance(attestation, dict) or set(attestation) != {"kind", "value"}:
        raise ValueError(f"{path}: attestation must contain exactly kind and value")
    if not isinstance(attestation["kind"], str) or not attestation["kind"].strip():
        raise ValueError(f"{path}: attestation.kind must be a non-empty string")
    if attestation["value"] is not None and (not isinstance(attestation["value"], str) or not attestation["value"].strip()):
        raise ValueError(f"{path}: attestation.value must be null or a non-empty string")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--entry", required=True, type=Path)
    parser.add_argument("--instances", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timestamp", required=True, help="Caller-supplied ISO timestamp for reproducible fixtures")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--official-metadata", type=Path, help="Private custody/leakage metadata for sealed-official runs")
    parser.add_argument("--dry-run", action="store_true", help="Validate and score without writing artifacts")
    args = parser.parse_args()
    try:
        contract = checker.load_contract()
        suite = load_and_validate(args.suite, "suite", contract)
        task = load_and_validate(args.task, "task", contract)
        entry = load_and_validate(args.entry, "entry", contract)
        instances = load_and_validate(args.instances, "instance_set", contract)
        predictions = load_and_validate(args.predictions, "prediction_set", contract)
        official_metadata = load_official_metadata(args.official_metadata, instances["layer"])
        bundle_errors: list[str] = []
        checker.validate_bundle([suite, task, entry, instances, predictions], contract, bundle_errors)
        if bundle_errors:
            raise ValueError("bundle validation failed: " + "; ".join(bundle_errors))
        assert_identity(suite, task, entry, instances, predictions)
        assert_complete_predictions(task, instances, predictions)
        artifacts = score(suite, task, entry, instances, predictions, args.run_id, args.timestamp, official_metadata)
        errors: list[str] = []
        for artifact in artifacts:
            checker.validate_artifact(artifact, contract, errors)
        checker.validate_bundle(list(artifacts), contract, errors)
        if errors:
            raise ValueError("generated artifact validation failed: " + "; ".join(errors))
        if not args.dry_run:
            write_outputs(args.out_dir, artifacts)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"everyday-benchmark run failed: {exc}", file=sys.stderr)
        return 1
    action = "validated" if args.dry_run else f"wrote {args.out_dir}"
    print(f"everyday-benchmark: {action}; no model or provider invoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
