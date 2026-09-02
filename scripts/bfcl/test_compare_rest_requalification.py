from compare_rest_requalification import compare


def frontier(accuracy=1.0):
    return {"accuracy": accuracy}


def arm(model_id, suite, outcomes, schema_failures=0, side_effects=0):
    return {
        "schema_version": "posttrainllm.rest-arm-eval.v1",
        "model_id": model_id,
        "suite": suite,
        "count": len(outcomes),
        "passed": sum(outcomes),
        "accuracy": sum(outcomes) / len(outcomes),
        "schema_failures": schema_failures,
        "unexpected_side_effects": side_effects,
        "load_seconds": 1.0,
        "decode_seconds": 2.0,
        "decode_tokens_per_second": 3.0,
        "peak_rss_bytes": 4,
        "wall_seconds": 5.0,
        "traces": [
            {"id": f"id-{index}", "valid": valid}
            for index, valid in enumerate(outcomes)
        ],
    }


def test_promotes_only_when_every_gate_passes():
    result = compare(
        frontier(),
        frontier(),
        arm("stock-4b", "depth", [True] * 7 + [False] * 5),
        arm("rest-4b", "depth", [True] * 12),
        arm("stock-4b", "breadth", [True, False, False, False]),
        arm("rest-4b", "breadth", [True, True, False, False]),
    )
    assert result["decision"] == "promote"
    assert (
        result["gates"]["heldout_breadth_delta"]["paired_counts"]["candidate_only"] == 1
    )


def test_frontier_failure_forces_protocol_retry():
    result = compare(
        frontier(0.99),
        frontier(),
        arm("stock-4b", "depth", [False] * 12),
        arm("rest-4b", "depth", [True] * 12),
        arm("stock-4b", "breadth", [False, False]),
        arm("rest-4b", "breadth", [True, False]),
    )
    assert result["decision"] == "retry-protocol"


def test_safety_regression_rejects_candidate():
    result = compare(
        frontier(),
        frontier(),
        arm("stock-4b", "depth", [False] * 12),
        arm("rest-4b", "depth", [True] * 12, schema_failures=1),
        arm("stock-4b", "breadth", [False, False]),
        arm("rest-4b", "breadth", [True, False]),
    )
    assert result["decision"] == "reject"
    assert not result["gates"]["safety_regressions"]["passed"]
