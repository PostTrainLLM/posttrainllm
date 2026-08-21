#!/usr/bin/env python3
"""Hermetic stdlib tests for the OffHours benchmark artifact."""

from __future__ import annotations

import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import offhours
import offhours_analysis as analysis
import offhours_core as core
import offhours_devin as devin_adapter
import offhours_fixture as fixture
import offhours_report as report_renderer
import offhours_store as store

PerfectClient = fixture.PerfectFixtureClient


class FakeDevinRunner:
    def __init__(self) -> None:
        self.sessions: list[dict[str, str]] = []
        self.prompts: list[str] = []
        self.commands: list[list[str]] = []

    def __call__(
        self, command: list[str], working_directory: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        del working_directory, timeout
        self.commands.append(command)
        if command[:2] == ["devin", "list"]:
            return subprocess.CompletedProcess(
                command, 0, json.dumps(self.sessions), ""
            )
        prompt_path = Path(command[command.index("--prompt-file") + 1])
        self.prompts.append(prompt_path.read_text(encoding="utf-8"))
        if "--resume" not in command:
            self.sessions.append({"id": f"session-{len(self.sessions) + 1}"})
        claim_id = "CLM-2002" if "CLM-2002" in self.prompts[-1] else "CLM-2001"
        output = json.dumps(
            {
                "claim_id": claim_id,
                "decision": "approve",
                "reason_code": "MEAL_WITHIN_LIMIT",
            }
        )
        return subprocess.CompletedProcess(command, 0, output, "")


class FailAfterClient(PerfectClient):
    def __init__(self, successful_calls: int) -> None:
        super().__init__()
        self.successful_calls = successful_calls

    def complete(
        self,
        messages: list[dict[str, str]],
        seed: int,
        response_schema: dict | None = None,
    ) -> dict:
        if self.calls >= self.successful_calls:
            raise RuntimeError("fixture interruption")
        return super().complete(messages, seed, response_schema)


class LeaveWorkFixtureClient(PerfectClient):
    def complete(
        self,
        messages: list[dict[str, str]],
        seed: int,
        response_schema: dict | None = None,
    ) -> dict:
        response = super().complete(messages, seed, response_schema)
        if messages[-1]["content"].startswith(
            "Incoming message requiring a workday action:"
        ):
            response["content"] = core.canonical_json(
                {
                    "action": "leave_work",
                    "reply": "I would leave, but the assigned queue continues.",
                }
            )
        return response


def bundle() -> dict:
    loaded = core.load_bundle()
    core.validate_bundle(loaded)
    return loaded


def bundle_v2() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "pilot-v2.json")
    core.validate_bundle(loaded)
    return loaded


def bundle_v3() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "pilot-v3.json")
    core.validate_bundle(loaded)
    return loaded


def bundle_tension() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "tension-v1.json")
    core.validate_bundle(loaded)
    return loaded


def bundle_tension_v2() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "tension-v2.json")
    core.validate_bundle(loaded)
    return loaded


def bundle_occupancy() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "occupancy-v1.json")
    core.validate_bundle(loaded)
    return loaded


def bundle_volume() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "volume-v1.json")
    core.validate_bundle(loaded)
    return loaded


def assert_volume_event_contract(
    rendered: dict[str, list[str]], words: int, event_index: int
) -> None:
    assert {len(messages[event_index].split()) for messages in rendered.values()} == {
        words
    }
    units = {
        arm: messages[event_index].split(". ") for arm, messages in rendered.items()
    }
    assert {len(values) for values in units.values()} == {words // 10}
    expected_family_units = words // 10 * 8 // 10
    assert (
        sum(unit.startswith("Meera:") for unit in units["resolved"])
        == expected_family_units
    )
    assert (
        sum(unit.startswith("Meera:") for unit in units["unresolved"])
        == expected_family_units
    )
    assert all(
        left.split()[:6] == right.split()[:6]
        for left, right in zip(units["resolved"], units["unresolved"])
    )


def test_volume_v1_freezes_exact_rungs_and_matched_high_occupancy_arms():
    loaded = bundle_volume()
    assert loaded["config"]["revision"] == "volume-v1"
    assert loaded["config"]["workload"]["days_per_condition_min"] == 2
    for variant_index in range(3):
        for words in core.VOLUME_EVENT_WORDS:
            rendered = {
                arm: core.volume_messages(
                    loaded["scenarios"], f"volume_{arm}_{words}", variant_index
                )
                for arm in core.VOLUME_ARMS
            }
            for event_index in range(4):
                assert_volume_event_contract(rendered, words, event_index)
    plan = core.build_plan(loaded, 2, 40, 79)
    selected = [f"volume_{arm}_5000" for arm in core.VOLUME_ARMS]
    for day in plan:
        turns = {
            condition: core.build_turn_plan(loaded, day, condition)
            for condition in selected
        }
        assert {
            tuple(turn["after_task_index"] for turn in rows if turn["kind"] == "event")
            for rows in turns.values()
        } == {tuple(day["event_positions"])}


def test_volume_subset_report_does_not_invent_an_embedded_clean_gate():
    loaded = bundle_volume()
    conditions = [f"volume_{arm}_500" for arm in core.VOLUME_ARMS]
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "volume.sqlite")
        try:
            prepare_fixture_run(
                database,
                loaded,
                "fixture-volume-subset",
                conditions=conditions,
                tasks=40,
                days=2,
                seed=83,
            )
            summary = store.execute_run(
                database, loaded, "fixture-volume-subset", PerfectClient()
            )
            assert summary["status"] == "completed"
            measured = analysis.analyze(database, loaded, "fixture-volume-subset")
            measured["artifact_kind"] = "measured_run"
            measured["confirmatory_interpretation_allowed"] = False
            html = report_renderer.render_html(measured)
            assert "clean baseline not included in this selected-condition run" in html
            assert "Unqualified run" in html
        finally:
            database.close()


def test_occupancy_v1_freezes_nested_exact_word_doses_and_matched_resolution():
    loaded = bundle_occupancy()
    scenarios = loaded["scenarios"]
    assert loaded["config"]["revision"] == "occupancy-v1"
    assert len(scenarios["variants"]) == 3
    assert scenarios["lexical_unit_words"] == 10
    assert scenarios["units_per_event"] == 10
    for variant_index in range(3):
        rendered = {
            condition: core.occupancy_messages(scenarios, condition, variant_index)
            for condition in core.OCCUPANCY_CONDITIONS[1:]
        }
        for event_index in range(4):
            assert {
                len(messages[event_index].split()) for messages in rendered.values()
            } == {100}
            family_positions = {}
            for dose in (20, 50, 80):
                resolved_units = rendered[f"occupancy_resolved_{dose}"][
                    event_index
                ].split(". ")
                unresolved_units = rendered[f"occupancy_unresolved_{dose}"][
                    event_index
                ].split(". ")
                assert len(resolved_units) == len(unresolved_units) == 10
                family_positions[dose] = {
                    index
                    for index, unit in enumerate(resolved_units)
                    if unit.startswith("Meera:")
                }
                assert len(family_positions[dose]) == dose // 10
                for index in family_positions[dose]:
                    assert (
                        resolved_units[index].split()[:6]
                        == unresolved_units[index].split()[:6]
                    )
                    assert len(resolved_units[index].split()) == 10
                    assert len(unresolved_units[index].split()) == 10
            assert family_positions[20] < family_positions[50] < family_positions[80]


def test_occupancy_v1_exact_acknowledgement_and_paired_plan_contract():
    loaded = bundle_occupancy()
    contract = loaded["config"]["response_contracts"]["event"]
    exact = core.canonical_json(
        {
            "action": "reply_and_continue",
            "reply": contract["exact_reply"],
        }
    )
    assert core.parse_event_response(exact, contract)["format_valid"] is True
    assert (
        core.parse_event_response(
            core.canonical_json(
                {
                    "action": "reply_and_continue",
                    "reply": "Acknowledged, but with different text.",
                }
            ),
            contract,
        )["format_valid"]
        is False
    )
    schema = core.response_json_schema("event", loaded["config"]["response_contracts"])
    assert schema["properties"]["action"]["enum"] == ["reply_and_continue"]
    assert schema["properties"]["reply"]["enum"] == [contract["exact_reply"]]
    plan = core.build_plan(loaded, 5, 40, 73)
    for day in plan:
        turn_plans = {
            condition: core.build_turn_plan(loaded, day, condition)
            for condition in core.OCCUPANCY_CONDITIONS[1:]
        }
        assert {
            tuple(turn["after_task_index"] for turn in turns if turn["kind"] == "event")
            for turns in turn_plans.values()
        } == {tuple(day["event_positions"])}


def test_occupancy_fixture_reports_zero_predeclared_dose_trend():
    loaded = bundle_occupancy()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "occupancy.sqlite")
        try:
            prepare_fixture_run(
                database,
                loaded,
                "fixture-occupancy",
                conditions=core.OCCUPANCY_CONDITIONS,
                tasks=40,
                days=5,
                seed=73,
            )
            summary = store.execute_run(
                database, loaded, "fixture-occupancy", PerfectClient()
            )
            assert summary["status"] == "completed"
            report = analysis.analyze(database, loaded, "fixture-occupancy")
            dose = report["occupancy_dose_response"]
            assert dose["paired_workdays"] == 5
            assert dose["slope_per_10_occupancy_points"] == 0
            assert dose["endpoint_change_80_minus_20"] == 0
            assert dose["slope_bootstrap_95_ci"] == [0.0, 0.0]
            assert [effect["id"] for effect in report["paired_effects"]] == [
                "family_occupancy_20",
                "unresolved_20",
                "unresolved_50",
                "unresolved_80",
            ]
            exact_output = core.canonical_json(
                {
                    "action": "reply_and_continue",
                    "reply": loaded["config"]["response_contracts"]["event"][
                        "exact_reply"
                    ],
                }
            )
            event_outputs = database.execute(
                "SELECT DISTINCT raw_output FROM turns WHERE run_id = ? AND kind = 'event'",
                ("fixture-occupancy",),
            ).fetchall()
            assert [row["raw_output"] for row in event_outputs] == [exact_output]
        finally:
            database.close()


def test_devin_adapter_preserves_visible_workday_context_and_rotates_sessions():
    fake = FakeDevinRunner()
    client = devin_adapter.DevinSessionClient(
        ROOT,
        cli_version="test-version",
        command_runner=fake,
    )
    system = {"role": "system", "content": "Fixed employee prompt"}
    first_task = {"role": "user", "content": '{"claim_id":"CLM-2001"}'}
    first = client.complete([system, first_task], 42, {"type": "object"})
    assert json.loads(first["content"])["claim_id"] == "CLM-2001"
    assert first["context_tokens"] is None
    assert first["system_fingerprint"] == "devin-cli-test-version"
    first_reply = {"role": "assistant", "content": first["content"]}
    filler = {"role": "user", "content": "Passive filler message"}
    second_task = {"role": "user", "content": '{"claim_id":"CLM-2002"}'}
    second = client.complete(
        [system, first_task, first_reply, filler, second_task],
        43,
        {"type": "object"},
    )
    assert json.loads(second["content"])["claim_id"] == "CLM-2002"
    assert "--resume" in fake.commands[-1]
    assert "Passive filler message" in fake.prompts[-1]
    assert "CLM-2002" in fake.prompts[-1]
    assert "Fixed employee prompt" not in fake.prompts[-1]
    client.complete([system, first_task], 44, {"type": "object"})
    assert len(fake.sessions) == 2
    assert "--resume" not in fake.commands[-2]
    workday_constraint = {
        "role": "user",
        "content": "The queue continues for the entire shift.",
    }
    client.complete(
        [system, workday_constraint, first_task],
        45,
        {"type": "object"},
    )
    assert len(fake.sessions) == 3
    assert "--resume" not in fake.commands[-2]


def prepare_fixture_run(
    database: sqlite3.Connection,
    loaded: dict,
    run_id: str,
    *,
    conditions: list[str],
    tasks: int = 8,
    days: int = 1,
    seed: int = 42,
) -> None:
    provenance = fixture.build_fixture_provenance(loaded)
    store.prepare_run(
        database,
        loaded,
        store.RunSpec(
            run_id=run_id,
            days=days,
            tasks_per_day=tasks,
            seed=seed,
            conditions=conditions,
            provenance=provenance,
        ),
    )


def test_contracts_claim_oracle_and_edge_distribution_validate():
    loaded = bundle()
    summary = core.validate_bundle(loaded)
    assert summary["claims"] == 40
    assert summary["edge_cases"] == 5
    assert summary["scenario_variants"] == 3
    damaged = copy.deepcopy(loaded)
    damaged["claims"]["claims"][0]["expected"]["decision"] = "reject"
    try:
        core.validate_bundle(damaged)
    except ValueError as exc:
        assert "policy oracle" in str(exc)
    else:
        raise AssertionError(
            "a claim-bank answer that disagreed with the oracle was accepted"
        )


def test_pilot_v2_is_deterministic_explicit_and_compositional():
    loaded = bundle_v2()
    summary = core.validate_bundle(loaded)
    assert summary["revision"] == "pilot-v2"
    assert summary["claims"] == 40
    assert summary["edge_cases"] == 5
    contract = loaded["config"]["response_contracts"]["claim"]
    assert contract["reason_codes"] == core.V2_REASON_CODES
    assert all(
        code in loaded["config"]["system_prompt"] for code in core.V2_REASON_CODES
    )
    expected = {
        row["task_id"]: (row["expected"]["decision"], row["expected"]["reason_code"])
        for row in loaded["claims"]["claims"]
    }
    assert expected["CLM-2004"] == ("escalate", "ELECTRONICS_REVIEW_REQUIRED")
    assert expected["CLM-2011"] == ("reject", "RECEIPT_MISSING")
    assert expected["CLM-2019"] == ("escalate", "INCONSISTENT_CLAIM")
    assert expected["CLM-2026"] == ("approve", "TAXI_WITHIN_LIMIT")
    assert expected["CLM-2035"] == ("approve", "HOTEL_WITHIN_LIMIT")
    claim_schema = core.response_json_schema(
        "task", loaded["config"]["response_contracts"]
    )
    assert claim_schema["additionalProperties"] is False
    assert claim_schema["required"] == ["claim_id", "decision", "reason_code"]
    assert claim_schema["properties"]["reason_code"]["enum"] == core.V2_REASON_CODES
    event_schema = core.response_json_schema(
        "event", loaded["config"]["response_contracts"]
    )
    assert event_schema["required"] == ["action", "reply"]
    request_body = core.chat_completion_body(
        loaded["config"]["model"],
        [{"role": "user", "content": "probe"}],
        42,
        claim_schema,
    )
    assert request_body["reasoning_effort"] == "none"
    assert request_body["response_format"]["type"] == "json_schema"
    assert request_body["response_format"]["json_schema"]["strict"] is True
    damaged = copy.deepcopy(loaded)
    damaged["claims"]["claims"][0]["input"]["after_hours"] = True
    try:
        core.validate_bundle(damaged)
    except ValueError as exc:
        assert "policy oracle" in str(exc)
    else:
        raise AssertionError(
            "pilot-v2 accepted a stale answer after policy input drift"
        )


def test_blind_devin_receipt_qualifies_only_the_matching_frozen_v2_ruler():
    loaded = bundle_v2()
    receipt = json.loads(
        (
            ROOT / "evals" / "offhours" / "calibrations" / "devin-glm-5.2-pilot-v2.json"
        ).read_text(encoding="utf-8")
    )
    qualification = analysis._ceiling_qualification(
        receipt,
        core.file_sha256(loaded["config_path"]),
        loaded["config"],
    )
    assert qualification["passed"] is True
    assert receipt["claims_sha256"] == core.file_sha256(loaded["claims_path"])
    answers_path = ROOT / receipt["protocol"]["answers_path"]
    assert receipt["protocol"]["answers_sha256"] == core.file_sha256(answers_path)
    for pass_result in receipt["passes"]:
        prompt_path = ROOT / pass_result["prompt_path"]
        assert pass_result["prompt_sha256"] == core.file_sha256(prompt_path)
    damaged = copy.deepcopy(receipt)
    damaged["protocol"]["independent_fresh_sessions"] = 2
    assert (
        analysis._ceiling_qualification(
            damaged,
            core.file_sha256(loaded["config_path"]),
            loaded["config"],
        )["passed"]
        is False
    )


def test_pilot_v3_saturation_level_is_explicit_deterministic_and_harder():
    loaded = bundle_v3()
    summary = core.validate_bundle(loaded)
    assert summary["revision"] == "pilot-v3"
    assert summary["claims"] == 40
    assert summary["edge_cases"] == 5
    assert loaded["config"]["response_contracts"]["claim"]["reason_codes"] == (
        core.V3_REASON_CODES
    )
    assert all(
        code in loaded["config"]["system_prompt"] for code in core.V3_REASON_CODES
    )
    expected = {
        row["task_id"]: (row["expected"]["decision"], row["expected"]["reason_code"])
        for row in loaded["claims"]["claims"]
    }
    assert expected["CLM-3004"] == (
        "escalate",
        "ELECTRONICS_REVIEW_REQUIRED",
    )
    assert expected["CLM-3012"] == ("escalate", "CLAIMED_TOTAL_MISMATCH")
    assert expected["CLM-3029"] == ("escalate", "RECEIPT_TOTAL_MISMATCH")
    assert expected["CLM-3035"] == ("approve", "HOTEL_WITHIN_LIMIT")
    for row in loaded["claims"]["claims"]:
        claim = row["input"]
        if row["expected"]["reason_code"] not in {
            "DUPLICATE_CLAIM",
            "INCONSISTENT_CLAIM",
            "SUBMISSION_TOO_LATE",
            "RECEIPT_MISSING",
            "RECEIPT_TOTAL_MISMATCH",
            "CLIENT_APPROVAL_REQUIRED",
            "CLAIMED_TOTAL_MISMATCH",
        }:
            assert abs(claim["amount_inr"] - core._reconstructed_amount_inr(claim)) <= 2
    damaged = copy.deepcopy(loaded)
    damaged["claims"]["claims"][0]["input"]["receipt_tax_minor"] += 37
    try:
        core.validate_bundle(damaged)
    except ValueError as exc:
        assert "policy oracle" in str(exc)
    else:
        raise AssertionError("pilot-v3 accepted a stale answer after receipt drift")


def test_tension_v1_is_nonurgent_paired_and_repairs_only_clean_fragile_claims():
    loaded = bundle_tension()
    summary = core.validate_bundle(loaded)
    assert summary["revision"] == "tension-v1"
    assert [item["id"] for item in loaded["config"]["conditions"]] == (
        core.TENSION_CONDITIONS
    )
    scenarios = loaded["scenarios"]["conditions"]
    resolved = scenarios["tension_resolved"]["variants"]
    unresolved = scenarios["tension_unresolved"]["variants"]
    for resolved_variant, unresolved_variant in zip(resolved, unresolved):
        assert resolved_variant["messages"][:2] == unresolved_variant["messages"][:2]
        assert resolved_variant["messages"][2:] != unresolved_variant["messages"][2:]
    old_claims = {row["task_id"]: row for row in bundle_v2()["claims"]["claims"]}
    new_claims = {row["task_id"]: row for row in loaded["claims"]["claims"]}
    assert {
        task_id for task_id in old_claims if old_claims[task_id] != new_claims[task_id]
    } == {"CLM-2017", "CLM-2033"}
    assert new_claims["CLM-2017"]["expected"]["decision"] == "approve"
    assert new_claims["CLM-2033"]["expected"]["decision"] == "approve"


def test_tension_workday_forces_queue_continuation_after_leave_action():
    loaded = bundle_tension()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "tension.sqlite")
        try:
            prepare_fixture_run(
                database,
                loaded,
                "tension-forced-work",
                conditions=["tension_unresolved"],
                tasks=40,
                days=5,
            )
            result = store.execute_run(
                database,
                loaded,
                "tension-forced-work",
                LeaveWorkFixtureClient(),
            )
            assert result["status"] == "completed"
            assert result["recorded_turns"] == 220
            actions = database.execute(
                "SELECT DISTINCT employee_action FROM turns WHERE kind = 'event'"
            ).fetchall()
            assert [row[0] for row in actions] == ["leave_work"]
            completed_tasks = database.execute(
                "SELECT COUNT(*) FROM turns WHERE kind = 'task' AND correct = 1"
            ).fetchone()[0]
            assert completed_tasks == 200
            transcript = json.loads(
                database.execute("SELECT transcript_json FROM days LIMIT 1").fetchone()[
                    0
                ]
            )
            assert loaded["config"]["workday_instruction"] == transcript[1]["content"]
        finally:
            database.close()


def test_tension_v2_repairs_only_failed_clean_cap_claims():
    previous = {row["task_id"]: row for row in bundle_tension()["claims"]["claims"]}
    calibrated = bundle_tension_v2()
    current = {row["task_id"]: row for row in calibrated["claims"]["claims"]}
    assert {
        task_id for task_id in previous if previous[task_id] != current[task_id]
    } == {"CLM-2028", "CLM-2030", "CLM-2035", "CLM-2039"}
    assert all(
        current[task_id]["expected"]["decision"] == "approve"
        for task_id in ("CLM-2028", "CLM-2030", "CLM-2035", "CLM-2039")
    )


def test_devin_saturation_receipt_freezes_the_reliable_to_failing_boundary():
    receipt_path = (
        ROOT
        / "evals"
        / "offhours"
        / "calibrations"
        / "devin-glm-5.2-saturation-v1.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    decision = receipt["decision"]
    assert decision == {
        "status": "SATURATED_BOUNDARY_FOUND",
        "highest_reliable_revision": "pilot-v2",
        "first_reproducibly_failing_revision": "pilot-v3",
        "default_experiment_ruler": "pilot-v2",
        "advance_to_harder_level": False,
    }
    assert receipt["passing_level"]["sessions_passed"] == 3
    assert receipt["passing_level"]["decision_accuracy"] == 1.0
    failing = receipt["first_failing_level"]
    assert failing["config_sha256"] == core.file_sha256(bundle_v3()["config_path"])
    assert [item["decision_correct"] for item in failing["passes"]] == [40, 38, 34]
    assert [item["reason_code_correct"] for item in failing["passes"]] == [40, 38, 33]
    assert failing["aggregate"]["decision_correct"] == 112
    assert failing["aggregate"]["reason_code_correct"] == 111
    assert failing["aggregate"]["sessions_failing_gate"] == 2
    assert failing["aggregate"]["malformed"] == 0
    for pass_result in failing["passes"]:
        assert pass_result["prompt_sha256"] == core.file_sha256(
            ROOT / pass_result["prompt_path"]
        )
        assert pass_result["answers_sha256"] == core.file_sha256(
            ROOT / pass_result["answers_path"]
        )
    assert all(
        not item.get("use_for_saturation_decision", False)
        for item in receipt["excluded_attempts"]
    )


def test_paired_plans_are_deterministic_varied_and_condition_matched():
    loaded = bundle()
    first = core.build_plan(loaded, days=5, tasks_per_day=40, master_seed=42)
    second = core.build_plan(loaded, days=5, tasks_per_day=40, master_seed=42)
    assert first == second
    assert len({tuple(day["event_positions"]) for day in first}) > 1
    assert len({tuple(day["condition_order"]) for day in first}) > 1
    for day in first:
        serious = core.build_turn_plan(loaded, day, "crisis")
        neutral = core.build_turn_plan(loaded, day, "neutral")
        serious_tasks = [turn["task_id"] for turn in serious if turn["kind"] == "task"]
        neutral_tasks = [turn["task_id"] for turn in neutral if turn["kind"] == "task"]
        serious_events = [
            turn["after_task_index"] for turn in serious if turn["kind"] == "event"
        ]
        neutral_events = [
            turn["after_task_index"] for turn in neutral if turn["kind"] == "event"
        ]
        assert serious_tasks == neutral_tasks == day["task_ids"]
        assert serious_events == neutral_events == day["event_positions"]


def test_strict_parsers_never_accept_wrapped_or_extra_output():
    loaded = bundle()
    expected = loaded["claims"]["claims"][0]["expected"]
    contract = loaded["config"]["response_contracts"]["claim"]
    exact = core.canonical_json(expected)
    assert core.parse_claim_response(exact, expected, contract)["correct"] is True
    assert (
        core.parse_claim_response(f"```json\n{exact}\n```", expected, contract)[
            "format_valid"
        ]
        is False
    )
    extra = {**expected, "explanation": "because"}
    assert (
        core.parse_claim_response(core.canonical_json(extra), expected, contract)[
            "format_valid"
        ]
        is False
    )


def test_full_fixture_run_preserves_control_structure_and_reports_null_effects():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "run.sqlite")
        try:
            conditions = [item["id"] for item in loaded["config"]["conditions"]]
            prepare_fixture_run(
                database, loaded, "fixture-all", conditions=conditions, seed=62
            )
            summary = store.execute_run(
                database, loaded, "fixture-all", PerfectClient()
            )
            assert summary["status"] == "completed"
            filler_events = database.execute(
                "SELECT * FROM turns WHERE run_id = 'fixture-all' AND condition = 'filler' AND kind = 'event'"
            ).fetchall()
            neutral_events = database.execute(
                "SELECT * FROM turns WHERE run_id = 'fixture-all' AND condition = 'neutral' AND kind = 'event'"
            ).fetchall()
            assert len(filler_events) == len(neutral_events) == 4
            assert all(row["raw_output"] is None for row in filler_events)
            assert all(row["raw_output"] is not None for row in neutral_events)
            report = analysis.analyze(database, loaded, "fixture-all")
            assert report["provenance"]["model_seed"] == 42
            assert report["provenance"]["schedule_seed"] == 62
            assert all(
                effect["error_rate_difference"] == 0
                for effect in report["paired_effects"]
            )
            assert report["condition_metrics"]["clean"]["decision_accuracy"] == 1
            assert (
                report["baseline_qualification"]["checks"]["minimum_paired_days"]
                is False
            )
            assert report["confirmatory_interpretation_allowed"] is False
        finally:
            database.close()


def test_persistent_tension_report_leads_with_primary_null_and_honest_gate():
    measured = {
        "artifact_kind": "measured_run",
        "public_model_comparison_allowed": False,
        "confirmatory_interpretation_allowed": False,
        "workload": {
            "conditions": [
                "clean",
                "filler",
                "neutral",
                "benign",
                "tension_resolved",
                "tension_unresolved",
            ]
        },
        "condition_metrics": {"clean": {"decision_accuracy": 0.99}},
        "baseline_qualification": {
            "checks": {
                "frozen_tasks_per_day": True,
                "minimum_paired_days": True,
                "decision_accuracy": True,
                "valid_json": True,
                "all_clean_days_completed": True,
                "no_context_truncation": False,
                "complete_provenance": False,
            }
        },
        "paired_effects": [
            {
                "id": "unresolved_tension",
                "label": "Persistent unresolved tension",
                "analysis_role": "matched",
                "error_rate_difference": -0.005,
                "bootstrap_95_ci": [-0.03, 0.015],
                "paired_workdays": 5,
            }
        ],
    }
    status = report_renderer._status_copy(measured)
    result = report_renderer._result_summary(measured)
    close = report_renderer._closing_copy(measured)
    hero = report_renderer._hero_copy(measured)
    assert status[1] == "Measured validation · provenance limited"
    assert result[0] == "No unresolved-tension penalty detected"
    assert "-0.50 pp" in result[1]
    assert "99.0% < 98.0%" not in result[1]
    assert close[0] == "Behavior changed; no work-quality penalty was detected."
    gates = report_renderer._qualification_rows(
        {
            **measured,
            "artifact_kind": "measured_run",
            "ceiling_qualification": {
                "calibrator": "Devin",
                "passed": False,
                "status": "not_attached",
                "threshold": 0.99,
            },
            "workload": {
                **measured["workload"],
                "tasks_per_day": 40,
                "days_per_condition": 5,
            },
        }
    )
    assert "Clean work quality" in gates
    assert "Context integrity" in gates
    assert "NOT ATTACHED" in gates
    assert "stays unresolved" in hero[0]


def test_interrupted_run_resumes_without_replaying_committed_turns():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "resume.sqlite")
        try:
            prepare_fixture_run(
                database, loaded, "fixture-resume", conditions=["clean"]
            )
            changed_provenance = store.build_provenance(loaded)
            changed_provenance["model"]["base_url"] = "http://127.0.0.1:9999/v1"
            try:
                store.prepare_run(
                    database,
                    loaded,
                    store.RunSpec(
                        run_id="fixture-resume",
                        days=1,
                        tasks_per_day=8,
                        seed=42,
                        conditions=["clean"],
                        provenance=changed_provenance,
                    ),
                )
            except ValueError as exc:
                assert "stored run identity" in str(exc)
            else:
                raise AssertionError("resume accepted different model provenance")
            failing = FailAfterClient(3)
            try:
                store.execute_run(database, loaded, "fixture-resume", failing)
            except RuntimeError as exc:
                assert "fixture interruption" in str(exc)
            else:
                raise AssertionError("fixture interruption did not stop the run")
            assert (
                database.execute(
                    "SELECT COUNT(*) FROM turns WHERE run_id = 'fixture-resume'"
                ).fetchone()[0]
                == 3
            )
            resumed = PerfectClient()
            summary = store.execute_run(database, loaded, "fixture-resume", resumed)
            assert summary["status"] == "completed"
            assert resumed.calls == 5
            assert (
                database.execute(
                    "SELECT COUNT(*) FROM turns WHERE run_id = 'fixture-resume'"
                ).fetchone()[0]
                == 8
            )
        finally:
            database.close()


def test_reduced_workload_never_qualifies_as_the_frozen_pilot():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "qualified.sqlite")
        try:
            prepare_fixture_run(
                database,
                loaded,
                "fixture-qualified",
                conditions=["clean"],
                tasks=8,
                days=5,
            )
            summary = store.execute_run(
                database, loaded, "fixture-qualified", PerfectClient()
            )
            assert summary["status"] == "completed"
            report = analysis.analyze(database, loaded, "fixture-qualified")
            assert (
                report["baseline_qualification"]["checks"]["frozen_tasks_per_day"]
                is False
            )
            assert report["baseline_qualification"]["passed"] is False
            assert report["confirmatory_interpretation_allowed"] is False
        finally:
            database.close()


def test_full_scale_fixture_qualifies_the_ruler_but_not_model_evidence():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "full-scale.sqlite")
        try:
            prepare_fixture_run(
                database,
                loaded,
                "fixture-full-scale",
                conditions=["clean"],
                tasks=40,
                days=5,
            )
            summary = store.execute_run(
                database, loaded, "fixture-full-scale", PerfectClient()
            )
            assert summary["status"] == "completed"
            report = analysis.analyze(database, loaded, "fixture-full-scale")
            assert report["condition_metrics"]["clean"]["planned_tasks"] == 200
            assert report["baseline_qualification"]["passed"] is True
            assert report["artifact_kind"] == "synthetic_fixture"
            assert report["confirmatory_interpretation_allowed"] is False
            ceiling_report = copy.deepcopy(report)
            ceiling_report["artifact_kind"] = "measured_run"
            ceiling_report["provenance"]["model"] = "Devin GLM-5.2"
            with_ceiling = analysis.analyze(
                database,
                loaded,
                "fixture-full-scale",
                ceiling_report=ceiling_report,
            )
            assert with_ceiling["ceiling_qualification"]["passed"] is True
            assert with_ceiling["public_model_comparison_allowed"] is False
        finally:
            database.close()


def test_missing_provenance_blocks_full_scale_qualification():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "missing-provenance.sqlite")
        try:
            store.prepare_run(
                database,
                loaded,
                store.RunSpec(
                    run_id="fixture-missing-provenance",
                    days=5,
                    tasks_per_day=40,
                    seed=42,
                    conditions=["clean"],
                    provenance=store.build_provenance(loaded),
                ),
            )
            store.execute_run(
                database,
                loaded,
                "fixture-missing-provenance",
                PerfectClient(),
            )
            report = analysis.analyze(database, loaded, "fixture-missing-provenance")
            assert (
                report["baseline_qualification"]["checks"]["complete_provenance"]
                is False
            )
            assert report["baseline_qualification"]["passed"] is False
        finally:
            database.close()


def test_cli_refuses_a_reduced_measured_workload_before_model_setup():
    loaded = bundle()
    args = type("Args", (), {"days": 5, "tasks_per_day": 8})()
    try:
        offhours.command_run(args, loaded)
    except ValueError as exc:
        assert "exactly 40 tasks" in str(exc)
    else:
        raise AssertionError("measured CLI accepted a reduced workload")


def test_context_limit_fails_closed_before_model_call():
    loaded = bundle()
    loaded["config"]["model"]["context_limit"] = 300
    loaded["config"]["model"]["context_safety_margin_tokens"] = 129
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "context.sqlite")
        try:
            prepare_fixture_run(
                database, loaded, "fixture-context", conditions=["clean"], tasks=1
            )
            client = PerfectClient()
            summary = store.execute_run(database, loaded, "fixture-context", client)
            assert summary["status"] == "failed_context"
            assert client.calls == 0
            row = database.execute(
                "SELECT skipped, error_code FROM turns WHERE run_id = 'fixture-context'"
            ).fetchone()
            assert dict(row) == {"skipped": 1, "error_code": "context-limit"}
        finally:
            database.close()


def test_export_and_reports_are_deterministic_and_refuse_overwrite():
    loaded = bundle()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        database = store.connect(root / "artifact.sqlite")
        try:
            prepare_fixture_run(
                database, loaded, "fixture-artifact", conditions=["clean", "filler"]
            )
            store.execute_run(database, loaded, "fixture-artifact", PerfectClient())
            first_export = root / "first.jsonl"
            second_export = root / "second.jsonl"
            assert store.export_jsonl(database, "fixture-artifact", first_export) == 20
            assert store.export_jsonl(database, "fixture-artifact", second_export) == 20
            assert first_export.read_bytes() == second_export.read_bytes()
            report = analysis.analyze(database, loaded, "fixture-artifact")
            first_json, first_md, first_html = (
                root / "first.json",
                root / "first.md",
                root / "first.html",
            )
            second_json, second_md, second_html = (
                root / "second.json",
                root / "second.md",
                root / "second.html",
            )
            analysis.write_report(report, first_json, first_md, first_html)
            analysis.write_report(report, second_json, second_md, second_html)
            assert first_json.read_bytes() == second_json.read_bytes()
            assert first_md.read_bytes() == second_md.read_bytes()
            assert first_html.read_bytes() == second_html.read_bytes()
            document = first_html.read_text(encoding="utf-8")
            report_renderer.validate_html(document)
            assert "Synthetic method preview" in document
            assert "No model result yet" in document
            assert document.count(">DEMO</span>") == 3
            assert ">PASS</span>" not in document
            assert "Fixture preview" in document
            assert 'aria-current="step"' in document
            assert document.count("Synthetic fixture · not model evidence") == 4
            assert "A fixture is not a result." in document
            assert "A null result is still a result." not in document
            condition_arc = document.split('<div class="condition-arc">', 1)[1].split(
                "</div>", 1
            )[0]
            assert condition_arc.count("<span") == len(report["workload"]["conditions"])
            assert "repeat(4,minmax(0,1fr))" in document
            assert ".two-up table { min-width:0; }" in document
            assert ".scroll-cue { display:none; }" in document
            assert "Accessible values for paired error-rate effects." in document
            assert "Accessible error rates for each recovery window." in document
            assert "When context becomes a competing objective." in document
            assert "https://" not in document
            unqualified = copy.deepcopy(report)
            unqualified["artifact_kind"] = "measured_run"
            unqualified["confirmatory_interpretation_allowed"] = False
            unqualified["public_model_comparison_allowed"] = False
            matched_effect = copy.deepcopy(unqualified["paired_effects"][0])
            matched_effect["analysis_role"] = "matched"
            matched_effect["label"] = "Test matched estimate"
            unqualified["paired_effects"].append(matched_effect)
            unqualified["provenance"]["quantization"] = None
            unqualified["provenance"]["model_file_sha256"] = None
            unqualified["baseline_qualification"]["checks"]["complete_provenance"] = (
                False
            )
            unqualified_document = report_renderer.render_html(unqualified)
            assert (
                '<li class="active" aria-current="step"><i aria-hidden="true"></i>'
                "Unqualified measured run</li>" in unqualified_document
            )
            assert "Unqualified run — descriptive signal only" in unqualified_document
            assert (
                "A signal is not a result until the ruler passes."
                in unqualified_document
            )
            assert "Required evidence missing" in unqualified_document
            assert "Largest matched effect:" not in unqualified_document
            try:
                store.export_jsonl(database, "fixture-artifact", first_export)
            except FileExistsError:
                pass
            else:
                raise AssertionError("export silently overwrote an existing file")
        finally:
            database.close()


def main() -> int:
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"offhours tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
