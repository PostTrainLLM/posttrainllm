from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals/capability-graph/fixtures"
sys.path.insert(0, str(ROOT / "scripts"))

import capability_graph as capability  # noqa: E402
import run_everyday_benchmark as everyday  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class CapabilityGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = load(ROOT / "specialists/capability-graph.json")
        self.policy = load(ROOT / "configs/capability-graph/policies/local-only-v1.json")
        self.request = load(FIXTURES / "request-file-ops-v1.json")
        self.installed = load(FIXTURES / "installed-v1.json")
        self.router = load(FIXTURES / "router-file-ops-v1.json")
        self.outcomes = load(FIXTURES / "outcomes-accept-v1.json")

    def mutate(self, callback):
        graph = copy.deepcopy(self.graph)
        callback(graph)
        return capability.validate_graph(graph)

    def test_development_graph_and_policy_are_valid(self):
        self.assertEqual(capability.validate_graph(self.graph), [])
        self.assertEqual(capability.validate_policy(self.policy), [])
        registry = load(ROOT / "specialists/registry.json")
        package_ids = {item["id"] for item in registry["packages"]}
        referenced = {item["package_id"] for item in self.graph["nodes"] if item["package_id"]}
        self.assertTrue(referenced.issubset(package_ids))
        self.assertEqual(registry["version"], 1)

    def test_validator_rejects_duplicate_and_dangling_ids(self):
        duplicate = self.mutate(lambda graph: graph["nodes"].append(copy.deepcopy(graph["nodes"][0])))
        dangling = self.mutate(lambda graph: graph["edges"][0].update({"to": "missing-node"}))
        self.assertTrue(any("duplicate node id" in error for error in duplicate))
        self.assertTrue(any("dangling node reference" in error for error in dangling))

    def test_validator_rejects_cycles_schema_mismatch_and_unverified_acceptance(self):
        def add_cycle(graph):
            graph["edges"].append({
                "id": "cycle-back", "kind": "fallback-to", "from": "local-generalist-placeholder",
                "to": "file-ops-distilled", "order": 2, "capability": "file-ops",
                "request_schema": "request/text-v1", "response_schema": "file-plan/v1", "executable": True,
            })

        cycle = self.mutate(add_cycle)
        mismatch = self.mutate(lambda graph: graph["edges"][0].update({"response_schema": "wrong/v1"}))
        unverified = self.mutate(
            lambda graph: graph.update({"edges": [edge for edge in graph["edges"] if edge["id"] != "verify-distilled"]})
        )
        self.assertTrue(any("fallback cycle" in error for error in cycle))
        self.assertTrue(any("target schema is incompatible" in error for error in mismatch))
        self.assertTrue(any("no valid verifier edge" in error for error in unverified))

    def test_validator_rejects_missing_safe_terminal_unsupported_claims_and_private_data(self):
        def remove_terminal(graph):
            graph["edges"] = [edge for edge in graph["edges"] if edge["id"] != "fallback-general-external"]
            next(node for node in graph["nodes"] if node["id"] == "local-generalist-placeholder")["terminal_behavior"] = "fallback-only"

        terminal = self.mutate(remove_terminal)
        unsupported = self.mutate(lambda graph: graph["nodes"][1]["verifier_policy"].update({"rule": "accept self-confidence"}))
        private = self.mutate(lambda graph: graph.update({"api_key": "sk-test-12345678901234567890"}))
        self.assertTrue(any("no fallback or safe terminal" in error for error in terminal))
        self.assertTrue(any("self-confidence cannot accept" in error for error in unsupported))
        self.assertTrue(any("prohibited sensitive field" in error for error in private))

    def test_dry_run_is_deterministic_and_selects_smallest_eligible_node(self):
        first = capability.dry_run(self.graph, self.policy, self.request, self.installed, self.router)
        second = capability.dry_run(self.graph, self.policy, self.request, self.installed, self.router)
        self.assertEqual(first, second)
        self.assertEqual(first["selected_node"], "file-ops-distilled")
        self.assertEqual(first["fallback_path"], ["file-ops-rest", "local-generalist-placeholder", "external-frontier-disabled"])
        self.assertEqual(first["residency"]["load_bytes"], 0)
        self.assertEqual(first["request"]["content"], "redacted")

    def test_low_confidence_bypasses_specialists(self):
        router = copy.deepcopy(self.router)
        router["confidence"] = 0.2
        route = capability.dry_run(self.graph, self.policy, self.request, self.installed, router)
        self.assertEqual(route["selected_node"], "local-generalist-placeholder")
        reasons = {(item["node_id"], item["reason"]) for item in route["exclusions"]}
        self.assertIn(("file-ops-distilled", "route-low-confidence"), reasons)

    def test_residency_never_overrides_capability_privacy_or_quality(self):
        mutations = (
            lambda node: node.update({"capabilities": ["unrelated"]}),
            lambda node: node["operating_envelope"].update({"quality": 0.1}),
            lambda node: node["privacy"].update({"class": "local-public"}),
        )
        for mutation in mutations:
            graph = copy.deepcopy(self.graph)
            node = next(item for item in graph["nodes"] if item["id"] == "file-ops-distilled")
            mutation(node)
            route = capability.dry_run(graph, self.policy, self.request, self.installed, self.router)
            self.assertNotIn("file-ops-distilled", route["eligible"])

    def test_verifier_acceptance_and_rejection_fallback(self):
        accepted = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, self.outcomes)
        self.assertEqual(accepted["result"]["kind"], "accepted")
        self.assertEqual(accepted["result"]["node_id"], "file-ops-distilled")

        outcomes = copy.deepcopy(self.outcomes)
        outcomes["file-ops-distilled"]["verifier"] = {"accepted": False, "reason": "state-mismatch"}
        outcomes["file-ops-rest"] = {
            "status": "success", "value": "pass", "latency_ms": 9, "external_cost_usd": 0,
            "verifier": {"accepted": True, "reason": "final-state-match"},
        }
        fallback = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, outcomes)
        self.assertEqual(fallback["result"]["node_id"], "file-ops-rest")
        self.assertEqual(fallback["trace"]["attempts"][0]["failure"], "verifier-rejected")

    def test_timeout_load_failure_and_exhaustion_return_safe_failure(self):
        outcomes = {
            "file-ops-distilled": {"status": "timeout", "latency_ms": 5},
            "file-ops-rest": {"status": "load-failed", "latency_ms": 1},
            "local-generalist-placeholder": {
                "status": "success", "value": "must-not-leak", "latency_ms": 2,
                "verifier": {"accepted": False, "reason": "state-mismatch"},
            },
        }
        execution = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, outcomes)
        self.assertEqual(execution["result"], {"kind": "safe-failure", "failure": "no-accepted-result"})
        self.assertNotIn("must-not-leak", json.dumps(execution))
        failures = [item["failure"] for item in execution["trace"]["attempts"]]
        self.assertIn("node-timeout", failures)
        self.assertIn("node-load-failed", failures)

    def test_hop_latency_and_external_cost_budgets_are_enforced(self):
        hop_policy = copy.deepcopy(self.policy)
        hop_policy["max_hops"] = 1
        execution = capability.cascade(self.graph, hop_policy, self.request, self.installed, self.router, {})
        self.assertEqual(execution["result"]["failure"], "hop-budget-exhausted")

        latency_policy = copy.deepcopy(self.policy)
        latency_policy["max_total_latency_ms"] = 1
        execution = capability.cascade(self.graph, latency_policy, self.request, self.installed, self.router, self.outcomes)
        self.assertEqual(execution["result"]["failure"], "latency-budget-exhausted")

        graph = copy.deepcopy(self.graph)
        external = next(node for node in graph["nodes"] if node["id"] == "external-frontier-disabled")
        external["enabled"] = True
        policy = copy.deepcopy(self.policy)
        policy.update({"allow_external": True, "allow_network": True, "max_external_calls": 1, "max_external_cost_usd": 0.01})
        request = copy.deepcopy(self.request)
        request["external_authorized"] = True
        router = {"ranked_node_ids": ["external-frontier-disabled"], "confidence": 1, "ood_score": 0}
        outcome = {"external-frontier-disabled": {"status": "success", "value": "pass", "latency_ms": 2, "external_cost_usd": 0.02, "verifier": {"accepted": True, "reason": "pass"}}}
        execution = capability.cascade(graph, policy, request, self.installed, router, outcome)
        self.assertEqual(execution["result"]["failure"], "external-cost-budget-exhausted")
        self.assertEqual(execution["trace"]["resources"]["external_calls"], 1)

    def test_external_execution_requires_all_three_opt_ins(self):
        graph = copy.deepcopy(self.graph)
        next(node for node in graph["nodes"] if node["id"] == "external-frontier-disabled")["enabled"] = True
        router = {"ranked_node_ids": ["external-frontier-disabled"], "confidence": 1, "ood_score": 0}
        blocked = capability.dry_run(graph, self.policy, self.request, self.installed, router)
        self.assertEqual(blocked["terminal"], "no-eligible-node")

        policy = copy.deepcopy(self.policy)
        policy.update({"allow_external": True, "allow_network": True, "max_external_calls": 1, "max_external_cost_usd": 1})
        request = copy.deepcopy(self.request)
        request["external_authorized"] = True
        allowed = capability.dry_run(graph, policy, request, self.installed, router)
        self.assertEqual(allowed["selected_node"], "external-frontier-disabled")

    def test_trace_is_redacted_and_resource_accounted(self):
        execution = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, self.outcomes)
        trace = execution["trace"]
        self.assertEqual(trace["request"]["content"], "redacted")
        self.assertEqual(trace["resources"]["latency_end_to_end_ms"], 12)
        self.assertEqual(trace["resources"]["max_active_parameters"], 4000000000)
        self.assertEqual(trace["resources"]["external_calls"], 0)
        self.assertNotIn("content_sha256", json.dumps(trace))

    def test_everyday_benchmark_adapter_binds_graph_policy_nodes_and_resources(self):
        execution = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, self.outcomes)
        task = load(ROOT / "configs/everyday-benchmark/tasks/local-file-operations-v1.json")
        entry = load(ROOT / "configs/everyday-benchmark/entries/pace-intent-v8-qwen-cascade-v1.json")
        prediction = capability.benchmark_prediction(execution, task, entry, "fileops-public-001")
        output = prediction["outputs"][0]
        metrics = everyday.system_metrics(prediction["outputs"], {"fileops-public-001": "pass"})
        self.assertEqual(metrics["false_accept_rate"], 0)
        self.assertEqual(metrics["resource_metrics"]["latency_end_to_end_ms_mean"], 12)
        self.assertEqual(metrics["resource_metrics"]["latency_warm_end_to_end_ms_mean"], 12)
        self.assertIsNone(metrics["resource_metrics"]["latency_cold_end_to_end_ms_mean"])
        self.assertEqual(metrics["resource_metrics"]["installed_bytes_touched_max"], 8044981893)
        self.assertEqual(metrics["resource_metrics"]["shared_base_bytes_touched_max"], 8044981893)
        self.assertEqual(metrics["resource_metrics"]["adapter_bytes_touched_max"], 0)
        self.assertEqual(output["routing"]["binding"]["invoked_node_ids"], ["file-ops-distilled"])
        self.assertEqual(output["routing"]["binding"]["invoked_package_ids"], ["qwen3-4b-file-ops-distilled"])
        self.assertEqual(output["routing"]["binding"]["verifier_ids"], ["file-state-verifier"])
        self.assertEqual(output["routing"]["binding"]["trace_contract_version"], "specialist-capability-trace/v1")
        self.assertEqual(output["routing"]["resource_evidence"]["peak_resident_bytes"], 8044981893)

    def test_system_qualification_fails_closed_on_router_or_end_to_end_gates(self):
        execution = capability.cascade(self.graph, self.policy, self.request, self.installed, self.router, self.outcomes)
        task = load(ROOT / "configs/everyday-benchmark/tasks/local-file-operations-v1.json")
        entry = load(ROOT / "configs/everyday-benchmark/entries/pace-intent-v8-qwen-cascade-v1.json")
        prediction = capability.benchmark_prediction(execution, task, entry, "fileops-public-001")
        metrics = everyday.system_metrics(prediction["outputs"], {"fileops-public-001": "pass"})
        gates = load(ROOT / "configs/capability-graph/system-gates-v1.json")

        qualified_metrics = copy.deepcopy(metrics)
        qualified_metrics.update({
            "false_accept_rate": 0, "route_accuracy": 1,
            "escalation_recall": 1, "over_escalation_rate": 0,
        })
        self.assertEqual(capability.system_qualification(1, qualified_metrics, gates)["state"], "qualified")

        router_failed = copy.deepcopy(qualified_metrics)
        router_failed["route_accuracy"] = 0.5
        result = capability.system_qualification(1, router_failed, gates)
        self.assertEqual(result["state"], "unqualified")
        self.assertFalse(result["checks"]["route_accuracy"]["passed"])

        leaf_strong_but_system_failed = capability.system_qualification(0.8, qualified_metrics, gates)
        self.assertEqual(leaf_strong_but_system_failed["state"], "unqualified")
        self.assertFalse(leaf_strong_but_system_failed["checks"]["final_accuracy"]["passed"])


if __name__ == "__main__":
    unittest.main()
