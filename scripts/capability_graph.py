#!/usr/bin/env python3
"""Validate and exercise the no-model specialist capability graph V1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "configs/specialist-capability-graph.schema.json"
DEFAULT_GRAPH = ROOT / "specialists/capability-graph.json"
DEFAULT_POLICY = ROOT / "configs/capability-graph/policies/local-only-v1.json"
DEFAULT_SYSTEM_GATES = ROOT / "configs/capability-graph/system-gates-v1.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def exact_fields(value: Any, required: set[str], path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return None
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    if missing:
        errors.append(f"{path}: missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{path}: unknown fields: {', '.join(unknown)}")
    return value


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def scan_private(value: Any, denylist: list[str], errors: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.lower()
            if any(part in lowered for part in denylist):
                errors.append(f"{path}: contains a prohibited sensitive field")
            scan_private(item, denylist, errors, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_private(item, denylist, errors, f"{path}[{index}]")
    elif isinstance(value, str) and re.search(r"(?:sk|key|token)[-_][A-Za-z0-9]{16,}", value, re.I):
        errors.append(f"{path}: contains credential-shaped content")


def validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "contract_version", "policy_id", "revision", "quality_floor",
        "resident_quality_tolerance", "max_route_ood_score", "min_route_confidence",
        "max_hops", "max_total_latency_ms", "max_resident_bytes",
        "max_active_parameters", "max_installed_bytes", "max_external_calls",
        "max_external_cost_usd", "allowed_privacy_classes", "allow_network",
        "allow_external", "trace_content", "safe_failure",
    }
    exact_fields(policy, required, "$policy", errors)
    if policy.get("contract_version") != "specialist-capability-policy/v1":
        errors.append("$policy.contract_version: unsupported")
    for field in (
        "quality_floor", "resident_quality_tolerance", "max_route_ood_score",
        "min_route_confidence", "max_total_latency_ms", "max_resident_bytes",
        "max_active_parameters", "max_installed_bytes", "max_external_calls",
        "max_external_cost_usd",
    ):
        if not finite_number(policy.get(field)) or policy[field] < 0:
            errors.append(f"$policy.{field}: must be a finite non-negative number")
    if not isinstance(policy.get("max_hops"), int) or isinstance(policy.get("max_hops"), bool) or policy["max_hops"] < 1:
        errors.append("$policy.max_hops: must be a positive integer")
    for field in ("quality_floor", "resident_quality_tolerance", "max_route_ood_score", "min_route_confidence"):
        if finite_number(policy.get(field)) and policy[field] > 1:
            errors.append(f"$policy.{field}: must be at most 1")
    if not isinstance(policy.get("allowed_privacy_classes"), list) or not policy["allowed_privacy_classes"]:
        errors.append("$policy.allowed_privacy_classes: must be a non-empty array")
    if policy.get("trace_content") != "redacted":
        errors.append("$policy.trace_content: V1 requires redacted")
    for field in ("allow_network", "allow_external"):
        if not isinstance(policy.get(field), bool):
            errors.append(f"$policy.{field}: must be boolean")
    return errors


def validate_graph(graph: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    schema = load(SCHEMA_PATH)
    errors: list[str] = []
    top = {
        "contract_version", "graph_id", "revision", "status", "registry_ref",
        "description", "nodes", "edges",
    }
    exact_fields(graph, top, "$", errors)
    if graph.get("contract_version") != schema["contract_version"]:
        errors.append("$.contract_version: unsupported")
    for field in ("graph_id", "revision", "status", "registry_ref", "description"):
        if not nonempty(graph.get(field)):
            errors.append(f"$.{field}: must be a non-empty string")
    registry_path = root / str(graph.get("registry_ref", ""))
    try:
        registry = load(registry_path)
        package_ids = {item["id"] for item in registry["packages"]}
    except (OSError, KeyError, json.JSONDecodeError, TypeError) as exc:
        errors.append(f"$.registry_ref: cannot load registry: {type(exc).__name__}")
        package_ids = set()

    nodes_raw = graph.get("nodes")
    edges_raw = graph.get("edges")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        errors.append("$.nodes: must be a non-empty array")
        nodes_raw = []
    if not isinstance(edges_raw, list) or not edges_raw:
        errors.append("$.edges: must be a non-empty array")
        edges_raw = []

    node_fields = {
        "id", "kind", "package_id", "runtime_id", "capabilities",
        "request_schema", "response_schema", "operating_envelope",
        "verifier_policy", "privacy", "resources", "known_failures",
        "prohibited_uses", "enabled", "external_opt_in_required", "terminal_behavior",
    }
    node_ids: set[str] = set()
    nodes: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(nodes_raw):
        path = f"$.nodes[{index}]"
        node = exact_fields(raw, node_fields, path, errors)
        if node is None:
            continue
        node_id = node.get("id")
        if not nonempty(node_id):
            errors.append(f"{path}.id: must be a non-empty string")
        elif node_id in node_ids:
            errors.append(f"{path}.id: duplicate node id")
        else:
            node_ids.add(node_id)
            nodes[node_id] = node
        if node.get("kind") not in schema["node_kinds"]:
            errors.append(f"{path}.kind: unsupported")
        identities = [nonempty(node.get("package_id")), nonempty(node.get("runtime_id"))]
        if sum(identities) != 1:
            errors.append(f"{path}: exactly one of package_id or runtime_id is required")
        if nonempty(node.get("package_id")) and node["package_id"] not in package_ids:
            errors.append(f"{path}.package_id: dangling registry package")
        for field in ("capabilities", "known_failures", "prohibited_uses"):
            value = node.get(field)
            if not isinstance(value, list) or not value or any(not nonempty(item) for item in value):
                errors.append(f"{path}.{field}: must be a non-empty string array")
        for field in ("request_schema", "response_schema", "terminal_behavior"):
            if not nonempty(node.get(field)):
                errors.append(f"{path}.{field}: must be a non-empty string")
        envelope = exact_fields(node.get("operating_envelope"), {"eval_ref", "quality", "ood_behavior"}, f"{path}.operating_envelope", errors)
        if envelope:
            if not nonempty(envelope.get("eval_ref")) or not nonempty(envelope.get("ood_behavior")):
                errors.append(f"{path}.operating_envelope: eval_ref and ood_behavior are required")
            if not finite_number(envelope.get("quality")) or not 0 <= envelope["quality"] <= 1:
                errors.append(f"{path}.operating_envelope.quality: must be between 0 and 1")
        verifier = exact_fields(node.get("verifier_policy"), {"kind", "verifier_id", "rule"}, f"{path}.verifier_policy", errors)
        if verifier:
            if verifier.get("kind") not in schema["verifier_kinds"]:
                errors.append(f"{path}.verifier_policy.kind: unsupported")
            if not nonempty(verifier.get("verifier_id")) or not nonempty(verifier.get("rule")):
                errors.append(f"{path}.verifier_policy: verifier_id and rule are required")
            if node.get("kind") in {"specialist", "generalist", "external-fallback"} and "self-confidence" in str(verifier.get("rule", "")).lower():
                errors.append(f"{path}.verifier_policy: self-confidence cannot accept a generative result")
        privacy = exact_fields(node.get("privacy"), {"class", "network_allowed"}, f"{path}.privacy", errors)
        if privacy and (not nonempty(privacy.get("class")) or not isinstance(privacy.get("network_allowed"), bool)):
            errors.append(f"{path}.privacy: invalid privacy contract")
        resources = node.get("resources")
        if not isinstance(resources, dict) or set(resources) != set(schema["required_resources"]):
            errors.append(f"{path}.resources: must contain exactly the required measurements")
        else:
            for name, raw_measurement in resources.items():
                measurement = exact_fields(raw_measurement, {"state", "value", "unit", "source"}, f"{path}.resources.{name}", errors)
                if not measurement:
                    continue
                state = measurement.get("state")
                if state not in schema["measurement_states"]:
                    errors.append(f"{path}.resources.{name}.state: unsupported")
                if state in {"measured", "derived", "historical"}:
                    if not finite_number(measurement.get("value")) or measurement["value"] < 0:
                        errors.append(f"{path}.resources.{name}.value: measured value must be non-negative")
                    if not nonempty(measurement.get("source")):
                        errors.append(f"{path}.resources.{name}.source: evidence source required")
                elif measurement.get("value") is not None:
                    errors.append(f"{path}.resources.{name}.value: must be null for {state}")
                if not nonempty(measurement.get("unit")):
                    errors.append(f"{path}.resources.{name}.unit: required")
        for field in ("enabled", "external_opt_in_required"):
            if not isinstance(node.get(field), bool):
                errors.append(f"{path}.{field}: must be boolean")
        if node.get("kind") == "external-fallback":
            if not node.get("external_opt_in_required"):
                errors.append(f"{path}: external fallback must require opt-in")
            if not (privacy or {}).get("network_allowed"):
                errors.append(f"{path}: external fallback must declare its network boundary")

    edge_fields = {"id", "kind", "from", "to", "order", "capability", "request_schema", "response_schema", "executable"}
    edge_ids: set[str] = set()
    edges: list[dict[str, Any]] = []
    for index, raw in enumerate(edges_raw):
        path = f"$.edges[{index}]"
        edge = exact_fields(raw, edge_fields, path, errors)
        if edge is None:
            continue
        if not nonempty(edge.get("id")) or edge["id"] in edge_ids:
            errors.append(f"{path}.id: missing or duplicate")
        else:
            edge_ids.add(edge["id"])
        if edge.get("kind") not in schema["edge_kinds"]:
            errors.append(f"{path}.kind: unsupported")
        if edge.get("from") not in nodes or edge.get("to") not in nodes:
            errors.append(f"{path}: dangling node reference")
            continue
        if not isinstance(edge.get("order"), int) or isinstance(edge.get("order"), bool) or edge["order"] < 1:
            errors.append(f"{path}.order: must be positive")
        if not isinstance(edge.get("executable"), bool):
            errors.append(f"{path}.executable: must be boolean")
        if edge.get("kind") == "composes-with" and edge.get("executable"):
            errors.append(f"{path}: V1 composition edges must be non-executable")
        source, target = nodes[edge["from"]], nodes[edge["to"]]
        if edge.get("kind") in {"routes-to", "fallback-to"}:
            if target["request_schema"] != edge.get("request_schema") or target["response_schema"] != edge.get("response_schema"):
                errors.append(f"{path}: target schema is incompatible")
            if edge.get("kind") == "fallback-to" and (
                source["request_schema"] != target["request_schema"]
                or source["response_schema"] != target["response_schema"]
            ):
                errors.append(f"{path}: fallback schemas are incompatible")
        if edge.get("kind") == "verified-by" and (
            source["response_schema"] != edge.get("request_schema")
            or target["request_schema"] != edge.get("request_schema")
            or target["response_schema"] != edge.get("response_schema")
        ):
            errors.append(f"{path}: verifier schemas are incompatible")
        edges.append(edge)

    fallback: dict[str, list[str]] = {}
    for edge in edges:
        if edge.get("kind") == "fallback-to" and edge.get("executable"):
            fallback.setdefault(edge["from"], []).append(edge["to"])
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            cycle = visiting[visiting.index(node_id):] + [node_id]
            errors.append("$.edges: executable fallback cycle: " + " -> ".join(cycle))
            return
        if node_id in visited:
            return
        visiting.append(node_id)
        for target in fallback.get(node_id, []):
            visit(target)
        visiting.pop()
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id)

    verified_sources = {edge["from"] for edge in edges if edge.get("kind") == "verified-by" and edge.get("executable")}
    fallback_sources = {edge["from"] for edge in edges if edge.get("kind") == "fallback-to" and edge.get("executable")}
    for node_id, node in nodes.items():
        if node["kind"] in {"specialist", "generalist", "external-fallback"}:
            verifier_id = node["verifier_policy"]["verifier_id"]
            if verifier_id not in nodes or nodes[verifier_id]["kind"] != "verifier" or node_id not in verified_sources:
                errors.append(f"$.nodes[{node_id}]: generative node has no valid verifier edge")
            if node_id not in fallback_sources and node["kind"] != "external-fallback" and "safe-failure" not in node["terminal_behavior"]:
                errors.append(f"$.nodes[{node_id}]: no fallback or safe terminal")

    scan_private(graph, schema["denylisted_field_fragments"], errors)
    return errors


def node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in graph["nodes"]}


def resource_value(node: dict[str, Any], name: str) -> float | None:
    value = node["resources"][name]["value"]
    return float(value) if finite_number(value) else None


def fallback_path(graph: dict[str, Any], start: str) -> list[str]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in graph["edges"]:
        if edge["kind"] == "fallback-to" and edge["executable"]:
            by_source.setdefault(edge["from"], []).append(edge)
    result = []
    seen = {start}
    current = start
    while by_source.get(current):
        edge = sorted(by_source[current], key=lambda item: (item["order"], item["id"]))[0]
        current = edge["to"]
        if current in seen:
            break
        seen.add(current)
        result.append(current)
    return result


def residency_plan(selected: str | None, nodes: dict[str, dict[str, Any]], snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    capacity = min(int(snapshot.get("capacity_bytes", policy["max_resident_bytes"])), int(policy["max_resident_bytes"]))
    residents = sorted(snapshot.get("resident", []), key=lambda item: (item["last_used"], item["node_id"]))
    resident_ids = {item["node_id"] for item in residents}
    used = sum(int(item["bytes"]) for item in residents)
    if selected is not None and nodes[selected]["kind"] == "external-fallback":
        return {"capacity_bytes": capacity, "before_bytes": used, "load_bytes": 0, "evictions": [], "after_bytes": used, "feasible": True}
    if selected is None or selected in resident_ids:
        return {"capacity_bytes": capacity, "before_bytes": used, "load_bytes": 0, "evictions": [], "after_bytes": used, "feasible": True}
    load_bytes = resource_value(nodes[selected], "loaded_bytes")
    if load_bytes is None:
        load_bytes = resource_value(nodes[selected], "installed_artifact_bytes")
    if load_bytes is None:
        return {"capacity_bytes": capacity, "before_bytes": used, "load_bytes": None, "evictions": [], "after_bytes": None, "feasible": False, "reason": "resource-evidence-missing"}
    evictions = []
    remaining = used
    for item in residents:
        if remaining + load_bytes <= capacity:
            break
        remaining -= int(item["bytes"])
        evictions.append(item["node_id"])
    feasible = remaining + load_bytes <= capacity
    return {"capacity_bytes": capacity, "before_bytes": used, "load_bytes": int(load_bytes), "evictions": evictions, "after_bytes": int(remaining + load_bytes) if feasible else None, "feasible": feasible}


def dry_run(graph: dict[str, Any], policy: dict[str, Any], request: dict[str, Any], installed: dict[str, Any], router: dict[str, Any]) -> dict[str, Any]:
    graph_errors = validate_graph(graph)
    policy_errors = validate_policy(policy)
    if graph_errors or policy_errors:
        raise ValueError("invalid graph/policy: " + "; ".join(graph_errors + policy_errors))
    nodes = node_index(graph)
    installed_nodes = set(installed.get("installed_node_ids", []))
    ranked = router.get("ranked_node_ids")
    if not isinstance(ranked, list) or any(node_id not in nodes for node_id in ranked):
        raise ValueError("router ranked_node_ids are invalid")
    confidence = router.get("confidence")
    ood_score = router.get("ood_score")
    if not finite_number(confidence) or not finite_number(ood_score):
        raise ValueError("router confidence and ood_score must be finite numbers")
    bypass = confidence < policy["min_route_confidence"] or ood_score > policy["max_route_ood_score"]
    exclusions: list[dict[str, str]] = []
    eligible: list[str] = []
    rank = {node_id: index for index, node_id in enumerate(ranked)}
    for node_id in ranked:
        node = nodes[node_id]
        reason = None
        if node["kind"] not in {"specialist", "generalist", "external-fallback"}:
            reason = "node-kind-not-executable"
        elif bypass and node["kind"] == "specialist":
            reason = "route-low-confidence" if confidence < policy["min_route_confidence"] else "route-out-of-distribution"
        elif not node["enabled"]:
            reason = "node-disabled"
        elif node["kind"] != "external-fallback" and node_id not in installed_nodes:
            reason = "node-not-installed"
        elif request["capability"] not in node["capabilities"] and "*" not in node["capabilities"]:
            reason = "capability-mismatch"
        elif request["request_schema"] != node["request_schema"] or request["response_schema"] != node["response_schema"]:
            reason = "schema-mismatch"
        elif request["privacy_class"] not in policy["allowed_privacy_classes"]:
            reason = "privacy-policy-blocked"
        elif node["kind"] != "external-fallback" and request["privacy_class"] == "local-private" and node["privacy"]["class"] != "local-private":
            reason = "privacy-policy-blocked"
        elif node["kind"] != "external-fallback" and node["privacy"]["network_allowed"] and not policy["allow_network"]:
            reason = "network-not-authorized"
        elif node["kind"] == "external-fallback" and (
            not policy["allow_external"] or not policy["allow_network"] or not request.get("external_authorized", False)
        ):
            reason = "network-not-authorized"
        elif node["operating_envelope"]["quality"] < policy["quality_floor"]:
            reason = "quality-floor"
        elif node["kind"] != "external-fallback":
            for resource, budget in (
                ("active_parameters", policy["max_active_parameters"]),
                ("resident_bytes_peak", policy["max_resident_bytes"]),
                ("installed_artifact_bytes", policy["max_installed_bytes"]),
            ):
                value = resource_value(node, resource)
                if value is None:
                    reason = f"{resource}-evidence-missing"
                    break
                if value > budget:
                    reason = "resource-budget-exhausted"
                    break
        if reason:
            exclusions.append({"node_id": node_id, "reason": reason})
        else:
            eligible.append(node_id)
    resident_ids = {item["node_id"] for item in installed.get("resident", [])}
    eligible.sort(
        key=lambda node_id: (
            resource_value(nodes[node_id], "active_parameters") or float("inf"),
            0 if node_id in resident_ids else 1,
            rank[node_id],
            node_id,
        )
    )
    selected = eligible[0] if eligible else None
    fallback = fallback_path(graph, selected) if selected else []
    residency = residency_plan(selected, nodes, installed, policy)
    if selected and not residency["feasible"]:
        exclusions.append({"node_id": selected, "reason": residency.get("reason", "resource-budget-exhausted")})
        eligible = [node_id for node_id in eligible if node_id != selected]
        selected = eligible[0] if eligible else None
        fallback = fallback_path(graph, selected) if selected else []
        residency = residency_plan(selected, nodes, installed, policy)
    return {
        "contract_version": "specialist-capability-dry-run/v1",
        "graph": {"id": graph["graph_id"], "revision": graph["revision"], "sha256": digest(graph)},
        "policy": {"id": policy["policy_id"], "revision": policy["revision"], "sha256": digest(policy)},
        "request": {
            "request_id": request["request_id"],
            "request_sha256": digest(request),
            "capability": request["capability"],
            "request_schema": request["request_schema"],
            "response_schema": request["response_schema"],
            "privacy_class": request["privacy_class"],
            "content": "redacted",
        },
        "router": {"confidence": confidence, "ood_score": ood_score, "bypassed_specialists": bypass},
        "candidates": ranked,
        "eligible": eligible,
        "exclusions": sorted(exclusions, key=lambda item: (item["node_id"], item["reason"])),
        "selected_node": selected,
        "fallback_path": fallback,
        "budgets": {key: policy[key] for key in ("max_hops", "max_total_latency_ms", "max_resident_bytes", "max_active_parameters", "max_installed_bytes", "max_external_calls", "max_external_cost_usd")},
        "residency": residency,
        "terminal": "ready" if selected else "no-eligible-node",
    }


def cascade(graph: dict[str, Any], policy: dict[str, Any], request: dict[str, Any], installed: dict[str, Any], router: dict[str, Any], outcomes: dict[str, Any]) -> dict[str, Any]:
    route = dry_run(graph, policy, request, installed, router)
    nodes = node_index(graph)
    blocked = {item["node_id"]: item["reason"] for item in route["exclusions"]}
    chain = ([route["selected_node"]] + route["fallback_path"]) if route["selected_node"] else []
    attempts = []
    total_latency = 0.0
    external_calls = 0
    external_cost = 0.0
    accepted: dict[str, Any] | None = None
    terminal_failure = "no-eligible-node" if not chain else "no-accepted-result"
    for node_id in chain:
        if len(attempts) >= policy["max_hops"]:
            terminal_failure = "hop-budget-exhausted"
            break
        node = nodes[node_id]
        if node_id in blocked or not node["enabled"]:
            reason = blocked.get(node_id, "node-disabled")
            attempts.append({"node_id": node_id, "package_id": node["package_id"], "runtime_id": node["runtime_id"], "tier": node["kind"], "status": "blocked", "accepted": False, "failure": reason, "latency_ms": 0, "verifier": None, "output_sha256": None})
            continue
        if node["kind"] == "external-fallback":
            if not policy["allow_external"] or not policy["allow_network"] or not request.get("external_authorized", False):
                attempts.append({"node_id": node_id, "package_id": node["package_id"], "runtime_id": node["runtime_id"], "tier": node["kind"], "status": "blocked", "accepted": False, "failure": "network-not-authorized", "latency_ms": 0, "verifier": None, "output_sha256": None})
                terminal_failure = "network-not-authorized"
                continue
            external_calls += 1
        outcome = outcomes.get(node_id)
        if not isinstance(outcome, dict):
            outcome = {"status": "load-failed", "latency_ms": 0, "external_cost_usd": 0}
        latency = float(outcome.get("latency_ms", 0))
        cost = float(outcome.get("external_cost_usd", 0))
        total_latency += latency
        external_cost += cost
        failure_by_status = {
            "timeout": "node-timeout",
            "load-failed": "node-load-failed",
            "output-invalid": "node-output-invalid",
        }
        failure = failure_by_status.get(outcome.get("status"))
        verifier = outcome.get("verifier") if outcome.get("status") == "success" else None
        is_accepted = isinstance(verifier, dict) and verifier.get("accepted") is True
        if outcome.get("status") == "success" and not isinstance(verifier, dict):
            failure = "verifier-unavailable"
        elif outcome.get("status") == "success" and not is_accepted:
            failure = "verifier-rejected"
        value = outcome.get("value")
        value_hash = digest(value) if value is not None else None
        attempts.append({"node_id": node_id, "package_id": node["package_id"], "runtime_id": node["runtime_id"], "tier": node["kind"], "status": outcome.get("status"), "accepted": is_accepted, "failure": failure, "latency_ms": latency, "verifier": None if verifier is None else {"id": node["verifier_policy"]["verifier_id"], "accepted": bool(verifier.get("accepted")), "reason": verifier.get("reason")}, "output_sha256": value_hash})
        if total_latency > policy["max_total_latency_ms"]:
            terminal_failure = "latency-budget-exhausted"
            break
        if external_calls > policy["max_external_calls"] or external_cost > policy["max_external_cost_usd"]:
            terminal_failure = "external-cost-budget-exhausted"
            break
        if is_accepted:
            accepted = {"kind": "accepted", "node_id": node_id, "value": value, "value_sha256": value_hash}
            break
    if accepted is None:
        result = {"kind": "safe-failure", "failure": terminal_failure}
        terminal = {"kind": "safe-failure", "failure": terminal_failure, "accepted_node": None}
    else:
        result = accepted
        terminal = {"kind": "accepted", "failure": None, "accepted_node": accepted["node_id"]}
    peak_resident = route["residency"].get("after_bytes")
    active_values = [resource_value(nodes[item["node_id"]], "active_parameters") for item in attempts]
    installed_values = [resource_value(nodes[item["node_id"]], "installed_artifact_bytes") for item in attempts]
    shared_values = [resource_value(nodes[item["node_id"]], "shared_base_bytes") for item in attempts]
    adapter_values = [resource_value(nodes[item["node_id"]], "adapter_bytes") for item in attempts]
    trace = {
        "contract_version": "specialist-capability-trace/v1",
        "graph": route["graph"],
        "policy": route["policy"],
        "request": route["request"],
        "routing": {key: route[key] for key in ("candidates", "eligible", "exclusions", "selected_node", "fallback_path")},
        "route_confidence": route["router"]["confidence"],
        "route_ood_score": route["router"]["ood_score"],
        "budgets": route["budgets"],
        "attempts": attempts,
        "residency": route["residency"],
        "resources": {
            "latency_end_to_end_ms": total_latency,
            "latency_mode": "warm" if route["residency"].get("load_bytes") == 0 else "cold",
            "loaded_bytes": route["residency"].get("load_bytes"),
            "peak_resident_bytes": peak_resident,
            "max_active_parameters": max((value for value in active_values if value is not None), default=None),
            "installed_bytes_touched": sum(value for value in installed_values if value is not None),
            "shared_base_bytes_touched": max((value for value in shared_values if value is not None), default=None),
            "adapter_bytes_touched": sum(value for value in adapter_values if value is not None),
            "external_calls": external_calls,
            "external_cost_usd": external_cost,
        },
        "terminal": terminal,
    }
    private_errors: list[str] = []
    scan_private(trace, load(SCHEMA_PATH)["denylisted_field_fragments"], private_errors)
    if private_errors:
        raise ValueError("trace privacy validation failed: " + "; ".join(private_errors))
    return {"contract_version": "specialist-capability-execution/v1", "result": result, "trace": trace}


def benchmark_prediction(execution: dict[str, Any], task: dict[str, Any], entry: dict[str, Any], instance_id: str) -> dict[str, Any]:
    trace = execution["trace"]
    attempts = trace["attempts"]
    accepted = execution["result"]["kind"] == "accepted"
    prediction_field = task["scorer"]["prediction_field"]
    output = {
        "instance_id": instance_id,
        "pass_index": 1,
        prediction_field: execution["result"].get("value") if accepted else None,
        "latency_ms": trace["resources"]["latency_end_to_end_ms"],
        "error": None if accepted else execution["result"]["failure"],
        "routing": {
            "eligible_nodes": trace["routing"]["eligible"] or [trace["routing"]["selected_node"]],
            "selected_node": trace["routing"]["selected_node"],
            "best_eligible_node": trace["routing"]["selected_node"],
            "accepted": accepted,
            "escalated": len(attempts) > 1,
            "should_escalate": len(attempts) > 1,
            "route_regret": 0.0,
            "hops": max(1, len(attempts)),
            "final_tier": attempts[-1]["tier"] if attempts else "safe-failure",
            "exhaustion": None if accepted else execution["result"]["failure"],
            "binding": {
                "graph_id": trace["graph"]["id"],
                "graph_revision": trace["graph"]["revision"],
                "graph_sha256": trace["graph"]["sha256"],
                "policy_id": trace["policy"]["id"],
                "policy_revision": trace["policy"]["revision"],
                "policy_sha256": trace["policy"]["sha256"],
                "trace_contract_version": trace["contract_version"],
                "invoked_node_ids": [item["node_id"] for item in attempts],
                "invoked_package_ids": [item["package_id"] or item["runtime_id"] for item in attempts],
                "verifier_ids": [item["verifier"]["id"] for item in attempts if item["verifier"] is not None],
            },
            "resource_evidence": trace["resources"],
        },
    }
    return {
        "artifact_type": "prediction_set",
        "contract_version": "everyday-benchmark/v1",
        "prediction_set_id": f"{entry['entry_id']}-{instance_id}-graph-prediction",
        "revision": "1",
        "task_ref": {"id": task["task_id"], "revision": task["revision"]},
        "entry_ref": {"id": entry["entry_id"], "revision": entry["revision"]},
        "instance_set_ref": {"id": task["instance_set"]["id"], "revision": task["instance_set"]["revision"]},
        "outputs": [output],
    }


def system_qualification(final_accuracy: float, metrics: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    required_gates = {
        "contract_version", "gate_id", "revision", "min_final_accuracy",
        "max_false_accept_rate", "min_route_accuracy", "min_escalation_recall",
        "max_over_escalation_rate", "max_latency_end_to_end_ms_mean",
        "max_external_calls", "max_external_cost_usd",
    }
    if not isinstance(gates, dict) or set(gates) != required_gates:
        raise ValueError("system qualification gates are invalid")
    if gates["contract_version"] != "capability-graph-system-gates/v1":
        raise ValueError("system qualification gate contract is unsupported")
    if not finite_number(final_accuracy) or not 0 <= final_accuracy <= 1:
        raise ValueError("final accuracy must be between 0 and 1")
    resources = metrics.get("resource_metrics") if isinstance(metrics, dict) else None
    observed = {
        "final_accuracy": final_accuracy,
        "false_accept_rate": metrics.get("false_accept_rate") if isinstance(metrics, dict) else None,
        "route_accuracy": metrics.get("route_accuracy") if isinstance(metrics, dict) else None,
        "escalation_recall": metrics.get("escalation_recall") if isinstance(metrics, dict) else None,
        "over_escalation_rate": metrics.get("over_escalation_rate") if isinstance(metrics, dict) else None,
        "latency_end_to_end_ms_mean": resources.get("latency_end_to_end_ms_mean") if isinstance(resources, dict) else None,
        "external_calls": resources.get("external_calls") if isinstance(resources, dict) else None,
        "external_cost_usd": resources.get("external_cost_usd") if isinstance(resources, dict) else None,
    }
    comparisons = {
        "final_accuracy": ("min", gates["min_final_accuracy"]),
        "false_accept_rate": ("max", gates["max_false_accept_rate"]),
        "route_accuracy": ("min", gates["min_route_accuracy"]),
        "escalation_recall": ("min", gates["min_escalation_recall"]),
        "over_escalation_rate": ("max", gates["max_over_escalation_rate"]),
        "latency_end_to_end_ms_mean": ("max", gates["max_latency_end_to_end_ms_mean"]),
        "external_calls": ("max", gates["max_external_calls"]),
        "external_cost_usd": ("max", gates["max_external_cost_usd"]),
    }
    checks = {}
    for name, (direction, threshold) in comparisons.items():
        value = observed[name]
        passed = finite_number(value) and (value >= threshold if direction == "min" else value <= threshold)
        checks[name] = {"observed": value, "operator": direction, "threshold": threshold, "passed": passed}
    passed = all(item["passed"] for item in checks.values())
    return {
        "contract_version": "capability-graph-system-qualification/v1",
        "gate_ref": {"id": gates["gate_id"], "revision": gates["revision"], "sha256": digest(gates)},
        "state": "qualified" if passed else "unqualified",
        "checks": checks,
    }


def write_or_print(value: Any, output: Path | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    inspect_cmd.add_argument("--capability", required=True)
    for name in ("dry-run", "cascade"):
        command = sub.add_parser(name)
        command.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
        command.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
        command.add_argument("--request", type=Path, required=True)
        command.add_argument("--installed", type=Path, required=True)
        command.add_argument("--router-output", type=Path, required=True)
        if name == "cascade":
            command.add_argument("--outcomes", type=Path, required=True)
        command.add_argument("--out", type=Path)
    adapter = sub.add_parser("benchmark-adapter")
    adapter.add_argument("--execution", type=Path, required=True)
    adapter.add_argument("--task", type=Path, required=True)
    adapter.add_argument("--entry", type=Path, required=True)
    adapter.add_argument("--instance-id", required=True)
    adapter.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            errors = validate_graph(load(args.graph))
            if errors:
                raise ValueError("; ".join(errors))
            print(f"capability graph valid: {args.graph}")
        elif args.command == "inspect":
            graph = load(args.graph)
            errors = validate_graph(graph)
            if errors:
                raise ValueError("; ".join(errors))
            nodes = [node for node in graph["nodes"] if args.capability in node["capabilities"] or "*" in node["capabilities"]]
            write_or_print({"capability": args.capability, "nodes": nodes}, None)
        elif args.command in {"dry-run", "cascade"}:
            graph, policy = load(args.graph), load(args.policy)
            request, installed, router = load(args.request), load(args.installed), load(args.router_output)
            value = dry_run(graph, policy, request, installed, router)
            if args.command == "cascade":
                value = cascade(graph, policy, request, installed, router, load(args.outcomes))
            write_or_print(value, args.out)
        else:
            value = benchmark_prediction(load(args.execution), load(args.task), load(args.entry), args.instance_id)
            write_or_print(value, args.out)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        print(f"capability graph failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
