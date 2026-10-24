"""Persistent specialist workflow acceptance; no model downloads or paid calls."""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from common import Budget, digest, read_json
from data_tools import decision_data, forecast_data, inspect, parse
from jobs import Jobs, atomic
from server import LabRuntime


def decision_rows():
    return [
        {
            "question": f"Which option equals {i}?",
            "left": str(i),
            "right": str(i + 1),
            "answer": "left",
        }
        for i in range(60)
    ]


def test_quoted_csv_bom_multiline_and_duplicate_headers():
    rows, columns = parse('\ufeffquestion,A,B,answer\n"two\nlines","a,b",c,A\n', "csv")
    assert rows[0]["question"] == "two\nlines"
    assert rows[0]["A"] == "a,b" and columns == ["question", "A", "B", "answer"]
    for source in ("a,a\n1,2", "a,b\n1", "a,\n1,2"):
        with pytest.raises(ValueError):
            parse(source, "csv")


def test_guided_decision_import_freezes_splits_and_maps_gold():
    result = decision_data(
        decision_rows(),
        {"question": "question", "answer": "answer", "options": ["left", "right"]},
    )
    splits = result["compare"]["splits"]
    assert [len(splits[k]) for k in ("train", "calibration", "test", "regression")] == [
        42,
        6,
        6,
        6,
    ]
    assert all(r["answer"] == "A" for rows in splits.values() for r in rows)
    assert result["train"]["rows"] == splits["train"]
    assert len({r["id"] for rows in splits.values() for r in rows}) == 60
    with pytest.raises(ValueError, match="leakage"):
        decision_data(
            decision_rows() + decision_rows()[:1],
            {"question": "question", "answer": "answer", "options": ["left", "right"]},
        )


def test_forecast_import_reserves_two_disjoint_future_windows():
    rows = [{"t": i, "y": i * 0.5} for i in range(64)]
    result = forecast_data(rows, {"timestamp": "t", "values": ["y"]}, 8)
    train = result["train"]["rows"][0]
    assert len(train["context"][0]) == 40 and len(train["target"][0]) == 8
    assert result["compare"]["origins"] == [48, 56]
    rows[30]["t"] = 0
    with pytest.raises(ValueError, match="strictly increasing"):
        forecast_data(rows, {"timestamp": "t", "values": ["y"]}, 8)


def test_import_rejects_invalid_values_and_oversized_records():
    with pytest.raises(ValueError, match="800 KB"):
        parse("x" * 800001, "csv")
    with pytest.raises(ValueError, match="missing observations"):
        forecast_data([{"y": "NaN"}] * 64, {"values": ["y"]}, 8)
    with pytest.raises(ValueError, match="at least"):
        forecast_data([{"y": 1}] * 12, {"values": ["y"]}, 8)
    result = inspect({"format": "jsonl", "content": '\n{"a": 1}\n'})
    assert result["count"] == 1 and result["preview"] == [{"a": 1}]


def runtime(root):
    lab = LabRuntime("unused", None, "unused", None, None)
    lab.configure_workspace(root)
    return lab


def wait_for_job(jobs, key):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        row = jobs.read(key)
        if row["status"] not in ("running", "queued"):
            return row
        time.sleep(0.05)
    raise AssertionError("worker did not finish")


def test_real_subprocess_result_survives_restart_and_reuses_recipe(tmp_path):
    manager = Jobs(tmp_path / "jobs")
    request = {
        "mode": "forecast",
        "action": "synthetic",
        "payload": {"seed": 13, "length": 32},
        "runtime": runtime(tmp_path).snapshot(),
    }
    try:
        run = manager.start(request)
        result = wait_for_job(manager, run["run_id"])
        assert result["status"] == "completed", result
        assert result["output"]["result"]["id"] == "synthetic-13"
    finally:
        manager.close()
    reopened = Jobs(tmp_path / "jobs")
    try:
        saved = reopened.read(run["run_id"], recipe=True)
        assert saved["recipe"]["payload"]["seed"] == 13
        assert saved["recipe"]["condition"]["sources"]["job_worker.py"]
        assert saved["dataset_sha256"] == digest(request["payload"])
    finally:
        reopened.close()


def test_workspace_lease_and_interrupted_status_never_kill_stale_pids(tmp_path):
    jobs = Jobs(tmp_path)
    with pytest.raises(ValueError, match="another runtime"):
        Jobs(tmp_path)
    key = "a" * 32
    atomic(
        tmp_path / key / "state.json",
        {
            "run_id": key,
            "status": "running",
            "phase": "training",
            "revision": 1,
            "created_at": "2026-01-01",
        },
    )
    jobs.close()
    reopened = Jobs(tmp_path)
    try:
        assert reopened.read(key)["status"] == "interrupted"
        assert reopened.read(key)["phase"] == "failed"
    finally:
        reopened.close()


def test_cancel_terminates_owned_worker_and_preserves_history(tmp_path):
    jobs = Jobs(tmp_path / "jobs")
    try:
        run = jobs.start(
            {
                "mode": "terminal",
                "action": "train",
                "payload": {"episodes": [], "steps": 200},
                "runtime": runtime(tmp_path).snapshot(),
            }
        )
        process = jobs.process
        cancelled = jobs.cancel(run["run_id"])
        assert cancelled["status"] == "cancelled" and process.poll() is not None
        assert jobs.list()[0]["status"] == "cancelled"
        assert not (jobs.folder(run["run_id"]) / "artifact.json").exists()
    finally:
        jobs.close()


def test_real_terminal_artifact_reopens_after_runtime_restart(tmp_path):
    from test_specialist_labs import tiny_episode

    first = runtime(tmp_path)
    try:
        run = first.start_job(
            "terminal", "train", {"episodes": [tiny_episode()], "steps": 2}
        )
        result = wait_for_job(first.jobs, run["run_id"])
        assert result["status"] == "completed", result
        key = result["output"]["result"]["artifact"]
        first.use_artifact(key)
    finally:
        first.jobs.close()
    second = runtime(tmp_path)
    assert second.active_artifacts["terminal"] == key
    metadata = read_json(second.artifact_path(key) / "specialist.json")
    assert metadata["steps"] == 2 and metadata["run_id"] == run["run_id"]


def test_report_uses_canonical_contract_and_marks_missing_measurements(tmp_path):
    from comparison import report

    result = {
        "metric": "accuracy",
        "baseline": {
            "primary": {"accuracy": 0.5},
            "regression": {"accuracy": 0.5},
            "model_identity": "base",
        },
        "candidate": {
            "primary": {"accuracy": 0.75},
            "regression": {"accuracy": 0.5},
            "model_identity": "candidate",
            "latency_ms": 5,
        },
        "sample_size": 6,
        "regression_size": 6,
        "dataset_sha256": "a" * 64,
        "metadata": {"elapsed_seconds": 1},
    }
    output = report(tmp_path, result, Budget())
    assert output["decision"] == "report-only"
    card = output["report_card"]
    assert card["performance"]["tokens_per_second"]["state"] == "missing"
    assert card["decision"]["verified"] is False
    assert output["primary_delta"] == 0.25
    assert (tmp_path / "report" / "report-card.html").is_file()


def test_budget_emits_observed_losses_and_checks_deadline():
    events = []
    budget = Budget(progress=events.append)
    budget.progress(1, 2, 0.5)
    assert events == [{"step": 1, "total": 2, "loss": 0.5, "phase": "training"}]
    budget.started -= 61
    with pytest.raises(TimeoutError):
        budget.progress(2, 2, 0.1)


def test_artifact_ids_cannot_read_arbitrary_local_paths(tmp_path):
    lab = runtime(tmp_path)
    for key in ("../private", "a" * 33, "/etc/passwd"):
        with pytest.raises(ValueError, match="artifact id"):
            lab.artifact_path(key)


def test_comparison_rejects_changed_training_labels_even_with_same_questions(tmp_path):
    from comparison import verify_training_rows

    key = "b" * 32
    original = [{"question": "same question", "answer": "A"}]
    atomic(tmp_path / "jobs" / key / "request.json", {"payload": {"rows": original}})
    lab = runtime(tmp_path)
    verify_training_rows(lab, {"run_id": key}, original)
    with pytest.raises(ValueError, match="different rows or labels"):
        verify_training_rows(
            lab, {"run_id": key}, [{"question": "same question", "answer": "B"}]
        )


def test_browser_training_step_limit_rejects_booleans():
    from server import bounded_steps

    for value in (True, False, 0, 201):
        with pytest.raises(ValueError):
            bounded_steps({"steps": value})


def test_readiness_requires_every_weight_shard(tmp_path):
    from model_catalog import complete_weights

    atomic(
        tmp_path / "model.safetensors.index.json",
        {"weight_map": {"a": "part-1.safetensors", "b": "part-2.safetensors"}},
    )
    (tmp_path / "part-1.safetensors").write_bytes(b"one shard")
    assert complete_weights(tmp_path) is False
    (tmp_path / "part-2.safetensors").write_bytes(b"second shard")
    assert complete_weights(tmp_path) is True
