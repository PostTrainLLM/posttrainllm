import json
import math

from needle2_successor_eval import load_rows, parse_calls, risk_coverage, summarize


def test_load_rows_normalizes_training_answers(tmp_path) -> None:
    path = tmp_path / "tiny.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "tiny",
                "query": "Explain DNS",
                "slice": "supported",
                "tools": [],
                "answers": [{"name": "answer_knowledge", "arguments": {}}],
            }
        )
        + "\n"
    )
    assert load_rows(path)[0]["expected_tool"] == "answer_knowledge"


def test_parse_calls_requires_a_well_formed_tool_call_block() -> None:
    calls, valid = parse_calls(
        '<think>copy the query</think><tool_call>[{"name":"answer_knowledge","arguments":{"question":"DNS"}}]</tool_call>'
    )
    assert valid is True
    assert calls[0]["name"] == "answer_knowledge"
    assert parse_calls("no call")[1] is False
    assert parse_calls("<tool_call>{}</tool_call>")[1] is False


def test_risk_coverage_preserves_safety_counts() -> None:
    points = risk_coverage(
        [
            {
                "score": 0.9,
                "predicted_tools": ["answer_knowledge"],
                "exact": True,
                "slice": "knowledge",
            },
            {
                "score": 0.8,
                "predicted_tools": ["perform_screen_action"],
                "exact": False,
                "slice": "out-of-scope",
            },
        ]
    )
    assert points[0]["accepted"] == 1
    assert points[0]["precision"] == 1
    assert points[-1]["out_of_scope_false_actions"] == 1


def test_summary_scores_exact_empty_and_named_calls() -> None:
    rows = [
        {"id": "a", "slice": "knowledge", "expected_tool": "answer_knowledge"},
        {"id": "b", "slice": "out-of-scope", "expected_tool": None},
    ]
    decoded = [
        {
            "text": '<tool_call>[{"name":"answer_knowledge","arguments":{}}]</tool_call>',
            "tokens": [1, 2],
            "mean_logprob": math.log(0.8),
        },
        {
            "text": "<tool_call>[]</tool_call>",
            "tokens": [3],
            "mean_logprob": math.log(0.7),
        },
    ]
    result = summarize("candidate", None, rows, decoded, 1.0)
    assert result["tool_selection_exact"] == 1
    assert result["out_of_scope_false_actions"] == 0
    assert result["destructive_bypasses"] == 0
