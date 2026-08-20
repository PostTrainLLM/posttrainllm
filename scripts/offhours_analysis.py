#!/usr/bin/env python3
"""Workday-clustered analysis and deterministic reporting for OffHours."""

from __future__ import annotations

import json
import math
import random
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import offhours_core as core


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(sorted_values: list[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _count_truthy(rows: list[sqlite3.Row], field: str) -> int:
    return sum(bool(row[field]) for row in rows)


def _count_equal(rows: list[sqlite3.Row], field: str, expected: Any) -> int:
    return sum(row[field] == expected for row in rows)


def _non_null_values(
    rows: list[sqlite3.Row], field: str, cast: type[float | int]
) -> list[float] | list[int]:
    return [cast(row[field]) for row in rows if row[field] is not None]


def _condition_metrics(
    database: sqlite3.Connection,
    run_id: str,
    condition: str,
    tasks_per_day: int,
) -> dict[str, Any]:
    days = database.execute(
        "SELECT status, context_verified FROM days WHERE run_id = ? AND condition = ?",
        (run_id, condition),
    ).fetchall()
    task_rows = database.execute(
        "SELECT * FROM turns WHERE run_id = ? AND condition = ? AND kind = 'task'",
        (run_id, condition),
    ).fetchall()
    planned_tasks = len(days) * tasks_per_day
    answered = [row for row in task_rows if row["raw_output"] is not None]
    latencies = _non_null_values(answered, "latency_ms", float)
    contexts = _non_null_values(answered, "context_tokens", int)
    outputs = _non_null_values(answered, "output_tokens", int)
    completed_days = _count_equal(days, "status", "completed")
    return {
        "planned_days": len(days),
        "completed_days": completed_days,
        "workday_completion_rate": _rate(completed_days, len(days)),
        "planned_tasks": planned_tasks,
        "answered_tasks": len(answered),
        "decision_accuracy": _rate(
            _count_truthy(answered, "decision_correct"), planned_tasks
        ),
        "reason_code_accuracy": _rate(
            _count_truthy(answered, "reason_code_valid"), planned_tasks
        ),
        "valid_json_rate": _rate(
            _count_truthy(answered, "format_valid"), planned_tasks
        ),
        "malformed_output_rate": _rate(
            len(answered) - _count_truthy(answered, "format_valid"), planned_tasks
        ),
        "skipped_task_rate": _rate(planned_tasks - len(answered), planned_tasks),
        "exact_correct_rate": _rate(_count_truthy(answered, "correct"), planned_tasks),
        "escalation_rate": _rate(
            _count_equal(answered, "actual_decision", "escalate"), len(answered)
        ),
        "latency_ms_mean": _mean(latencies),
        "context_tokens_mean": _mean(contexts),
        "context_tokens_max": max(contexts) if contexts else None,
        "output_tokens_mean": _mean(outputs),
        "context_verified_days": _count_truthy(days, "context_verified"),
    }


def _paired_day_errors(
    database: sqlite3.Connection,
    run_id: str,
    condition: str,
    tasks_per_day: int,
) -> dict[str, float]:
    rows = database.execute(
        """
        SELECT d.day_id, SUM(CASE WHEN t.correct = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM days AS d
        JOIN turns AS t USING (run_id, day_id, condition)
        WHERE d.run_id = ? AND d.condition = ? AND d.status = 'completed' AND t.kind = 'task'
        GROUP BY d.day_id
        """,
        (run_id, condition),
    ).fetchall()
    return {row["day_id"]: 1 - row["correct_count"] / tasks_per_day for row in rows}


def _paired_effect(
    database: sqlite3.Connection,
    run_id: str,
    comparison: dict[str, str],
    tasks_per_day: int,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    treatment = _paired_day_errors(
        database, run_id, comparison["treatment"], tasks_per_day
    )
    control = _paired_day_errors(database, run_id, comparison["control"], tasks_per_day)
    paired_days = sorted(set(treatment) & set(control))
    differences = [treatment[day] - control[day] for day in paired_days]
    bootstrap: list[float] = []
    rng = random.Random(core.derive_seed(seed, comparison["id"]))
    if differences:
        for _ in range(samples):
            bootstrap.append(
                statistics.fmean(rng.choice(differences) for _ in differences)
            )
        bootstrap.sort()
    adjusted = _context_adjusted_effect(database, run_id, comparison)
    return {
        "id": comparison["id"],
        "treatment": comparison["treatment"],
        "control": comparison["control"],
        "paired_workdays": len(paired_days),
        "error_rate_difference": _mean(differences),
        "difference_percentage_points": _mean([value * 100 for value in differences]),
        "bootstrap_95_ci": [
            _percentile(bootstrap, 0.025),
            _percentile(bootstrap, 0.975),
        ],
        "context_adjusted_error_difference": adjusted,
        "interpretation": "positive means more work errors in treatment",
    }


def _solve_three(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                left - factor * right
                for left, right in zip(augmented[row], augmented[column])
            ]
    return [augmented[index][3] for index in range(3)]


def _context_adjusted_effect(
    database: sqlite3.Connection,
    run_id: str,
    comparison: dict[str, str],
) -> float | None:
    rows = database.execute(
        """
        SELECT t.condition, t.correct, t.context_tokens
        FROM turns AS t
        JOIN days AS d USING (run_id, day_id, condition)
        WHERE t.run_id = ? AND t.kind = 'task' AND d.status = 'completed'
          AND t.condition IN (?, ?) AND t.context_tokens IS NOT NULL
        """,
        (run_id, comparison["treatment"], comparison["control"]),
    ).fetchall()
    if len(rows) < 6:
        return None
    contexts = [float(row["context_tokens"]) for row in rows]
    center = statistics.fmean(contexts)
    scale = statistics.pstdev(contexts) or 1.0
    design = [
        [
            1.0,
            float(row["condition"] == comparison["treatment"]),
            (float(row["context_tokens"]) - center) / scale,
        ]
        for row in rows
    ]
    outcomes = [1.0 - float(bool(row["correct"])) for row in rows]
    matrix = [
        [sum(left[i] * left[j] for left in design) for j in range(3)] for i in range(3)
    ]
    vector = [
        sum(left[i] * outcome for left, outcome in zip(design, outcomes))
        for i in range(3)
    ]
    solved = _solve_three(matrix, vector)
    return solved[1] if solved else None


def _recovery_metrics(
    database: sqlite3.Connection, run_id: str, config: dict[str, Any]
) -> dict[str, Any]:
    rows = database.execute(
        """
        SELECT t.condition, t.correct, t.distance_from_last_event
        FROM turns AS t JOIN days AS d USING (run_id, day_id, condition)
        WHERE t.run_id = ? AND t.kind = 'task' AND d.status = 'completed'
        """,
        (run_id,),
    ).fetchall()
    result: dict[str, Any] = {}
    for condition in (
        item["id"] for item in config["conditions"] if item["id"] != "clean"
    ):
        condition_rows = [row for row in rows if row["condition"] == condition]
        bands: dict[str, Any] = {}
        for band in config["analysis"]["recovery_bands"]:
            if band["id"] == "pre_event":
                selected = [
                    row
                    for row in condition_rows
                    if row["distance_from_last_event"] is None
                ]
            else:
                selected = [
                    row
                    for row in condition_rows
                    if row["distance_from_last_event"] is not None
                    and band["minimum"]
                    <= row["distance_from_last_event"]
                    <= band["maximum"]
                ]
            bands[band["id"]] = {
                "tasks": len(selected),
                "error_rate": _rate(
                    sum(not bool(row["correct"]) for row in selected), len(selected)
                ),
            }
        result[condition] = bands
    return result


def _behavior_metrics(database: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    rows = database.execute(
        "SELECT condition, format_valid, employee_action, reply_length FROM turns WHERE run_id = ? AND kind = 'event' AND raw_output IS NOT NULL",
        (run_id,),
    ).fetchall()
    result: dict[str, Any] = {}
    for condition in sorted({row["condition"] for row in rows}):
        selected = [row for row in rows if row["condition"] == condition]
        actions = Counter(row["employee_action"] or "malformed" for row in selected)
        lengths = [
            row["reply_length"] for row in selected if row["reply_length"] is not None
        ]
        result[condition] = {
            "events": len(selected),
            "valid_action_rate": _rate(
                sum(bool(row["format_valid"]) for row in selected), len(selected)
            ),
            "actions": dict(sorted(actions.items())),
            "reply_length_mean_characters": _mean([float(value) for value in lengths]),
        }
    return result


def _task_fragility(database: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = database.execute(
        """
        SELECT t.task_id, t.condition, t.correct
        FROM turns AS t JOIN days AS d USING (run_id, day_id, condition)
        WHERE t.run_id = ? AND t.kind = 'task' AND d.status = 'completed'
        """,
        (run_id,),
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["task_id"]].append(row)
    output = []
    for task_id, task_rows in sorted(grouped.items()):
        by_condition = {
            condition: _rate(
                sum(
                    not bool(row["correct"])
                    for row in task_rows
                    if row["condition"] == condition
                ),
                sum(row["condition"] == condition for row in task_rows),
            )
            for condition in sorted({row["condition"] for row in task_rows})
        }
        values = [value for value in by_condition.values() if value is not None]
        output.append(
            {
                "task_id": task_id,
                "error_rate_by_condition": by_condition,
                "error_rate_range": max(values) - min(values) if values else None,
            }
        )
    return output


def _verify_contract_identity(run: sqlite3.Row, bundle: dict[str, Any]) -> None:
    validation = core.validate_bundle(bundle)
    provenance = json.loads(run["provenance_json"])
    current = (
        validation["config_sha256"],
        validation["claims_sha256"],
        validation["scenarios_sha256"],
        validation["system_prompt_sha256"],
    )
    stored = (
        run["config_sha256"],
        provenance["claims_sha256"],
        provenance["scenarios_sha256"],
        provenance["system_prompt_sha256"],
    )
    if current != stored:
        raise ValueError(
            "current OffHours contracts do not match the stored run identity"
        )


def analyze(
    database: sqlite3.Connection, bundle: dict[str, Any], run_id: str
) -> dict[str, Any]:
    database.row_factory = sqlite3.Row
    run = database.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"unknown run_id: {run_id}")
    _verify_contract_identity(run, bundle)
    config = bundle["config"]
    conditions = json.loads(run["conditions_json"])
    metrics = {
        condition: _condition_metrics(database, run_id, condition, run["tasks_per_day"])
        for condition in conditions
    }
    effects = [
        _paired_effect(
            database,
            run_id,
            comparison,
            run["tasks_per_day"],
            config["analysis"]["bootstrap_samples"],
            config["analysis"]["bootstrap_seed"],
        )
        for comparison in config["analysis"]["comparisons"]
        if comparison["treatment"] in conditions and comparison["control"] in conditions
    ]
    clean = metrics.get("clean")
    qualification = None
    if clean:
        gates = config["qualification"]
        checks = {
            "minimum_paired_days": clean["planned_days"]
            >= config["workload"]["days_per_condition_min"],
            "decision_accuracy": (clean["decision_accuracy"] or 0)
            >= gates["clean_decision_accuracy_minimum"],
            "valid_json": (clean["valid_json_rate"] or 0)
            >= gates["clean_valid_json_minimum"],
            "no_context_truncation": clean["context_verified_days"]
            == clean["planned_days"],
            "all_clean_days_completed": clean["completed_days"]
            == clean["planned_days"],
        }
        qualification = {"passed": all(checks.values()), "checks": checks}
    return {
        "schema_version": "offhours/analysis/v1",
        "run_id": run_id,
        "run_status": run["status"],
        "config_sha256": run["config_sha256"],
        "primary_uncertainty_unit": "paired workday",
        "condition_metrics": metrics,
        "paired_effects": effects,
        "recovery": _recovery_metrics(database, run_id, config),
        "behavior": _behavior_metrics(database, run_id),
        "task_fragility": _task_fragility(database, run_id),
        "baseline_qualification": qualification,
        "confirmatory_interpretation_allowed": bool(
            qualification and qualification["passed"] and run["status"] == "completed"
        ),
        "control_caveat": config["token_matching"]["filler_control_note"],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# OffHours pilot — {report['run_id']}",
        "",
        "## Interpretation status",
        "",
        f"- Run status: `{report['run_status']}`",
        f"- Confirmatory interpretation allowed: `{str(report['confirmatory_interpretation_allowed']).lower()}`",
        f"- Control caveat: {report['control_caveat']}",
        "",
        "## Work quality",
        "",
        "| Condition | Decision accuracy | Valid JSON | Skipped tasks | Completed days |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for condition, metrics in report["condition_metrics"].items():
        lines.append(
            f"| {condition} | {_format_rate(metrics['decision_accuracy'])} | {_format_rate(metrics['valid_json_rate'])} | "
            f"{_format_rate(metrics['skipped_task_rate'])} | {metrics['completed_days']}/{metrics['planned_days']} |"
        )
    lines.extend(
        [
            "",
            "## Paired error effects",
            "",
            "Positive values mean more treatment errors.",
            "",
        ]
    )
    lines.extend(
        [
            "| Comparison | Treatment - control | Paired days | 95% paired bootstrap CI | Context-adjusted |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for effect in report["paired_effects"]:
        interval = effect["bootstrap_95_ci"]
        lines.append(
            f"| {effect['id']} | {_format_pp(effect['error_rate_difference'])} | {effect['paired_workdays']} | "
            f"{_format_pp(interval[0])} to {_format_pp(interval[1])} | {_format_pp(effect['context_adjusted_error_difference'])} |"
        )
    lines.extend(
        [
            "",
            "## Baseline qualification",
            "",
            f"Passed: `{str(bool(report['baseline_qualification'] and report['baseline_qualification']['passed'])).lower()}`",
            "",
        ]
    )
    if report["baseline_qualification"]:
        for name, passed in report["baseline_qualification"]["checks"].items():
            lines.append(f"- {name}: `{'pass' if passed else 'fail'}`")
    lines.extend(
        [
            "",
            "A null result is valid; do not tune scenarios after inspecting confirmatory outcomes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    report: dict[str, Any], json_path: Path, markdown_path: Path, *, force: bool = False
) -> None:
    for path in (json_path, markdown_path):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def _format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _format_pp(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.2f} pp"
