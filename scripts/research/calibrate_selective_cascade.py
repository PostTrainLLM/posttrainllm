#!/usr/bin/env python3
"""Calibrate a first-hop specialist cascade on public development evidence.

The tool consumes imported specialist and fallback predictions for the same
public instance set. It selects a deterministic threshold policy, emits a
privacy-safe aggregate report, and can compose graph-compatible system
predictions. It refuses sealed-official calibration and never invokes a model.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import check_everyday_benchmark as checker
import run_everyday_benchmark as benchmark


TARGET_FIELDS = {
    "specialist_accuracy_min",
    "first_hop_acceptance_rate_min",
    "first_hop_accuracy_min",
    "escalation_recall_min",
    "final_accuracy_min",
}
GRID_FIELDS = {"max_probability_min", "margin_min", "normalized_entropy_max"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def load_artifact(path: Path, artifact_type: str) -> dict[str, Any]:
    value = load_json(path)
    errors: list[str] = []
    checker.validate_artifact(value, checker.load_contract(), errors)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    if value.get("artifact_type") != artifact_type:
        raise ValueError(f"{path}: expected {artifact_type}")
    return value


def require_exact_fields(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing or unknown:
        raise ValueError(
            f"{label}: fields mismatch missing={missing} unknown={unknown}"
        )


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def validate_policy(value: dict[str, Any]) -> None:
    require_exact_fields(
        value,
        {
            "artifact_type",
            "contract_version",
            "policy_id",
            "revision",
            "task_ref",
            "calibration_layer",
            "ordered_nodes",
            "max_hops",
            "targets",
            "threshold_grid",
            "selection_objective",
            "official_policy",
        },
        "policy",
    )
    if value["artifact_type"] != "selective-routing-target":
        raise ValueError("policy.artifact_type must be selective-routing-target")
    if value["contract_version"] != "everyday-benchmark/v1":
        raise ValueError("policy.contract_version is unsupported")
    if value["calibration_layer"] != "public-development":
        raise ValueError("selective policy calibration must use public-development")
    if value["official_policy"] is not False:
        raise ValueError(
            "a calibrated development policy cannot declare itself official"
        )
    task_ref = value["task_ref"]
    if not isinstance(task_ref, dict) or set(task_ref) != {"id", "revision"}:
        raise ValueError("policy.task_ref must contain exactly id and revision")
    nodes = value["ordered_nodes"]
    if not isinstance(nodes, list) or len(nodes) < 2:
        raise ValueError(
            "policy.ordered_nodes must contain at least specialist and fallback"
        )
    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != {"id", "tier", "enabled"}:
            raise ValueError(f"policy.ordered_nodes[{index}] has invalid fields")
        if not isinstance(node["id"], str) or not node["id"] or node["id"] in node_ids:
            raise ValueError(
                f"policy.ordered_nodes[{index}].id must be unique and non-empty"
            )
        if not isinstance(node["tier"], str) or not node["tier"]:
            raise ValueError(f"policy.ordered_nodes[{index}].tier must be non-empty")
        if not isinstance(node["enabled"], bool):
            raise ValueError(f"policy.ordered_nodes[{index}].enabled must be boolean")
        node_ids.add(node["id"])
    if not nodes[0]["enabled"] or not nodes[1]["enabled"]:
        raise ValueError("the first specialist and fallback nodes must be enabled")
    max_hops = value["max_hops"]
    if (
        not isinstance(max_hops, int)
        or isinstance(max_hops, bool)
        or not 2 <= max_hops <= len(nodes)
    ):
        raise ValueError(
            "policy.max_hops must cover the enabled chain without exceeding node count"
        )
    targets = value["targets"]
    if not isinstance(targets, dict) or set(targets) != TARGET_FIELDS:
        raise ValueError(f"policy.targets must contain exactly {sorted(TARGET_FIELDS)}")
    for field, target in targets.items():
        if not checker.is_number(target) or not 0 <= target <= 1:
            raise ValueError(f"policy.targets.{field} must be between 0 and 1")
    grid = value["threshold_grid"]
    if not isinstance(grid, dict) or set(grid) != GRID_FIELDS:
        raise ValueError(
            f"policy.threshold_grid must contain exactly {sorted(GRID_FIELDS)}"
        )
    for field, values in grid.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"policy.threshold_grid.{field} must be a non-empty list")
        if len(values) != len(set(values)):
            raise ValueError(f"policy.threshold_grid.{field} contains duplicates")
        if any(not checker.is_number(item) or not 0 <= item <= 1 for item in values):
            raise ValueError(
                f"policy.threshold_grid.{field} values must be between 0 and 1"
            )


def assert_identity(
    policy: dict[str, Any],
    task: dict[str, Any],
    instances: dict[str, Any],
    specialist: dict[str, Any],
    fallback: dict[str, Any],
    system_entry: dict[str, Any],
) -> None:
    if instances["layer"] != "public-development":
        raise ValueError(
            "selective policy calibration refuses non-public instance sets"
        )
    if policy["task_ref"] != instances["task_ref"] or policy["task_ref"] != {
        "id": task["task_id"],
        "revision": task["revision"],
    }:
        raise ValueError("policy, task, and instance-set identity do not match")
    configured_instances = task["instance_set"]
    if (
        configured_instances["id"],
        configured_instances["revision"],
        configured_instances["layer"],
    ) != (instances["instance_set_id"], instances["revision"], instances["layer"]):
        raise ValueError(
            "calibration instances do not match the task's public-development set"
        )
    if (
        specialist["task_ref"] != policy["task_ref"]
        or fallback["task_ref"] != policy["task_ref"]
    ):
        raise ValueError("prediction task references do not match the policy")
    expected_instances = {
        "id": instances["instance_set_id"],
        "revision": instances["revision"],
    }
    if (
        specialist["instance_set_ref"] != expected_instances
        or fallback["instance_set_ref"] != expected_instances
    ):
        raise ValueError(
            "specialist and fallback predictions must share the calibration instance set"
        )
    nodes = policy["ordered_nodes"]
    if specialist["entry_ref"]["id"] != nodes[0]["id"]:
        raise ValueError(
            "specialist prediction entry does not match the first policy node"
        )
    if fallback["entry_ref"]["id"] != nodes[1]["id"]:
        raise ValueError(
            "fallback prediction entry does not match the second policy node"
        )
    if system_entry["track"] != "system":
        raise ValueError("composed cascade entry must use the system track")
    expected_policy_revision = f"{policy['policy_id']}@{policy['revision']}"
    if system_entry["adapter"].get("kind") != "capability-graph":
        raise ValueError("composed cascade entry must use a capability-graph adapter")
    if system_entry["adapter"].get("policy_revision") != expected_policy_revision:
        raise ValueError(
            "system entry adapter does not reference the selected policy revision"
        )
    if system_entry["disclosure"].get("policy_revision") != expected_policy_revision:
        raise ValueError(
            "system entry disclosure does not reference the selected policy revision"
        )
    components = system_entry["disclosure"].get("components", [])
    for node in nodes[:2]:
        if not any(component.startswith(f"{node['id']}@") for component in components):
            raise ValueError(
                f"system entry does not disclose required node {node['id']}"
            )
    benchmark.assert_complete_predictions(task, instances, specialist)
    benchmark.assert_complete_predictions(task, instances, fallback)


def collapse_predictions(
    predictions: dict[str, Any],
    *,
    require_signals: bool,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for output in predictions["outputs"]:
        grouped[output["instance_id"]].append(output)
    collapsed: dict[str, dict[str, Any]] = {}
    revisions: set[str] = set()
    for instance_id, rows in grouped.items():
        rows.sort(key=lambda row: row["pass_index"])
        signatures = {
            canonical_bytes(
                {
                    "predicted_label": row["predicted_label"],
                    "error": row["error"],
                    "decision_signals": row.get("decision_signals"),
                }
            )
            for row in rows
        }
        if len(signatures) != 1:
            raise ValueError(
                f"{predictions['prediction_set_id']}: {instance_id} is inconsistent across passes"
            )
        first = rows[0]
        signals = first.get("decision_signals")
        if require_signals and first["error"] is None and signals is None:
            raise ValueError(
                f"{predictions['prediction_set_id']}: {instance_id} lacks decision signals"
            )
        if signals is not None:
            revisions.add(signals["revision"])
        collapsed[instance_id] = {
            "predicted_label": first["predicted_label"],
            "error": first["error"],
            "decision_signals": signals,
            "latency_ms": statistics.fmean(float(row["latency_ms"]) for row in rows),
        }
    if require_signals and len(revisions) > 1:
        raise ValueError("specialist decision signal revisions must be identical")
    return collapsed


def accepts(signals: dict[str, Any] | None, rule: dict[str, float]) -> bool:
    if signals is None:
        return False
    return (
        signals["max_probability"] >= rule["max_probability_min"]
        and signals["margin"] >= rule["margin_min"]
        and signals["normalized_entropy"] <= rule["normalized_entropy_max"]
    )


def evaluate_rule(
    rule: dict[str, float],
    instances: dict[str, Any],
    specialist: dict[str, dict[str, Any]],
    fallback: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    total = len(instances["instances"])
    specialist_correct = 0
    first_hop_accepted = 0
    first_hop_correct = 0
    specialist_errors = 0
    caught_errors = 0
    escalated = 0
    final_correct = 0
    for instance in instances["instances"]:
        instance_id = instance["id"]
        expected = instance["expected_label"]
        local = specialist[instance_id]
        broad = fallback[instance_id]
        local_correct = local["error"] is None and local["predicted_label"] == expected
        broad_correct = broad["error"] is None and broad["predicted_label"] == expected
        accept = local["error"] is None and accepts(local["decision_signals"], rule)
        specialist_correct += int(local_correct)
        specialist_errors += int(not local_correct)
        first_hop_accepted += int(accept)
        first_hop_correct += int(accept and local_correct)
        escalated += int(not accept)
        caught_errors += int(not accept and not local_correct)
        final_correct += int(local_correct if accept else broad_correct)
    return {
        "thresholds": rule,
        "counts": {
            "instances": total,
            "specialist_correct": specialist_correct,
            "specialist_errors": specialist_errors,
            "first_hop_accepted": first_hop_accepted,
            "escalated": escalated,
            "final_correct": final_correct,
        },
        "metrics": {
            "specialist_accuracy": ratio(specialist_correct, total),
            "first_hop_acceptance_rate": ratio(first_hop_accepted, total),
            "first_hop_accuracy": ratio(first_hop_correct, first_hop_accepted),
            "escalation_rate": ratio(escalated, total),
            "escalation_recall": ratio(caught_errors, specialist_errors),
            "final_accuracy": ratio(final_correct, total),
        },
    }


def gate_failures(candidate: dict[str, Any], targets: dict[str, float]) -> list[str]:
    metrics = candidate["metrics"]
    mapping = {
        "specialist_accuracy_min": "specialist_accuracy",
        "first_hop_acceptance_rate_min": "first_hop_acceptance_rate",
        "first_hop_accuracy_min": "first_hop_accuracy",
        "escalation_recall_min": "escalation_recall",
        "final_accuracy_min": "final_accuracy",
    }
    failures = []
    for target_name, metric_name in mapping.items():
        value = metrics[metric_name]
        if value is None or value + 1e-12 < targets[target_name]:
            failures.append(target_name)
    return failures


def candidate_rank(candidate: dict[str, Any]) -> tuple[float, ...]:
    metrics = candidate["metrics"]
    thresholds = candidate["thresholds"]
    return (
        metrics["first_hop_acceptance_rate"] or 0.0,
        metrics["final_accuracy"] or 0.0,
        metrics["first_hop_accuracy"] or 0.0,
        metrics["escalation_recall"] or 0.0,
        -thresholds["max_probability_min"],
        -thresholds["margin_min"],
        thresholds["normalized_entropy_max"],
    )


def fallback_rank(
    candidate: dict[str, Any], targets: dict[str, float]
) -> tuple[float, ...]:
    return (
        len(TARGET_FIELDS) - len(gate_failures(candidate, targets)),
    ) + candidate_rank(candidate)


def calibrate(
    policy: dict[str, Any],
    instances: dict[str, Any],
    specialist: dict[str, dict[str, Any]],
    fallback: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    grid = policy["threshold_grid"]
    candidates = []
    for max_probability, margin, entropy in itertools.product(
        grid["max_probability_min"], grid["margin_min"], grid["normalized_entropy_max"]
    ):
        candidate = evaluate_rule(
            {
                "max_probability_min": float(max_probability),
                "margin_min": float(margin),
                "normalized_entropy_max": float(entropy),
            },
            instances,
            specialist,
            fallback,
        )
        candidate["gate_failures"] = gate_failures(candidate, policy["targets"])
        candidates.append(candidate)
    feasible = [candidate for candidate in candidates if not candidate["gate_failures"]]
    selected = max(feasible, key=candidate_rank) if feasible else None
    best_observed = max(
        candidates, key=lambda candidate: fallback_rank(candidate, policy["targets"])
    )
    selective_feasible = [
        candidate
        for candidate in candidates
        if candidate["metrics"]["first_hop_accuracy"] is not None
        and candidate["metrics"]["first_hop_accuracy"]
        >= policy["targets"]["first_hop_accuracy_min"]
        and candidate["metrics"]["escalation_recall"] is not None
        and candidate["metrics"]["escalation_recall"]
        >= policy["targets"]["escalation_recall_min"]
    ]
    expected_by_id = {
        item["id"]: item["expected_label"] for item in instances["instances"]
    }

    def component_summary(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
        correct = sum(
            row["error"] is None
            and row["predicted_label"] == expected_by_id[instance_id]
            for instance_id, row in rows.items()
        )
        return {
            "accuracy": ratio(correct, len(expected_by_id)),
            "correct": correct,
            "count": len(expected_by_id),
            "latency_ms_mean": statistics.fmean(
                row["latency_ms"] for row in rows.values()
            ),
        }

    oracle_correct = sum(
        (
            specialist[instance_id]["error"] is None
            and specialist[instance_id]["predicted_label"] == expected
        )
        or (
            fallback[instance_id]["error"] is None
            and fallback[instance_id]["predicted_label"] == expected
        )
        for instance_id, expected in expected_by_id.items()
    )
    signal_revisions = sorted(
        {
            row["decision_signals"]["revision"]
            for row in specialist.values()
            if row["decision_signals"] is not None
        }
    )
    return {
        "artifact_type": "selective-routing-calibration",
        "contract_version": policy["contract_version"],
        "policy_ref": {"id": policy["policy_id"], "revision": policy["revision"]},
        "task_ref": instances["task_ref"],
        "calibration_instance_set": {
            "id": instances["instance_set_id"],
            "revision": instances["revision"],
            "layer": instances["layer"],
            "sha256": sha256_json(instances),
            "count": len(instances["instances"]),
        },
        "ordered_nodes": policy["ordered_nodes"],
        "signal_revisions": signal_revisions,
        "targets": policy["targets"],
        "candidate_count": len(candidates),
        "feasible_candidate_count": len(feasible),
        "selective_gate_candidate_count": len(selective_feasible),
        "selected_policy": selected,
        "best_observed": best_observed,
        "component_metrics": {
            "specialist": component_summary(specialist),
            "fallback": component_summary(fallback),
            "perfect_router_oracle_accuracy": ratio(
                oracle_correct, len(expected_by_id)
            ),
            "perfect_router_oracle_correct": oracle_correct,
        },
        "decision": "calibrated" if selected is not None else "no-feasible-policy",
        "official": False,
    }


def compose_system_predictions(
    policy: dict[str, Any],
    calibration: dict[str, Any],
    instances: dict[str, Any],
    specialist_predictions: dict[str, Any],
    fallback_predictions: dict[str, Any],
    system_entry: dict[str, Any],
) -> dict[str, Any]:
    selected = calibration["selected_policy"]
    if selected is None:
        raise ValueError("cannot compose system predictions without a feasible policy")
    rule = selected["thresholds"]
    expected_by_id = {
        item["id"]: item["expected_label"] for item in instances["instances"]
    }
    fallback_by_key = {
        (item["instance_id"], item["pass_index"]): item
        for item in fallback_predictions["outputs"]
    }
    nodes = [node for node in policy["ordered_nodes"] if node["enabled"]]
    eligible_nodes = [node["id"] for node in nodes[:2]]
    specialist_node, fallback_node = eligible_nodes
    fallback_tier = nodes[1]["tier"]
    outputs = []
    for local in specialist_predictions["outputs"]:
        key = (local["instance_id"], local["pass_index"])
        broad = fallback_by_key[key]
        expected = expected_by_id[local["instance_id"]]
        local_correct = local["error"] is None and local["predicted_label"] == expected
        broad_correct = broad["error"] is None and broad["predicted_label"] == expected
        accept_local = local["error"] is None and accepts(
            local.get("decision_signals"), rule
        )
        final = local if accept_local else broad
        selected_node = specialist_node if accept_local else fallback_node
        if local_correct:
            best_node = specialist_node
        elif broad_correct:
            best_node = fallback_node
        else:
            best_node = specialist_node
        output = {
            "instance_id": local["instance_id"],
            "pass_index": local["pass_index"],
            "predicted_label": final["predicted_label"],
            "latency_ms": float(local["latency_ms"])
            + (0.0 if accept_local else float(broad["latency_ms"])),
            "error": final["error"],
            "routing": {
                "eligible_nodes": eligible_nodes,
                "selected_node": selected_node,
                "best_eligible_node": best_node,
                "accepted": final["error"] is None,
                "escalated": not accept_local,
                "should_escalate": not local_correct,
                "route_regret": 0.0 if selected_node == best_node else 1.0,
                "hops": 1 if accept_local else 2,
                "final_tier": nodes[0]["tier"] if accept_local else fallback_tier,
                "exhaustion": None if final["error"] is None else "no-accepted-result",
            },
        }
        if local.get("decision_signals") is not None:
            output["decision_signals"] = local["decision_signals"]
        outputs.append(output)
    artifact = {
        "artifact_type": "prediction_set",
        "contract_version": policy["contract_version"],
        "prediction_set_id": f"{system_entry['entry_id']}-{instances['instance_set_id']}-predictions",
        "revision": "1",
        "task_ref": instances["task_ref"],
        "entry_ref": {
            "id": system_entry["entry_id"],
            "revision": system_entry["revision"],
        },
        "instance_set_ref": {
            "id": instances["instance_set_id"],
            "revision": instances["revision"],
        },
        "outputs": outputs,
    }
    errors: list[str] = []
    checker.validate_artifact(artifact, checker.load_contract(), errors)
    if errors:
        raise ValueError(
            "composed system predictions are invalid: " + "; ".join(errors)
        )
    return artifact


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--instances", required=True, type=Path)
    parser.add_argument("--specialist-predictions", required=True, type=Path)
    parser.add_argument("--fallback-predictions", required=True, type=Path)
    parser.add_argument("--system-entry", required=True, type=Path)
    parser.add_argument("--out-report", required=True, type=Path)
    parser.add_argument("--out-predictions", type=Path)
    args = parser.parse_args()
    try:
        policy = load_json(args.policy)
        validate_policy(policy)
        task = load_artifact(args.task, "task")
        instances = load_artifact(args.instances, "instance_set")
        specialist_predictions = load_artifact(
            args.specialist_predictions, "prediction_set"
        )
        fallback_predictions = load_artifact(
            args.fallback_predictions, "prediction_set"
        )
        system_entry = load_artifact(args.system_entry, "entry")
        assert_identity(
            policy,
            task,
            instances,
            specialist_predictions,
            fallback_predictions,
            system_entry,
        )
        specialist = collapse_predictions(specialist_predictions, require_signals=True)
        fallback = collapse_predictions(fallback_predictions, require_signals=False)
        report = calibrate(policy, instances, specialist, fallback)
        report["prediction_inputs"] = [
            {
                "prediction_set_id": value["prediction_set_id"],
                "revision": value["revision"],
                "sha256": sha256_json(value),
                "output_count": len(value["outputs"]),
            }
            for value in (specialist_predictions, fallback_predictions)
        ]
        write_json(args.out_report, report)
        if args.out_predictions is not None:
            predictions = compose_system_predictions(
                policy,
                report,
                instances,
                specialist_predictions,
                fallback_predictions,
                system_entry,
            )
            write_json(args.out_predictions, predictions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"selective cascade calibration failed: {exc}", file=sys.stderr)
        return 1
    print(
        "selective cascade calibration: "
        f"{report['decision']} ({report['feasible_candidate_count']}/{report['candidate_count']} feasible)"
    )
    return 0 if report["selected_policy"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
