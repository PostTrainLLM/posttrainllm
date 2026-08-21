"""Self-contained publication renderer for OffHours analysis reports."""

from __future__ import annotations

import html
from html.parser import HTMLParser
from typing import Any

CONDITION_LABELS = {
    "clean": "Clean",
    "filler": "Filler",
    "neutral": "Neutral",
    "benign": "Benign family",
    "moderate": "Moderate problem",
    "crisis": "Crisis",
    "tension_resolved": "Resolved tension",
    "tension_unresolved": "Unresolved tension",
    "occupancy_neutral": "Neutral-only occupancy",
    "occupancy_resolved_20": "Resolved occupancy 20%",
    "occupancy_unresolved_20": "Unresolved occupancy 20%",
    "occupancy_resolved_50": "Resolved occupancy 50%",
    "occupancy_unresolved_50": "Unresolved occupancy 50%",
    "occupancy_resolved_80": "Resolved occupancy 80%",
    "occupancy_unresolved_80": "Unresolved occupancy 80%",
}
CONDITION_COLORS = {
    "clean": "#a6adb9",
    "filler": "#737b88",
    "neutral": "#eaedf2",
    "benign": "#48e5c2",
    "moderate": "#a6adb9",
    "crisis": "#ff6f5c",
    "tension_resolved": "#a6adb9",
    "tension_unresolved": "#ff6f5c",
    "occupancy_neutral": "#737b88",
    "occupancy_resolved_20": "#a6adb9",
    "occupancy_unresolved_20": "#ff6f5c",
    "occupancy_resolved_50": "#a6adb9",
    "occupancy_unresolved_50": "#ff6f5c",
    "occupancy_resolved_80": "#48e5c2",
    "occupancy_unresolved_80": "#ff6f5c",
}
RECOVERY_DASHES = {
    "filler": "2 6",
    "neutral": "8 5",
    "benign": "",
    "moderate": "12 5",
    "crisis": "4 4",
    "tension_resolved": "12 5",
    "tension_unresolved": "4 4",
    "occupancy_neutral": "2 6",
    "occupancy_resolved_20": "12 5",
    "occupancy_unresolved_20": "4 4",
    "occupancy_resolved_50": "12 5",
    "occupancy_unresolved_50": "4 4",
    "occupancy_resolved_80": "12 5",
    "occupancy_unresolved_80": "4 4",
}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _rate(value: float | None) -> str:
    return "Not measured" if value is None else f"{value:.1%}"


def _pp(value: float | None) -> str:
    return "Not measured" if value is None else f"{value * 100:+.2f} pp"


def _number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "Not measured"
    return f"{value:,.1f}{suffix}" if isinstance(value, float) else f"{value:,}{suffix}"


def _short_hash(value: str | None) -> str:
    return "missing" if not value else f"{value[:12]}…{value[-8:]}"


def _is_persistent_tension(report: dict[str, Any]) -> bool:
    conditions = set((report.get("workload") or {}).get("conditions") or [])
    return {"tension_resolved", "tension_unresolved"} <= conditions


def _is_occupancy(report: dict[str, Any]) -> bool:
    conditions = set((report.get("workload") or {}).get("conditions") or [])
    return {"occupancy_resolved_20", "occupancy_unresolved_80"} <= conditions


def _hero_copy(report: dict[str, Any]) -> tuple[str, str, str, str]:
    if _is_occupancy(report):
        return (
            "Does unresolved context become harder to ignore as it grows?",
            "OffHours holds injected non-work text constant while family material replaces neutral material at 20%, 50%, and 80% occupancy. Resolved and unresolved twins carry identical word budgets.",
            "Fixed-volume semantic dose",
            "20% → 50% → 80% family occupancy",
        )
    if _is_persistent_tension(report):
        return (
            "What happens when a problem stays unresolved?",
            "OffHours measures whether routine claim work changes when the same nonurgent family-health problem either gains a credible plan or remains open—and every assigned claim still has to be processed.",
            "Matched life tension",
            "Identical opening → resolved or unresolved responsibility",
        )
    return (
        "When context becomes a competing objective.",
        "OffHours measures whether one model’s routine expense-claim work changes after passive context, ordinary interruptions, and increasingly consequential family obligations.",
        "Six controlled conditions",
        "Token volume → interruption → family obligation",
    )


def _status_copy(report: dict[str, Any]) -> tuple[str, str, str]:
    if report["artifact_kind"] == "synthetic_fixture":
        return (
            "method-preview",
            "Synthetic method preview",
            "The pipeline is exercised end to end, but every displayed score comes from a perfect fixture—not a model experiment.",
        )
    if report["public_model_comparison_allowed"]:
        return (
            "verified",
            "Public comparison ready",
            "The measured run, frozen workload, provenance, and Devin ceiling checks all passed.",
        )
    if report["confirmatory_interpretation_allowed"]:
        return (
            "caution",
            "Measured run; ceiling required",
            "The run qualifies for internal interpretation, but public model comparison remains locked until the Devin ceiling passes.",
        )
    checks = (report.get("baseline_qualification") or {}).get("checks", {})
    if _is_persistent_tension(report) and all(
        checks.get(name, False)
        for name in (
            "frozen_tasks_per_day",
            "minimum_paired_days",
            "decision_accuracy",
            "valid_json",
            "all_clean_days_completed",
        )
    ):
        return (
            "validation",
            "Measured validation · provenance limited",
            "Workload, clean accuracy, valid JSON, and paired-workday gates passed. Baseline qualification remains held because Devin CLI cannot verify prompt-token context usage or complete model provenance.",
        )
    return (
        "blocked",
        "Qualification incomplete",
        "This run is evidence about the harness or a failed calibration—not a confirmatory benchmark result.",
    )


def _gate_presentation(
    *, is_fixture: bool, fixture_demo: bool, passed: bool, override: str | None
) -> tuple[str, str]:
    if fixture_demo:
        return "demo", "DEMO"
    if is_fixture:
        return "hold", "HOLD"
    if override:
        return "hold", override
    return ("pass", "PASS") if passed else ("hold", "HOLD")


def _qualification_rows(report: dict[str, Any]) -> str:
    qualification = report.get("baseline_qualification") or {"checks": {}}
    checks = qualification["checks"]
    ceiling = report["ceiling_qualification"]
    rows = [
        (
            "Frozen workload",
            checks.get("frozen_tasks_per_day", False),
            f"{report['workload']['tasks_per_day']} claims × {report['workload']['days_per_condition']} paired days",
        ),
        (
            "Clean work quality",
            all(
                checks.get(name, False)
                for name in (
                    "minimum_paired_days",
                    "decision_accuracy",
                    "valid_json",
                    "all_clean_days_completed",
                )
            ),
            "≥98% decisions · ≥99% valid JSON · every clean day complete",
            None,
        ),
        (
            "Context integrity",
            checks.get("no_context_truncation", False),
            (
                "Prompt-token counts verify no truncation"
                if checks.get("no_context_truncation", False)
                else "Devin CLI does not expose prompt-token counts; no-truncation verification is unavailable"
            ),
            None,
        ),
        (
            "Complete provenance",
            checks.get("complete_provenance", False),
            "Model hash · quantization · server version · endpoint identity",
            None,
        ),
        (
            f"Frontier-ceiling calibration — {ceiling['calibrator']}",
            ceiling["passed"],
            f"≥{ceiling['threshold']:.0%} clean accuracy on the same frozen ruler",
            "NOT ATTACHED" if ceiling.get("status") == "not_attached" else None,
        ),
    ]
    rendered = []
    for index, row in enumerate(rows):
        label, passed, detail, *state_override = row
        is_fixture = report["artifact_kind"] == "synthetic_fixture"
        fixture_demo = is_fixture and index < 3
        state, word = _gate_presentation(
            is_fixture=is_fixture,
            fixture_demo=fixture_demo,
            passed=passed,
            override=state_override[0] if state_override else None,
        )
        rendered.append(
            f'<li><span class="gate-mark {state}">{word}</span>'
            f"<div><strong>{_escape(label)}</strong><span>{_escape(detail)}</span></div></li>"
        )
    return "".join(rendered)


def _evidence_ladder(report: dict[str, Any]) -> str:
    if report["public_model_comparison_allowed"]:
        active = "public"
    elif report["confirmatory_interpretation_allowed"]:
        active = "qualified"
    elif report["artifact_kind"] == "measured_run":
        active = "unqualified"
    else:
        active = "fixture"
    steps = (
        ("fixture", "Fixture preview"),
        ("unqualified", "Unqualified measured run"),
        ("qualified", "Qualified model result"),
        ("public", "Public comparison"),
    )
    return "".join(
        '<li class="{class_name}"{current}><i aria-hidden="true"></i>{label}</li>'.format(
            class_name="active" if identifier == active else "",
            current=' aria-current="step"' if identifier == active else "",
            label=_escape(label),
        )
        for identifier, label in steps
    )


def _persistent_tension_result_summary(
    report: dict[str, Any], matched: list[dict[str, Any]]
) -> tuple[str, str] | None:
    primary = next(
        (effect for effect in matched if effect["id"] == "unresolved_tension"),
        None,
    )
    if primary is None:
        return None
    low, high = primary["bootstrap_95_ci"]
    result = primary["error_rate_difference"]
    direction = (
        "No unresolved-tension penalty detected"
        if result is not None and result <= 0
        else "Unresolved-tension penalty remains uncertain"
    )
    suffix = (
        " Devin provenance remains incomplete, so this is validation evidence rather than a confirmatory local-model result."
        if not report["confirmatory_interpretation_allowed"]
        else ""
    )
    return (
        direction,
        f"Unresolved minus resolved error rate: {_pp(result)}; 95% paired-workday interval {_pp(low)} to {_pp(high)}.{suffix}",
    )


def _occupancy_result_summary(report: dict[str, Any]) -> tuple[str, str] | None:
    dose = report.get("occupancy_dose_response")
    if not dose or not dose["paired_workdays"]:
        return None
    low, high = dose["slope_bootstrap_95_ci"]
    slope = dose["slope_per_10_occupancy_points"]
    title = (
        "Unresolved interference increased with occupancy"
        if low is not None and low > 0
        else "No reliable occupancy-dose penalty detected"
    )
    monotonic = "yes" if dose["monotonic_adverse_point_estimates"] else "no"
    return (
        title,
        f"Unresolved-minus-resolved error slope per +10 occupancy points: {_pp(slope)}; 95% paired-workday interval {_pp(low)} to {_pp(high)}. Monotonic adverse point estimates: {monotonic}.",
    )


def _result_summary(report: dict[str, Any]) -> tuple[str, str]:
    if report["artifact_kind"] == "synthetic_fixture":
        return (
            "No model result yet",
            "The fixture proves scheduling, grading, persistence, analysis, and rendering. It makes no claim about context interference.",
        )
    matched = [
        effect
        for effect in report["paired_effects"]
        if effect["analysis_role"] == "matched"
        and effect["error_rate_difference"] is not None
    ]
    if not matched:
        return ("Result not estimable", "No completed matched comparison is available.")
    occupancy_summary = _occupancy_result_summary(report)
    if occupancy_summary is not None:
        return occupancy_summary
    primary_summary = _persistent_tension_result_summary(report, matched)
    if primary_summary is not None:
        return primary_summary
    largest = max(matched, key=lambda effect: abs(effect["error_rate_difference"]))
    if not report["confirmatory_interpretation_allowed"]:
        clean_accuracy = report["condition_metrics"]["clean"]["decision_accuracy"]
        provenance_complete = (
            (report.get("baseline_qualification") or {})
            .get("checks", {})
            .get("complete_provenance", False)
        )
        provenance_state = (
            "model identity complete"
            if provenance_complete
            else "required model identity incomplete"
        )
        clean_gate_passed = clean_accuracy is not None and clean_accuracy >= 0.98
        clean_state = (
            f"clean baseline {_rate(clean_accuracy)} passed"
            if clean_gate_passed
            else f"clean baseline {_rate(clean_accuracy)} < 98.0%"
        )
        detail = "".join(
            (
                f"Largest matched estimate: {_pp(largest['error_rate_difference'])} ",
                f"for {largest['label']}. Qualification is blocked: {clean_state}; ",
                f"{provenance_state}.",
            )
        )
        return (
            "Unqualified run — descriptive signal only",
            detail,
        )
    return (
        f"Largest matched effect: {_pp(largest['error_rate_difference'])}",
        f"{largest['label']} across {largest['paired_workdays']} paired workdays; inspect its interval before interpreting direction.",
    )


def _fixture_label(report: dict[str, Any]) -> str:
    if report["artifact_kind"] != "synthetic_fixture":
        return ""
    return '<p class="fixture-label">Synthetic fixture · not model evidence</p>'


def _closing_copy(report: dict[str, Any]) -> tuple[str, str]:
    if report["artifact_kind"] == "synthetic_fixture":
        return (
            "A fixture is not a result.",
            "This preview proves the benchmark pipeline and publication format. It contains no evidence about model behavior or context interference.",
        )
    if not report["confirmatory_interpretation_allowed"]:
        if _is_occupancy(report):
            return (
                "Semantic occupancy is not a stress meter.",
                "This design tests whether unresolved personal material interferes with routine work beyond a byte-matched resolved control. Devin token provenance remains incomplete, and a null or non-monotonic slope must be preserved.",
            )
        if _is_persistent_tension(report):
            primary = next(
                (
                    effect
                    for effect in report.get("paired_effects", [])
                    if effect.get("id") == "unresolved_tension"
                ),
                None,
            )
            behavior = report.get("behavior") or {}
            resolved_reply = (behavior.get("tension_resolved") or {}).get(
                "reply_length_mean_characters"
            )
            unresolved_reply = (behavior.get("tension_unresolved") or {}).get(
                "reply_length_mean_characters"
            )
            reply_detail = "Unresolved tension produced longer replies."
            if resolved_reply is not None and unresolved_reply is not None:
                reply_detail = (
                    f"Unresolved replies averaged {unresolved_reply - resolved_reply:+.0f} characters "
                    "longer than resolved replies."
                )
            effect_detail = "The work-quality effect was not estimable."
            if primary is not None:
                low, high = primary["bootstrap_95_ci"]
                effect_detail = (
                    f"Its error-rate difference was {_pp(primary['error_rate_difference'])} "
                    f"(95% paired-workday interval {_pp(low)} to {_pp(high)}; "
                    f"{primary['paired_workdays']} paired days)."
                )
            return (
                "Behavior changed; no work-quality penalty was detected.",
                f"{reply_detail} {effect_detail} Devin provenance remains incomplete.",
            )
        return (
            "A signal is not a result until the ruler passes.",
            "This run found descriptive differences, but its 95% clean baseline and incomplete model provenance block confirmatory interpretation. Repair the ruler, then rerun the same paired design.",
        )
    return (
        "Qualified evidence can support a null result.",
        "OffHours succeeds when it distinguishes personally relevant competing objectives from ordinary prompt length and interruption structure—even if the qualified model remains unaffected.",
    )


def _condition_table(report: dict[str, Any]) -> str:
    rows = []
    for condition, metrics in report["condition_metrics"].items():
        rows.append(
            "<tr>"
            f'<th scope="row"><span class="condition-dot" style="--condition:{CONDITION_COLORS[condition]}"></span>{_escape(CONDITION_LABELS[condition])}</th>'
            f"<td>{_rate(metrics['decision_accuracy'])}</td>"
            f"<td>{_rate(metrics['valid_json_rate'])}</td>"
            f"<td>{_rate(metrics['skipped_task_rate'])}</td>"
            f"<td>{metrics['completed_days']}/{metrics['planned_days']}</td>"
            f"<td>{_number(metrics['latency_ms_mean'], ' ms')}</td>"
            "</tr>"
        )
    return "".join(rows)


def _accuracy_chart(report: dict[str, Any]) -> str:
    metrics = report["condition_metrics"]
    width, row_height = 880, 54
    left, right = 176, 72
    plot_width = width - left - right
    height = 50 + row_height * len(metrics)
    rows = []
    for index, (condition, values) in enumerate(metrics.items()):
        y = 42 + index * row_height
        accuracy = values["decision_accuracy"]
        bar_width = 0 if accuracy is None else plot_width * accuracy
        rows.append(
            f'<text x="0" y="{y + 16}" class="svg-label">{_escape(CONDITION_LABELS[condition])}</text>'
            f'<rect x="{left}" y="{y}" width="{plot_width}" height="22" rx="6" class="svg-track"/>'
            f'<rect x="{left}" y="{y}" width="{bar_width:.2f}" height="22" rx="6" fill="{CONDITION_COLORS[condition]}"/>'
            f'<text x="{width}" y="{y + 16}" text-anchor="end" class="svg-value">{_rate(accuracy)}</text>'
        )
    threshold_x = left + plot_width * 0.98
    return (
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="accuracy-title accuracy-desc">'
        '<title id="accuracy-title">Decision accuracy by experimental condition</title>'
        '<desc id="accuracy-desc">Horizontal bars compare decision accuracy. A vertical marker shows the 98 percent clean qualification threshold.</desc>'
        f'<line x1="{threshold_x:.2f}" y1="26" x2="{threshold_x:.2f}" y2="{height - 8}" class="threshold"/>'
        f'<text x="{threshold_x - 6:.2f}" y="16" text-anchor="end" class="svg-note">98% clean gate</text>'
        f"{''.join(rows)}</svg>"
    )


def _effect_chart(report: dict[str, Any]) -> str:
    effects = report["paired_effects"]
    width, row_height = 960, 68
    left, right = 280, 112
    values = []
    for effect in effects:
        values.extend(
            value
            for value in [effect["error_rate_difference"], *effect["bootstrap_95_ci"]]
            if value is not None
        )
    raw_extent = max([0.05, *(abs(value) for value in values)])
    extent = max(0.06, (int(raw_extent * 50 + 0.9999) / 50))
    plot_width = width - left - right
    mid = left + plot_width / 2

    def x(value: float) -> float:
        return mid + value / (2 * extent) * plot_width

    height = 54 + row_height * len(effects)
    rows = []
    ticks = []
    for tick_value in (-extent, -extent / 2, 0.0, extent / 2, extent):
        tick_x = x(tick_value)
        ticks.append(
            f'<line x1="{tick_x:.2f}" y1="24" x2="{tick_x:.2f}" y2="{height - 10}" class="grid-line"/>'
            f'<text x="{tick_x:.2f}" y="{height - 1}" text-anchor="middle" class="svg-note">{_pp(tick_value)}</text>'
        )
    for index, effect in enumerate(effects):
        y = 52 + index * row_height
        value = effect["error_rate_difference"]
        low, high = effect["bootstrap_95_ci"]
        role = effect["analysis_role"].replace("_", " ")
        rows.append(
            f'<text x="0" y="{y}" class="svg-label">{_escape(effect["label"])}</text>'
            f'<text x="0" y="{y + 18}" class="svg-note">{_escape(role)} · {effect["paired_workdays"]} paired days</text>'
        )
        if value is not None and low is not None and high is not None:
            dash = ' stroke-dasharray="5 5"' if role == "descriptive" else ""
            rows.append(
                f'<line x1="{x(low):.2f}" y1="{y - 5}" x2="{x(high):.2f}" y2="{y - 5}" class="effect-ci"{dash}/>'
                f'<circle cx="{x(value):.2f}" cy="{y - 5}" r="7" class="effect-dot {"descriptive" if role == "descriptive" else "matched"}"/>'
                f'<text x="{width}" y="{y}" text-anchor="end" class="svg-value">{_pp(value)}</text>'
            )
        else:
            rows.append(
                f'<text x="{width}" y="{y}" text-anchor="end" class="svg-value">Not measured</text>'
            )
    return (
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="effect-title effect-desc">'
        '<title id="effect-title">Paired change in error rate</title>'
        f'<desc id="effect-desc">Dots show treatment minus control error rate on a {-extent * 100:.2f} to +{extent * 100:.2f} percentage-point axis. Lines show 95 percent paired-workday bootstrap confidence intervals. Positive values mean more treatment errors.</desc>'
        f"{''.join(ticks)}"
        f'<line x1="{mid:.2f}" y1="24" x2="{mid:.2f}" y2="{height - 10}" class="zero-line"/>'
        f'<text x="{mid - 8:.2f}" y="16" text-anchor="end" class="svg-note">fewer errors</text>'
        f'<text x="{mid + 8:.2f}" y="16" class="svg-note">more errors</text>'
        f"{''.join(rows)}</svg>"
    )


def _effect_table(report: dict[str, Any]) -> str:
    rows = []
    for effect in report["paired_effects"]:
        low, high = effect["bootstrap_95_ci"]
        interval = (
            "Not measured"
            if low is None or high is None
            else f"{_pp(low)} to {_pp(high)}"
        )
        rows.append(
            "<tr>"
            f'<th scope="row">{_escape(effect["label"])}</th>'
            f"<td>{_escape(effect['analysis_role'].replace('_', ' '))}</td>"
            f"<td>{_pp(effect['error_rate_difference'])}</td>"
            f"<td>{_escape(interval)}</td>"
            f"<td>{effect['paired_workdays']}</td>"
            "</tr>"
        )
    return "".join(rows)


def _primary_effect_block(report: dict[str, Any]) -> str:
    dose = report.get("occupancy_dose_response")
    if dose and dose["paired_workdays"]:
        low, high = dose["slope_bootstrap_95_ci"]
        return (
            '<aside class="primary-effect" aria-label="Primary benchmark comparison">'
            "<span>Primary dose trend</span>"
            "<div><strong>Unresolved-minus-resolved slope</strong>"
            "<p>"
            f"{_pp(dose['slope_per_10_occupancy_points'])} per +10 occupancy points · "
            f"95% interval {_pp(low)} to {_pp(high)} · "
            f"{dose['paired_workdays']} paired days"
            "</p></div></aside>"
        )
    primary = next(
        (
            effect
            for effect in report.get("paired_effects", [])
            if effect.get("id") == "unresolved_tension"
        ),
        None,
    )
    if primary is None:
        return ""
    low, high = primary["bootstrap_95_ci"]
    return (
        '<aside class="primary-effect" aria-label="Primary benchmark comparison">'
        "<span>Primary comparison</span>"
        "<div><strong>Unresolved minus resolved</strong>"
        "<p>"
        f"{_pp(primary['error_rate_difference'])} error rate · "
        f"95% interval {_pp(low)} to {_pp(high)} · "
        f"{primary['paired_workdays']} paired days"
        "</p></div></aside>"
    )


def _recovery_series(
    recovery: dict[str, Any],
    bands: list[str],
    x_positions: list[float],
    top: int,
    plot_height: int,
    y_max: float,
) -> tuple[list[str], list[str], bool]:
    series = {
        condition: tuple(values[band]["error_rate"] for band in bands)
        for condition, values in recovery.items()
    }
    composite = len(series) > 1 and len(set(series.values())) == 1
    visible_series = (
        [("clean", next(iter(recovery.values())))] if composite else recovery.items()
    )
    parts = []
    for condition, values in visible_series:
        segments: list[list[str]] = []
        current_segment: list[str] = []
        markers = []
        for index, band in enumerate(bands):
            rate = values[band]["error_rate"]
            if rate is None:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
                continue
            x_value = x_positions[index]
            y_value = top + plot_height * (1 - rate / y_max)
            current_segment.append(f"{x_value:.2f},{y_value:.2f}")
            markers.append(
                f'<circle cx="{x_value:.2f}" cy="{y_value:.2f}" r="6" fill="{CONDITION_COLORS[condition]}" stroke="#0a0c0f" stroke-width="3"/>'
            )
        if current_segment:
            segments.append(current_segment)
        dash = RECOVERY_DASHES.get(condition, "")
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.extend(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{CONDITION_COLORS[condition]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"{dash_attr}/>'
            for points in segments
            if len(points) > 1
        )
        parts.extend(markers)
    legend = [
        f'<span><i style="--condition:{CONDITION_COLORS[condition]}"></i>{_escape(CONDITION_LABELS[condition])}</span>'
        for condition in recovery
    ]
    return parts, legend, composite


def _recovery_chart(report: dict[str, Any]) -> str:
    recovery = report["recovery"]
    bands = ["pre_event", "after_1_3", "after_4_10", "after_11_25"]
    labels = ["Before event", "Tasks 1–3", "Tasks 4–10", "Tasks 11–25"]
    width, height = 900, 390
    left, right, top, bottom = 72, 72, 34, 72
    plot_width, plot_height = width - left - right, height - top - bottom
    x_positions = [left + index * plot_width / (len(bands) - 1) for index in range(4)]
    observed_rates = [
        values[band]["error_rate"]
        for values in recovery.values()
        for band in bands
        if values[band]["error_rate"] is not None
    ]
    observed_max = max(observed_rates, default=0.0)
    y_max = (
        0.10
        if observed_max <= 0.10
        else min(1.0, (int(observed_max * 10 + 0.9999) / 10))
    )
    parts = []
    for tick in range(5):
        rate = y_max * tick / 4
        y = top + plot_height * (1 - rate / y_max)
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" class="grid-line"/>'
            f'<text x="{left - 12}" y="{y + 5:.2f}" text-anchor="end" class="svg-note">{rate:.0%}</text>'
        )
    for index, label in enumerate(labels):
        parts.append(
            f'<text x="{x_positions[index]:.2f}" y="{height - 28}" text-anchor="middle" class="svg-note">{_escape(label)}</text>'
        )
    series_parts, legend, composite = _recovery_series(
        recovery, bands, x_positions, top, plot_height, y_max
    )
    parts.extend(series_parts)
    overlap_note = (
        '<p class="chart-note">All condition series overlap exactly in this fixture.</p>'
        if composite
        else ""
    )
    return (
        '<div class="chart-legend">'
        + "".join(legend)
        + "</div>"
        + overlap_note
        + f'<p class="chart-note">Vertical scale: 0–{y_max:.0%} error; all observations shown.</p>'
        + f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-labelledby="recovery-title recovery-desc">'
        + '<title id="recovery-title">Error rate by distance from the latest interruption</title>'
        + f'<desc id="recovery-desc">Lines compare error rates from zero to {y_max:.0%} before an event and across three recovery windows. Missing measurements are left blank.</desc>'
        + "".join(parts)
        + "</svg>"
    )


def _recovery_table(report: dict[str, Any]) -> str:
    bands = ("pre_event", "after_1_3", "after_4_10", "after_11_25")
    rows = []
    for condition, values in report["recovery"].items():
        cells = "".join(f"<td>{_rate(values[key]['error_rate'])}</td>" for key in bands)
        rows.append(
            f'<tr><th scope="row">{_escape(CONDITION_LABELS[condition])}</th>{cells}</tr>'
        )
    return "".join(rows)


def _behavior_rows(report: dict[str, Any]) -> str:
    rows = []
    for condition, metrics in report["behavior"].items():
        action = " · ".join(
            f"{name.replace('_', ' ')} {count}"
            for name, count in metrics["actions"].items()
        )
        rows.append(
            "<tr>"
            f'<th scope="row">{_escape(CONDITION_LABELS[condition])}</th>'
            f"<td>{metrics['events']}</td>"
            f"<td>{_rate(metrics['valid_action_rate'])}</td>"
            f"<td>{_escape(action or 'No recorded actions')}</td>"
            f"<td>{_number(metrics['reply_length_mean_characters'], ' chars')}</td>"
            "</tr>"
        )
    if rows:
        return "".join(rows)
    return '<tr><td colspan="5" class="empty-cell">No response-required events were completed.</td></tr>'


def _fragile_claims(report: dict[str, Any]) -> str:
    ranked = sorted(
        report["task_fragility"],
        key=lambda item: item["error_rate_range"] or 0,
        reverse=True,
    )[:8]
    if not ranked or not any((item["error_rate_range"] or 0) > 0 for item in ranked):
        noun = (
            "fixture data"
            if report["artifact_kind"] == "synthetic_fixture"
            else "this run"
        )
        return f'<p class="empty-state">No condition-sensitive claims appeared in {noun}.</p>'
    return (
        "<ol class=fragility>"
        + "".join(
            f"<li><code>{_escape(item['task_id'])}</code><span>{_pp(item['error_rate_range'])} range</span></li>"
            for item in ranked
            if (item["error_rate_range"] or 0) > 0
        )
        + "</ol>"
    )


def _provenance_rows(report: dict[str, Any]) -> str:
    provenance = report["provenance"]
    server = provenance["inference_server"]
    values = [
        ("Model", provenance["model"], False),
        (
            "Endpoint identity",
            ", ".join(provenance["endpoint_models"]) or "Required evidence missing",
            not provenance["endpoint_models"],
        ),
        (
            "Quantization",
            provenance["quantization"] or "Required evidence missing",
            not provenance["quantization"],
        ),
        (
            "Inference server",
            f"{server['name']} {server['version'] or 'version missing'}",
            not server["version"],
        ),
        (
            "Model file",
            _short_hash(provenance["model_file_sha256"])
            if provenance["model_file_sha256"]
            else "Required evidence missing",
            not provenance["model_file_sha256"],
        ),
        ("Config", _short_hash(report["config_sha256"]), False),
        ("Claims", _short_hash(provenance["claims_sha256"]), False),
        ("Scenarios", _short_hash(provenance["scenarios_sha256"]), False),
        (
            "Sampling",
            f"temperature {provenance['temperature']} · model seed {provenance['model_seed']} · schedule seed {provenance['schedule_seed']}",
            False,
        ),
        (
            "Context",
            f"{provenance['context_limit']:,} tokens · {provenance['context_safety_margin_tokens']:,} safety margin",
            False,
        ),
    ]
    return "".join(
        f'<dt>{_escape(label)}</dt><dd class="{"missing" if missing else ""}">{_escape(value)}</dd>'
        for label, value, missing in values
    )


def _head_html(report: dict[str, Any]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <title>OffHours — {_escape(report["run_id"])}</title>
  <style>
    :root {{ --canvas:#0a0c0f; --surface:#111419; --raised:#171b22; --ink:#eaedf2; --secondary:#a6adb9; --muted:#737b88; --rule:#252b34; --teal:#48e5c2; --coral:#ff6f5c; --display:"Bricolage Grotesque",Inter,system-ui,sans-serif; --body:Geist,Inter,system-ui,sans-serif; --mono:"Geist Mono",ui-monospace,SFMono-Regular,monospace; }}
    * {{ box-sizing:border-box; }}
    html {{ max-width:100%; background:var(--canvas); color:var(--ink); scroll-behavior:smooth; }}
    body {{ max-width:100%; margin:0; overflow-x:clip; font:400 16px/1.62 var(--body); background:var(--canvas); }}
    a {{ color:var(--teal); }}
    .shell {{ width:min(1180px,calc(100% - 40px)); margin:0 auto; }}
    .topline {{ display:flex; justify-content:space-between; align-items:center; gap:24px; min-height:64px; border-bottom:1px solid var(--rule); color:var(--secondary); font-size:.86rem; }} .topline > * {{ min-width:0; }}
    .brand {{ color:var(--ink); font:650 1rem/1 var(--display); letter-spacing:-.02em; }}
    .run-id {{ font-family:var(--mono); color:var(--muted); overflow-wrap:anywhere; }}
    .hero {{ min-height:670px; display:grid; grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr); gap:72px; align-items:center; padding:88px 0 72px; border-bottom:1px solid var(--rule); }}
    .status {{ display:inline-flex; align-items:center; gap:10px; margin-bottom:30px; font:650 .75rem/1 var(--mono); letter-spacing:.08em; text-transform:uppercase; }}
    .status::before {{ content:""; width:9px; height:9px; border-radius:50%; background:var(--secondary); box-shadow:0 0 0 5px var(--raised); }}
    .status.verified::before {{ background:var(--teal); box-shadow:0 0 0 5px rgba(72,229,194,.12); }}
    .status.validation::before {{ background:var(--coral); box-shadow:0 0 0 5px rgba(255,111,92,.12); }}
    .status.blocked::before {{ background:var(--coral); box-shadow:0 0 0 5px rgba(255,111,92,.12); }}
    h1,h2,h3 {{ font-family:var(--display); letter-spacing:-.03em; text-wrap:balance; }}
    h1 {{ margin:0; max-width:790px; overflow-wrap:normal; font-size:clamp(3.6rem,8vw,6rem); line-height:.93; font-weight:620; }}
    .lede {{ max-width:66ch; margin:32px 0 0; color:var(--secondary); font-size:clamp(1.05rem,2vw,1.3rem); line-height:1.55; }}
    .status-note {{ max-width:60ch; margin:18px 0 0; color:var(--muted); }}
    .experiment {{ position:relative; padding:28px 0 20px; margin:0; list-style:none; }}
    .experiment::before {{ content:""; position:absolute; left:10px; top:22px; bottom:28px; width:1px; background:var(--rule); }}
    .experiment-step {{ position:relative; display:grid; grid-template-columns:22px 1fr; gap:18px; padding:0 0 28px; }}
    .experiment-step:last-child {{ padding-bottom:0; }}
    .experiment-step i {{ position:relative; width:9px; height:9px; margin:8px 0 0 6px; border-radius:50%; background:var(--teal); box-shadow:0 0 0 6px var(--canvas); }}
    .experiment-step strong {{ display:block; font-size:.96rem; }}
    .experiment-step span {{ display:block; color:var(--muted); font-size:.88rem; }}
    .section {{ padding:76px 0; border-bottom:1px solid var(--rule); }}
    .section-head {{ display:grid; grid-template-columns:minmax(220px,.42fr) minmax(0,1fr); gap:56px; margin-bottom:42px; }}
    .section-head h2 {{ margin:0; font-size:clamp(2rem,4vw,3rem); line-height:1.02; }}
    .section-head p {{ margin:4px 0 0; max-width:68ch; color:var(--secondary); }}
    .result-band {{ display:grid; grid-template-columns:minmax(220px,.42fr) minmax(0,1fr); gap:56px; padding:30px 0; border-bottom:1px solid var(--rule); }}
    .result-band h2 {{ margin:0; font-size:clamp(1.55rem,3vw,2.25rem); line-height:1.05; }} .result-band p {{ margin:4px 0 0; max-width:68ch; color:var(--secondary); }}
    .mobile-result {{ display:none; margin:30px 0 0; padding:20px 0 0; border-top:1px solid var(--rule); }} .mobile-result strong {{ display:block; font-family:var(--display); font-size:1.25rem; line-height:1.15; }} .mobile-result span {{ display:block; margin-top:8px; color:var(--secondary); font-size:.9rem; }}
    .evidence-ladder {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); margin:28px 0 0; padding:0; list-style:none; color:var(--muted); font:550 .72rem/1.35 var(--mono); }}
    .evidence-ladder li {{ min-width:0; position:relative; padding:18px 8px 0 0; border-top:1px solid var(--rule); overflow-wrap:anywhere; }} .evidence-ladder i {{ position:absolute; top:-5px; left:0; width:9px; height:9px; border-radius:50%; background:var(--rule); box-shadow:0 0 0 5px var(--canvas); }}
    .evidence-ladder .active {{ color:var(--ink); border-color:var(--teal); }} .evidence-ladder .active i {{ background:var(--teal); }}
    .gates {{ list-style:none; padding:0; margin:0; border-top:1px solid var(--rule); }}
    .gates li {{ display:grid; grid-template-columns:74px 1fr; gap:20px; padding:20px 0; border-bottom:1px solid var(--rule); }}
    .gate-mark {{ align-self:start; padding:6px 8px; border-radius:9px; font:650 .7rem/1 var(--mono); text-align:center; background:rgba(255,111,92,.1); color:var(--coral); }}
    .gate-mark.pass {{ color:var(--teal); background:rgba(72,229,194,.1); }}
    .gate-mark.demo {{ color:var(--secondary); background:var(--raised); }}
    .gates strong,.gates span {{ display:block; }} .gates span {{ color:var(--muted); font-size:.9rem; }}
    .condition-arc {{ display:flex; flex-wrap:wrap; gap:10px 22px; margin:0 0 30px; color:var(--secondary); }}
    .condition-arc span {{ display:inline-flex; align-items:center; gap:8px; font-size:.86rem; }}
    .condition-arc i,.condition-dot,.chart-legend i {{ width:9px; height:9px; border-radius:50%; background:var(--condition); display:inline-block; flex:0 0 auto; }}
    .condition-dot {{ margin-right:10px; }}
    .chart-frame {{ overflow-x:auto; padding:28px 0 10px; border-top:1px solid var(--rule); border-bottom:1px solid var(--rule); }}
    .scroll-cue {{ display:none; margin:0 0 8px; color:var(--muted); font:550 .7rem/1.4 var(--mono); }}
    .chart {{ display:block; width:100%; min-width:720px; height:auto; font-family:var(--body); }}
    .svg-label {{ fill:var(--ink); font-size:14px; font-weight:620; }} .svg-note {{ fill:var(--muted); font-size:12px; }} .svg-value {{ fill:var(--secondary); font:600 13px var(--mono); }}
    .svg-track {{ fill:var(--raised); }} .threshold {{ stroke:var(--teal); stroke-width:1; stroke-dasharray:4 5; }} .zero-line {{ stroke:var(--secondary); stroke-width:1; }} .grid-line {{ stroke:var(--rule); stroke-width:1; }}
    .effect-ci {{ stroke:var(--secondary); stroke-width:3; stroke-linecap:round; }} .effect-dot {{ stroke:var(--canvas); stroke-width:3; }} .effect-dot.matched {{ fill:var(--teal); }} .effect-dot.descriptive {{ fill:var(--secondary); }}
    .chart-legend {{ display:flex; flex-wrap:wrap; gap:12px 22px; margin:0 0 6px; color:var(--secondary); font-size:.82rem; }} .chart-legend span {{ display:inline-flex; align-items:center; gap:8px; }}
    .chart-note {{ margin:8px 0 0; color:var(--muted); font:550 .76rem/1.4 var(--mono); }}
    .primary-effect {{ display:grid; grid-template-columns:180px 1fr; gap:28px; margin:0 0 28px; padding:22px 0; border-top:1px solid var(--coral); border-bottom:1px solid var(--rule); }} .primary-effect > span {{ color:var(--coral); font:650 .72rem/1.4 var(--mono); letter-spacing:.06em; text-transform:uppercase; }} .primary-effect strong {{ display:block; font-family:var(--display); font-size:1.2rem; }} .primary-effect p {{ margin:4px 0 0; color:var(--secondary); }}
    .fixture-label {{ margin:-18px 0 26px; color:var(--secondary); font:650 .7rem/1.4 var(--mono); letter-spacing:.06em; text-transform:uppercase; }}
    .table-wrap {{ overflow-x:auto; border-top:1px solid var(--rule); }}
    table {{ width:100%; min-width:760px; border-collapse:collapse; font-size:.88rem; }} caption {{ padding:16px 0; color:var(--muted); text-align:left; }}
    th,td {{ padding:16px 14px; border-bottom:1px solid var(--rule); text-align:right; vertical-align:top; }} th:first-child,td:first-child {{ padding-left:0; text-align:left; }} thead th {{ color:var(--muted); font:550 .74rem/1.3 var(--mono); }} tbody th {{ font-weight:620; white-space:nowrap; }}
    .two-up {{ display:grid; grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr); gap:64px; }}
    .two-up table {{ min-width:0; }}
    .minor-title {{ margin:0 0 22px; font-size:1.35rem; }}
    .empty-state,.empty-cell {{ color:var(--muted); }}
    .fragility {{ list-style:none; padding:0; margin:0; border-top:1px solid var(--rule); }} .fragility li {{ display:flex; justify-content:space-between; gap:18px; padding:13px 0; border-bottom:1px solid var(--rule); }} code {{ color:var(--secondary); font-family:var(--mono); font-size:.82rem; }} .fragility span {{ color:var(--muted); font:500 .8rem var(--mono); }}
    .provenance {{ display:grid; grid-template-columns:180px 1fr; gap:0; margin:0; border-top:1px solid var(--rule); }} .provenance dt,.provenance dd {{ margin:0; padding:13px 0; border-bottom:1px solid var(--rule); }} .provenance dt {{ color:var(--muted); }} .provenance dd {{ font-family:var(--mono); overflow-wrap:anywhere; }} .provenance dd.missing {{ color:var(--coral); font-weight:650; }}
    .limitations {{ margin:0; padding-left:1.25rem; color:var(--secondary); }} .limitations li {{ margin:0 0 12px; padding-left:8px; }}
    .method {{ max-width:72ch; color:var(--secondary); }} .method strong {{ color:var(--ink); }}
    .close {{ padding:76px 0 100px; display:grid; grid-template-columns:1fr auto; align-items:end; gap:42px; }} .close h2 {{ margin:0; max-width:760px; font-size:clamp(2.4rem,5vw,4.4rem); line-height:1; }} .close p {{ margin:22px 0 0; max-width:62ch; color:var(--secondary); }} .stamp {{ color:var(--muted); font:500 .76rem/1.5 var(--mono); text-align:right; }}
    @media (max-width:820px) {{ .hero,.section-head,.two-up,.close,.result-band {{ grid-template-columns:1fr; gap:34px; }} .hero > *,.section-head > *,.two-up > *,.close > *,.result-band > * {{ min-width:0; }} .hero {{ min-height:auto; padding:64px 0; }} .experiment {{ max-width:520px; }} .section {{ padding:58px 0; }} .scroll-cue {{ display:block; }} .table-wrap th:first-child,.table-wrap td:first-child {{ position:sticky; left:0; z-index:1; background:var(--canvas); box-shadow:1px 0 var(--rule); }} .stamp {{ text-align:left; }} }}
    @media (max-width:520px) {{ .shell {{ width:calc(100% - 28px); }} .topline {{ display:grid; grid-template-columns:1fr; align-items:start; gap:10px; padding:18px 0; }} .run-id {{ max-width:100%; text-align:left; font-size:.68rem; }} .hero {{ padding:52px 0; }} .status {{ margin-bottom:24px; }} h1 {{ max-width:100%; font-size:clamp(2.5rem,12vw,3rem); line-height:.96; text-wrap:balance; }} .lede,.status-note {{ overflow-wrap:anywhere; }} .mobile-result {{ display:block; }} .desktop-result {{ display:none; }} .evidence-ladder {{ grid-template-columns:repeat(2,minmax(0,1fr)); gap:24px 12px; }} .gates li {{ grid-template-columns:62px 1fr; gap:14px; }} .primary-effect {{ grid-template-columns:1fr; gap:8px; }} .provenance {{ grid-template-columns:1fr; }} .provenance dt {{ padding-bottom:0; border-bottom:0; }} .provenance dd {{ padding-top:4px; }} }}
    @media (prefers-reduced-motion:reduce) {{ html {{ scroll-behavior:auto; }} }}
    @media print {{ :root {{ --canvas:#fff; --surface:#fff; --raised:#f1f3f5; --ink:#111; --secondary:#333; --muted:#666; --rule:#ccc; }} body {{ font-size:11pt; }} .shell {{ width:100%; }} .topline {{ min-height:42px; }} .hero {{ min-height:auto; padding:38px 0; }} .section {{ padding:32px 0; break-inside:avoid; }} .scroll-cue {{ display:none; }} .chart-frame,.table-wrap {{ overflow:visible; }} .chart,table {{ min-width:0; }} svg rect[fill="#eaedf2"],svg circle[fill="#eaedf2"] {{ fill:#111; }} .close {{ padding:38px 0; }} }}
  </style>
</head>
"""


def _body_html(report: dict[str, Any]) -> str:
    status_class, status_title, status_note = _status_copy(report)
    result_title, result_note = _result_summary(report)
    close_title, close_note = _closing_copy(report)
    hero_title, hero_lede, condition_title, condition_note = _hero_copy(report)
    fixture_label = _fixture_label(report)
    fixture_block = f"      {fixture_label}\n" if fixture_label else ""
    limitations = "".join(f"<li>{_escape(item)}</li>" for item in report["limitations"])
    conditions = "".join(
        f'<span style="--condition:{CONDITION_COLORS[name]}"><i></i>{_escape(CONDITION_LABELS[name])}</span>'
        for name in report["workload"]["conditions"]
    )
    return f"""<body>
  <header class="shell topline"><span class="brand">posttrainllm / OffHours</span><span class="run-id">{_escape(report["run_id"])}</span></header>
  <main>
    <section class="shell hero" aria-labelledby="report-title">
      <div>
        <div class="status {status_class}">{_escape(status_title)}</div>
        <h1 id="report-title">{_escape(hero_title)}</h1>
        <p class="lede">{_escape(hero_lede)}</p>
        <p class="status-note">{_escape(status_note)}</p>
        <aside class="mobile-result"><strong>{_escape(result_title)}</strong><span>{_escape(result_note)}</span></aside>
      </div>
      <ol class="experiment" aria-label="Benchmark sequence">
        <li class="experiment-step"><i aria-hidden="true"></i><div><strong>One employee</strong><span>Byte-identical Arjun persona and policy</span></div></li>
        <li class="experiment-step"><i aria-hidden="true"></i><div><strong>Paired workdays</strong><span>{report["workload"]["tasks_per_day"]} claims · four interruption positions</span></div></li>
        <li class="experiment-step"><i aria-hidden="true"></i><div><strong>{_escape(condition_title)}</strong><span>{_escape(condition_note)}</span></div></li>
        <li class="experiment-step"><i aria-hidden="true"></i><div><strong>Workday-level inference</strong><span>Paired bootstrap intervals, not claim-level certainty</span></div></li>
      </ol>
    </section>

    <aside class="shell result-band desktop-result" aria-labelledby="result-title">
      <div><h2 id="result-title">{_escape(result_title)}</h2></div>
      <div><p>{_escape(result_note)}</p><ol class="evidence-ladder" aria-label="Evidence maturity">{_evidence_ladder(report)}</ol></div>
    </aside>

    <section class="shell section" aria-labelledby="qualification-title">
      <div class="section-head"><h2 id="qualification-title">Can this run be believed?</h2><p>The report fails closed. A completed page is not automatically a qualified result, and a qualified local run is not automatically a publishable model comparison.</p></div>
      <ul class="gates">{_qualification_rows(report)}</ul>
    </section>

    <section class="shell section" aria-labelledby="quality-title">
      <div class="section-head"><h2 id="quality-title">Routine work quality</h2><p>Accuracy is scored against a deterministic policy oracle. Malformed JSON receives no retry; skipped work remains in the denominator.</p></div>
{fixture_block}      <div class="condition-arc">{conditions}</div>
      <p class="scroll-cue">Swipe horizontally to inspect the full chart →</p>
      <div class="chart-frame">{_accuracy_chart(report)}</div>
      <p class="scroll-cue">Swipe horizontally to inspect all columns →</p>
      <div class="table-wrap"><table><caption>Absolute work metrics by condition.</caption><thead><tr><th scope="col">Condition</th><th scope="col">Decision accuracy</th><th scope="col">Valid JSON</th><th scope="col">Skipped</th><th scope="col">Days</th><th scope="col">Mean latency</th></tr></thead><tbody>{_condition_table(report)}</tbody></table></div>
    </section>

    <section class="shell section" aria-labelledby="effects-title">
      <div class="section-head"><h2 id="effects-title">What changed after context?</h2><p>Treatment minus control error rate, paired by simulated workday. Positive values indicate worse work in the treatment condition. Dashed intervals are explicitly descriptive.</p></div>
{fixture_block}{_primary_effect_block(report)}
      <p class="scroll-cue">Swipe horizontally to inspect the full interval plot →</p>
      <div class="chart-frame">{_effect_chart(report)}</div>
      <p class="scroll-cue">Swipe horizontally to inspect all columns →</p>
      <div class="table-wrap"><table><caption>Accessible values for paired error-rate effects.</caption><thead><tr><th scope="col">Comparison</th><th scope="col">Role</th><th scope="col">Effect</th><th scope="col">95% interval</th><th scope="col">Paired days</th></tr></thead><tbody>{_effect_table(report)}</tbody></table></div>
    </section>

    <section class="shell section" aria-labelledby="recovery-section-title">
      <div class="section-head"><h2 id="recovery-section-title">Does the effect persist?</h2><p>Error probability is sliced by distance from the latest interruption. The expected signature is strongest immediately after an event, then recovery across later claims.</p></div>
{fixture_block}      <p class="scroll-cue">Swipe horizontally to inspect the full recovery plot →</p>
      <div class="chart-frame">{_recovery_chart(report)}</div>
      <p class="scroll-cue">Swipe horizontally to inspect all columns →</p>
      <div class="table-wrap"><table><caption>Accessible error rates for each recovery window.</caption><thead><tr><th scope="col">Condition</th><th scope="col">Before event</th><th scope="col">Tasks 1–3</th><th scope="col">Tasks 4–10</th><th scope="col">Tasks 11–25</th></tr></thead><tbody>{_recovery_table(report)}</tbody></table></div>
    </section>

    <section class="shell section" aria-labelledby="behavior-title">
      <div class="section-head"><h2 id="behavior-title">Behavior around the work</h2><p>Family messages can change more than claim accuracy. The benchmark retains visible action choices and reply length while excluding hidden chain-of-thought.</p></div>
{fixture_block}      <div class="two-up">
        <div><h3 class="minor-title">Event actions</h3><p class="scroll-cue">Swipe horizontally to inspect all columns →</p><div class="table-wrap"><table><caption>Structured responses to response-required events.</caption><thead><tr><th scope="col">Condition</th><th scope="col">Events</th><th scope="col">Valid</th><th scope="col">Actions</th><th scope="col">Reply length</th></tr></thead><tbody>{_behavior_rows(report)}</tbody></table></div></div>
        <div><h3 class="minor-title">Fragile claims</h3>{_fragile_claims(report)}</div>
      </div>
    </section>

    <section class="shell section" aria-labelledby="method-title">
      <div class="section-head"><h2 id="method-title">Method and evidence</h2><p>Every number should be traceable to the frozen task bank, scenario revision, model identity, and local inference server that produced it.</p></div>
      <div class="two-up">
        <div><h3 class="minor-title">Provenance</h3><dl class="provenance">{_provenance_rows(report)}</dl></div>
        <div><h3 class="minor-title">Interpretation limits</h3><ul class="limitations">{limitations}</ul></div>
      </div>
      <p class="method"><strong>Primary uncertainty unit:</strong> {_escape(report["primary_uncertainty_unit"])}. Confidence intervals resample paired workdays. The context-adjusted coefficient is a task-turn descriptive diagnostic and is never promoted above the paired estimate.</p>
    </section>

    <footer class="shell close">
      <div><h2>{_escape(close_title)}</h2><p>{_escape(close_note)}</p></div>
      <div class="stamp">schema {_escape(report["schema_version"])}<br>config {_escape(_short_hash(report["config_sha256"]))}<br>hidden reasoning stored: no</div>
    </footer>
  </main>
</body>
</html>
"""


def render_html(report: dict[str, Any]) -> str:
    return _head_html(report) + _body_html(report)


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.main_count = 0
        self.external_assets: list[str] = []
        self.svgs = 0
        self.svg_titles = 0
        self._inside_svg = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1":
            self.h1_count += 1
        elif tag == "main":
            self.main_count += 1
        elif tag == "svg":
            self.svgs += 1
            self._inside_svg = True
        elif tag == "title" and self._inside_svg:
            self.svg_titles += 1
        if tag in {"script", "img", "link"}:
            source = attributes.get("src") or attributes.get("href")
            if source:
                self.external_assets.append(source)

    def handle_endtag(self, tag: str) -> None:
        if tag == "svg":
            self._inside_svg = False


def validate_html(document: str) -> None:
    if not document.lower().startswith("<!doctype html>"):
        raise ValueError("OffHours report must start with an HTML doctype")
    parser = _StructureParser()
    parser.feed(document)
    if parser.h1_count != 1:
        raise ValueError("OffHours report must contain exactly one h1")
    if parser.main_count != 1:
        raise ValueError("OffHours report must contain exactly one main landmark")
    if parser.external_assets:
        raise ValueError("OffHours report must not load external assets")
    if parser.svgs != parser.svg_titles:
        raise ValueError("every OffHours report chart needs an accessible title")
