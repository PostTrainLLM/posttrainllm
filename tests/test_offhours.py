#!/usr/bin/env python3
"""Hermetic stdlib tests for the OffHours benchmark artifact."""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import offhours
import offhours_analysis as analysis
import offhours_core as core
import offhours_fixture as fixture
import offhours_report as report_renderer
import offhours_store as store

PerfectClient = fixture.PerfectFixtureClient


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


def bundle() -> dict:
    loaded = core.load_bundle()
    core.validate_bundle(loaded)
    return loaded


def bundle_v2() -> dict:
    loaded = core.load_bundle(ROOT / "configs" / "offhours" / "pilot-v2.json")
    core.validate_bundle(loaded)
    return loaded


def prepare_fixture_run(
    database: sqlite3.Connection,
    loaded: dict,
    run_id: str,
    *,
    conditions: list[str],
    tasks: int = 8,
    days: int = 1,
) -> None:
    provenance = fixture.build_fixture_provenance(loaded)
    store.prepare_run(
        database,
        loaded,
        store.RunSpec(
            run_id=run_id,
            days=days,
            tasks_per_day=tasks,
            seed=42,
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
            prepare_fixture_run(database, loaded, "fixture-all", conditions=conditions)
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
            assert "Accessible values for paired error-rate effects." in document
            assert "Accessible error rates for each recovery window." in document
            assert "When context becomes a competing objective." in document
            assert "https://" not in document
            unqualified = copy.deepcopy(report)
            unqualified["artifact_kind"] = "measured_run"
            unqualified["confirmatory_interpretation_allowed"] = False
            unqualified["public_model_comparison_allowed"] = False
            unqualified_document = report_renderer.render_html(unqualified)
            assert (
                '<li class="active" aria-current="step"><i aria-hidden="true"></i>'
                "Unqualified measured run</li>" in unqualified_document
            )
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
