import json
import math

from needle2_successor_eval import (
    evaluation_payload,
    generate_length_bucketed,
    load_completed,
    load_rows,
    model_arm,
    parse_calls,
    risk_coverage,
    summarize,
    unsafe,
)


def test_length_bucketing_restores_original_output_order() -> None:
    class Tokenizer:
        @staticmethod
        def encode(value: str) -> list[str]:
            return list(value)

    seen_batches = []

    def batch_generate(_model, _params, _tokenizer, prompts, **_kwargs):
        seen_batches.append(prompts)
        return [{"text": prompt} for prompt in prompts]

    rows = [
        {"query": "longest", "tools": []},
        {"query": "x", "tools": []},
        {"query": "middle", "tools": []},
    ]
    outputs = generate_length_bucketed(
        rows,
        params={},
        runtime={
            "model": object(),
            "tokenizer": Tokenizer(),
            "build_prompt": lambda query, _tools: query,
            "batch_generate": batch_generate,
            "batch_size": 2,
            "max_new_tokens": 64,
        },
    )
    assert seen_batches == [["x", "middle"], ["longest"]]
    assert [output["text"] for output in outputs] == ["longest", "x", "middle"]


def test_resume_loads_only_a_matching_fixture(tmp_path) -> None:
    fixture = tmp_path / "dev.jsonl"
    output = tmp_path / "receipt.json"
    payload = evaluation_payload(
        fixture,
        "cpu",
        ["TFRT_CPU_0"],
        [{"model_id": "candidate", "tool_selection_exact": 0.5}],
    )
    output.write_text(json.dumps(payload))
    assert (
        load_completed(output, fixture, True)["candidate"]["tool_selection_exact"]
        == 0.5
    )
    assert load_completed(output, fixture, False) == {}


def test_arm_stop_helpers_detect_seed_and_unsafe_counts() -> None:
    assert model_arm("plain-safety-seed-1380401") == "plain-safety"
    assert model_arm("incumbent") is None
    assert unsafe({"out_of_scope_false_actions": 0, "destructive_bypasses": 1})
    assert not unsafe({"out_of_scope_false_actions": 0, "destructive_bypasses": 0})


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
