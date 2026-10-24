"""Owned specialist worker; launched by jobs.py, never by browser-provided code."""

from __future__ import annotations

import sys
from pathlib import Path

from common import Budget, read_json
from jobs import atomic


def work(folder):
    request = read_json(folder / "request.json")
    losses = []

    def progress(event):
        if event.get("loss") is not None:
            losses.append({"step": event["step"], "loss": event["loss"]})
        atomic(folder / "progress.json", {**event, "losses": losses[-200:]})

    budget = Budget(170, progress=progress)
    progress({"phase": "loading runtime", "step": 0, "total": 0})
    if request["mode"] == "model":
        from model_catalog import download

        return {
            "result": download(request["payload"]["model"]),
            "measurements": budget.measurements(),
        }
    from server import LabRuntime

    runtime = LabRuntime.from_snapshot(request["runtime"], restore=False)
    runtime.budget = budget
    mode, action, payload = request["mode"], request["action"], request["payload"]
    if action == "ceiling" and mode == "decision":
        from decision_eval import ceiling

        ceiling(payload["rows"], folder / "ceiling")
        return {
            "result": {"ceiling": read_json(folder / "ceiling" / "ceiling.json")},
            "measurements": budget.measurements(),
        }
    if action == "compare":
        from comparison import decision_compare, forecast_compare, report

        compare = {"decision": decision_compare, "forecast": forecast_compare}.get(mode)
        if compare is None:
            raise ValueError(
                "terminal comparisons need a separately qualified benchmark"
            )
        result = compare(runtime, payload, budget)
        return {
            "result": report(folder, result, budget),
            "measurements": budget.measurements(),
        }
    output = runtime.run(mode, action, payload)
    if action == "train":
        key = output["result"]["artifact"]
        path = runtime.artifact_path(key) / "specialist.json"
        atomic(path, {**read_json(path), "run_id": folder.name})
        # Only complete jobs become discoverable model artifacts.
        atomic(folder / "artifact.json", {"artifact": key})
    return output


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve()
    try:
        atomic(target / "result.json", work(target))
    except Exception as error:
        atomic(target / "error.json", {"error": str(error)[:1000]})
        raise SystemExit(1) from None
