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

import offhours_analysis as analysis
import offhours_core as core
import offhours_store as store


class PerfectClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], seed: int) -> dict:
        del seed
        self.calls += 1
        prompt = messages[-1]["content"]
        if prompt.startswith("Process this expense claim."):
            claim = json.loads(prompt.splitlines()[1])
            output = core.grade_claim_input(claim)
        else:
            output = {
                "action": "reply_and_continue",
                "reply": "Acknowledged. I will continue the current batch.",
            }
        content = core.canonical_json(output)
        prompt_tokens = sum(len(message["content"].split()) + 4 for message in messages)
        return {
            "content": content,
            "latency_ms": 1.25,
            "context_tokens": prompt_tokens,
            "output_tokens": len(content.split()),
            "endpoint_model": "fixture-perfect",
            "system_fingerprint": "fixture-v1",
        }


class FailAfterClient(PerfectClient):
    def __init__(self, successful_calls: int) -> None:
        super().__init__()
        self.successful_calls = successful_calls

    def complete(self, messages: list[dict[str, str]], seed: int) -> dict:
        if self.calls >= self.successful_calls:
            raise RuntimeError("fixture interruption")
        return super().complete(messages, seed)


def bundle() -> dict:
    loaded = core.load_bundle()
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
    store.prepare_run(
        database,
        loaded,
        store.RunSpec(
            run_id=run_id,
            days=days,
            tasks_per_day=tasks,
            seed=42,
            conditions=conditions,
            provenance=store.build_provenance(loaded),
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


def test_minimum_clean_day_gate_allows_a_qualified_fixture_baseline():
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
            assert report["baseline_qualification"]["passed"] is True
            assert report["confirmatory_interpretation_allowed"] is True
        finally:
            database.close()


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
            first_json, first_md = root / "first.json", root / "first.md"
            second_json, second_md = root / "second.json", root / "second.md"
            analysis.write_report(report, first_json, first_md)
            analysis.write_report(report, second_json, second_md)
            assert first_json.read_bytes() == second_json.read_bytes()
            assert first_md.read_bytes() == second_md.read_bytes()
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
