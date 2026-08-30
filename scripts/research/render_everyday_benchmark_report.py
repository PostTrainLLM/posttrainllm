#!/usr/bin/env python3
"""Render the deterministic Everyday Specialist Benchmark cohort report."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

import check_everyday_benchmark as checker

ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = ROOT / "configs/everyday-benchmark/suite-v1.json"
ENTRY_DIR = ROOT / "configs/everyday-benchmark/entries"
RECEIPT_DIR = ROOT / "evals/everyday-benchmark/receipts"
DEFAULT_JSON = ROOT / "evals/everyday-benchmark/cohort-v1.json"
DEFAULT_HTML = ROOT / "evals/everyday-benchmark/cohort-v1.html"
PACE_REPORT = "evals/everyday-benchmark/pace-intent-sealed-v1.md"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(value: dict[str, Any], contract: dict[str, Any], path: Path) -> None:
    errors: list[str] = []
    checker.validate_artifact(value, contract, errors)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))


def measurement(entry: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in entry["resources"] if item["name"] == name)


def pareto(rows: list[dict[str, Any]], resource: str) -> dict[str, Any]:
    eligible = []
    excluded = []
    for row in rows:
        item = row["resources"][resource]
        if item["value"] is None:
            excluded.append(
                {
                    "entry_id": row["entry_id"],
                    "reason": f"{resource} is {item['state']}",
                }
            )
        else:
            eligible.append(row)
    frontier = []
    for row in eligible:
        value = row["resources"][resource]["value"]
        dominated = any(
            other["accuracy"] >= row["accuracy"]
            and other["resources"][resource]["value"] <= value
            and (
                other["accuracy"] > row["accuracy"]
                or other["resources"][resource]["value"] < value
            )
            for other in eligible
            if other is not row
        )
        if not dominated:
            frontier.append(row["entry_id"])
    return {
        "resource": resource,
        "direction": "minimize resource, maximize exact accuracy",
        "frontier_entry_ids": sorted(frontier),
        "excluded": sorted(excluded, key=lambda item: item["entry_id"]),
    }


def compile_report() -> dict[str, Any]:
    contract = checker.load_contract()
    suite = load(SUITE_PATH)
    validate(suite, contract, SUITE_PATH)

    tasks = []
    for ref in suite["task_refs"]:
        path = ROOT / ref["path"]
        task = load(path)
        validate(task, contract, path)
        tasks.append(
            {
                "task_id": task["task_id"],
                "title": task["title"],
                "status": task["status"],
                "scorer": task["scorer"],
                "frontier_qualification": task["frontier_qualification"],
                "official_ranking_allowed": task["publication_policy"][
                    "official_ranking_allowed"
                ],
                "public_fixture_ref": task["instance_set"]["path"],
            }
        )
    qualified = [
        task
        for task in tasks
        if task["status"] == "qualified"
        and task["frontier_qualification"]["state"] == "passed"
    ]
    minimum = suite["publication"]["minimum_qualified_task_families"]
    if len(qualified) < minimum:
        raise ValueError(
            f"qualified task count {len(qualified)} is below required {minimum}"
        )

    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(ENTRY_DIR.glob("*.json")):
        entry = load(path)
        validate(entry, contract, path)
        for evidence in entry["evidence"]:
            target = ROOT / evidence["ref"]
            if not target.exists():
                raise ValueError(f"{path}: missing evidence ref {evidence['ref']}")
        entries[entry["entry_id"]] = entry

    rows = []
    receipts = []
    for path in sorted(RECEIPT_DIR.glob("*.json")):
        receipt = load(path)
        validate(receipt, contract, path)
        receipts.append(receipt)
        entry_id = receipt["entry_ref"]["id"]
        entry = entries.get(entry_id)
        if entry is None:
            raise ValueError(f"{path}: missing entry config for {entry_id}")
        aggregate = receipt["aggregate"]
        frontier_score = receipt["frontier_qualification"].get("score")
        resources = {
            name: measurement(entry, name)
            for name in (
                "latency_warm_end_to_end_ms",
                "active_parameters",
                "resident_bytes_peak",
                "installed_artifact_bytes",
                "energy_joules",
                "external_cost_usd",
            )
        }
        rows.append(
            {
                "task_id": receipt["task_ref"]["id"],
                "entry_id": entry_id,
                "title": entry["title"],
                "track": entry["track"],
                "accuracy": aggregate["exact_accuracy"],
                "frontier_capability_retained": (
                    aggregate["exact_accuracy"] / frontier_score
                    if frontier_score
                    else None
                ),
                "slices": {"unknown_recall": aggregate["unknown_recall"]},
                "reliability": {
                    "state": "historical",
                    "consistency_rate": 1.0,
                    "source": PACE_REPORT,
                },
                "selective_risk": {
                    "state": "missing",
                    "reason": "No sealed system-track receipt is committed for this entry.",
                },
                "resources": resources,
                "evidence": entry["evidence"],
                "receipt_ref": str(path.relative_to(ROOT)),
            }
        )
    rows.sort(key=lambda item: (item["task_id"], item["track"], item["entry_id"]))
    return {
        "schema_version": 1,
        "report_id": "everyday-specialist-cohort-v1",
        "as_of": "2026-08-09",
        "suite_ref": {"id": suite["suite_id"], "revision": suite["revision"]},
        "filters": {
            "task_ids": sorted({task["task_id"] for task in tasks}),
            "tracks": sorted({entry["track"] for entry in entries.values()}),
        },
        "qualification": {
            "minimum_task_families": minimum,
            "qualified_task_families": len(qualified),
            "tasks": tasks,
        },
        "results": rows,
        "pareto_views": [
            pareto(rows, "latency_warm_end_to_end_ms"),
            pareto(rows, "active_parameters"),
            pareto(rows, "installed_artifact_bytes"),
            pareto(rows, "resident_bytes_peak"),
            pareto(rows, "energy_joules"),
        ],
        "limitations": [
            "Only Pace intent has a shared sealed cohort; autocorrect and file operations qualify their rulers but are not cross-model headlines.",
            "Selective-risk metrics remain missing until a graph/system entry has a sealed receipt.",
            "Missing resource measurements are excluded from Pareto views, never treated as zero.",
            "decision.json and specialist package decisions remain authoritative outside this benchmark report.",
        ],
    }


def fmt_percent(value: float | None) -> str:
    return "missing" if value is None else f"{100 * value:.1f}%"


def fmt_measurement(item: dict[str, Any]) -> str:
    if item["value"] is None:
        return item["state"]
    value = item["value"]
    return f"{value:,.1f} {item['unit']} ({item['state']})"


def render_html(report: dict[str, Any]) -> str:
    task_options = "".join(
        f'<option value="{html.escape(task)}">{html.escape(task)}</option>'
        for task in report["filters"]["task_ids"]
    )
    track_options = "".join(
        f'<option value="{html.escape(track)}">{html.escape(track)}</option>'
        for track in report["filters"]["tracks"]
    )
    task_rows = "".join(
        "<tr>"
        f"<td>{html.escape(task['title'])}</td>"
        f"<td>{html.escape(task['status'])}</td>"
        f"<td>{fmt_percent(task['frontier_qualification']['score'])}</td>"
        f"<td>{'yes' if task['official_ranking_allowed'] else 'qualification only'}</td>"
        "</tr>"
        for task in report["qualification"]["tasks"]
    )
    result_rows = "".join(
        f'<tr data-task="{html.escape(row["task_id"])}" data-track="{html.escape(row["track"])}">'
        f"<td>{html.escape(row['title'])}</td><td>{html.escape(row['track'])}</td>"
        f"<td>{fmt_percent(row['accuracy'])}</td><td>{fmt_percent(row['frontier_capability_retained'])}</td>"
        f"<td>{fmt_percent(row['slices']['unknown_recall'])}</td>"
        f"<td>{fmt_measurement(row['resources']['latency_warm_end_to_end_ms'])}</td>"
        f"<td>{fmt_measurement(row['resources']['active_parameters'])}</td>"
        f"<td>{html.escape(row['selective_risk']['state'])}</td></tr>"
        for row in report["results"]
    )
    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in report["limitations"]
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Everyday Specialist Benchmark V1</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#171717}}table{{border-collapse:collapse;width:100%;margin:16px 0 32px}}th,td{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}th{{background:#f6f6f6}}label{{margin-right:18px}}select{{margin-left:6px;padding:4px}}.note{{color:#555}}</style></head>
<body><h1>Everyday Specialist Benchmark V1</h1>
<p>{report["qualification"]["qualified_task_families"]} frontier-qualified task families. Only results sharing an instance set are compared.</p>
<h2>Qualification</h2><table><thead><tr><th>Task</th><th>Status</th><th>Frontier</th><th>Headline</th></tr></thead><tbody>{task_rows}</tbody></table>
<h2>Sealed cohort</h2><p><label>Task <select id="task-filter"><option value="">all</option>{task_options}</select></label><label>Track <select id="track-filter"><option value="">all</option>{track_options}</select></label></p>
<table><thead><tr><th>Entry</th><th>Track</th><th>Accuracy</th><th>Frontier retained</th><th>Unknown recall</th><th>Warm latency</th><th>Active parameters</th><th>Selective risk</th></tr></thead><tbody id="results">{result_rows}</tbody></table>
<h2>Limitations</h2><ul>{limitations}</ul><p class="note">Generated deterministically from committed task, entry, and receipt artifacts. No model or provider was invoked.</p>
<script>const tf=document.querySelector('#task-filter'),kf=document.querySelector('#track-filter');function apply(){{for(const row of document.querySelectorAll('#results tr'))row.hidden=(tf.value&&row.dataset.task!==tf.value)||(kf.value&&row.dataset.track!==kf.value)}}tf.addEventListener('change',apply);kf.addEventListener('change',apply);</script>
</body></html>\n"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = compile_report()
        json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        html_text = render_html(report)
        if args.check:
            if args.json_out.read_text(encoding="utf-8") != json_text:
                raise ValueError(f"report drift: {args.json_out}")
            if args.html_out.read_text(encoding="utf-8") != html_text:
                raise ValueError(f"report drift: {args.html_out}")
        else:
            args.json_out.write_text(json_text, encoding="utf-8")
            args.html_out.write_text(html_text, encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"everyday benchmark report failed: {exc}", file=sys.stderr)
        return 1
    print("everyday benchmark report: clean; no model or provider invoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
