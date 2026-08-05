#!/usr/bin/env python3
"""Offline contract tests for local/cloud character-policy adapters."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import game_2048_cloud_pilot as cloud  # noqa: E402
import game_2048_llm_policy as policy  # noqa: E402

CLOUD_CONFIG = ROOT / "configs/game-2048/cloud-opponents-development-v1.json"
CLOUD_SMOKE_REPORT = ROOT / "evals/game-2048/cloud-adapter-smoke-v1.json"
FRONTIER_SCREENING_ATTEMPT = ROOT / "evals/game-2048/frontier-screening-attempt-v1.json"
FRONTIER_SCREENING_ATTEMPT_V2 = ROOT / "evals/game-2048/frontier-screening-attempt-v2.json"
FRONTIER_SCREENING_SONNET = ROOT / "evals/game-2048/frontier-screening-sonnet-v1.json"


def test_shared_prompt_and_legal_schema_are_character_only():
    observation = {
        "board": [0, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 0, 0, 0, 0],
        "score": 100,
        "move_count": 12,
        "legal_actions": ["up", "right"],
    }
    messages = policy.messages(observation)
    assert messages[-1]["content"] == "B=0123456789ab0000;S=100;M=12;L=UR"
    assert "screenshot" not in policy.flat_prompt(observation).lower()
    schema = policy.constrained_action_schema(observation["legal_actions"])
    assert schema["properties"]["action"]["enum"] == ["U", "R"]
    assert policy.parse_constrained_output('{"action":"R"}') == "right"


def test_cloud_config_is_development_only_and_fail_closed():
    config = cloud.load_config(CLOUD_CONFIG)
    assert config["status"] == "development-aliases-not-frozen"
    assert {entry["backend"] for entry in config["opponents"]} == {"codex-cli", "claude-cli"}
    assert {entry["identity_state"] for entry in config["opponents"]} == {"mutable-alias", "immutable"}
    assert {entry["requested_model"] for entry in config["opponents"] if entry["identity_state"] == "immutable"} == {
        "claude-sonnet-5",
        "claude-opus-4-8",
    }
    damaged = copy.deepcopy(config)
    damaged["opponents"][0]["unexpected"] = True
    temporary = ROOT / "runs/game-2048/invalid-cloud-config-test.json"
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_text(json.dumps(damaged), encoding="utf-8")
        try:
            cloud.load_config(temporary)
        except ValueError:
            pass
        else:
            raise AssertionError("cloud config accepted an undeclared field")
    finally:
        temporary.unlink(missing_ok=True)


def test_cloud_smoke_report_cannot_be_mistaken_for_benchmark_evidence():
    report = json.loads(CLOUD_SMOKE_REPORT.read_text(encoding="utf-8"))
    assert report["status"] == "adapter-smoke-only-not-benchmark-evidence"
    assert report["moves_per_run"] == 1
    assert len(report["entries"]) == 3
    assert all(entry["strict"]["valid"] for entry in report["entries"])
    assert all(entry["legal_constrained_diagnostic"]["valid"] for entry in report["entries"])
    assert next(entry for entry in report["entries"] if entry["requested_model"] == "gpt-5.5")["resolved_model"] is None


def test_failed_frontier_screen_has_no_score_or_random_comparison():
    reports = [
        json.loads(FRONTIER_SCREENING_ATTEMPT.read_text(encoding="utf-8")),
        json.loads(FRONTIER_SCREENING_ATTEMPT_V2.read_text(encoding="utf-8")),
    ]
    assert reports[0]["provider_budget_failures"] == len(reports[0]["seeds"])
    assert reports[0]["decision"] == "retry-harness-budget"
    assert reports[1]["identity_drift_observed"] is True
    assert reports[1]["decision"] == "retry-harness-budget-and-fallback"
    for report in reports:
        assert report["status"].startswith("invalid-provider")
        assert report["score"] is None
        assert report["random_legal_comparison"] is None


def test_valid_sonnet_screen_fails_the_intelligence_gradient():
    report = json.loads(FRONTIER_SCREENING_SONNET.read_text(encoding="utf-8"))
    assert report["status"] == "valid-development-screen-not-frozen-evidence"
    assert report["provider_failures"] == 0
    assert report["invalid_decisions"] == 0
    assert report["model_mean_score"] < report["random_legal_mean_score"]
    assert report["paired_win_rate"] < report["admission_thresholds"]["paired_win_rate_minimum"]
    assert report["paired_bootstrap_95_ci"]["lower"] < 0
    assert report["decision"] == "fail-development-intelligence-gradient"


def test_claude_envelope_preserves_identity_cost_and_action():
    raw, metadata = cloud.parse_claude_envelope(
        json.dumps(
            {
                "is_error": False,
                "structured_output": {"action": "D"},
                "modelUsage": {"claude-versioned-id": {"inputTokens": 10}},
                "total_cost_usd": 0.004,
                "num_turns": 1,
            }
        ),
        constrained=True,
    )
    assert policy.parse_constrained_output(raw) == "down"
    assert metadata == {"resolved_models": ["claude-versioned-id"], "cost_usd": 0.004, "turns": 1}


def test_codex_event_parser_rejects_tool_use():
    safe = '\n'.join(
        [
            json.dumps({"type": "thread.started", "thread_id": "test"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "L"}}),
        ]
    )
    assert cloud.parse_codex_events(safe)["event_count"] == 2
    unsafe = safe + "\n" + json.dumps({"type": "item.started", "item": {"type": "command_execution"}})
    try:
        cloud.parse_codex_events(unsafe)
    except ValueError as exc:
        assert "tool use" in str(exc)
    else:
        raise AssertionError("Codex tool use was accepted")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"game-2048 LLM policy tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
