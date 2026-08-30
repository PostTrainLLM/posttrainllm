#!/usr/bin/env python3
"""Compile a Fine-Tune Report Card from existing factory evidence.

Two ingestion adapters, both metadata-only:

    # canonical factory run folder (docs/factory/run-schema.md)
    python3 scripts/factory/build_fine_tune_report_card.py --run runs/<id> --out <dir>

    # legacy specialist package (docs/factory/packaging.md)
    python3 scripts/factory/build_fine_tune_report_card.py \
        --specialist specialists/qwen3-4b-rest-fused --out <dir>

The compiler performs **no** model load, training, generation, evaluation,
registry call, or network request. It reads recorded files, maps each reported
field to its source, derives only what arithmetic allows, and marks everything
else `missing`/`skipped` rather than inventing a value.

Output (written only after the payload passes validation):

    <out>/report-card.json   versioned machine-readable contract
    <out>/report-card.html   deterministic, self-contained public report

Exit codes: 0 ok, 1 validation/publication failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fine_tune_report_card as rc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# Keys in a specialist `eval_report.json` score row that are metadata rather
# than a baseline/candidate measurement.
SCORE_META_KEYS = {"suite", "n", "delta", "source", "frontier", "note"}

BASELINE_KEY_HINTS = ("stock", "baseline", "base", "before")

BREADTH_MARKERS = ("breadth", "out_of_domain", "out-of-domain", "regression")


# ---------------------------------------------------------------------------
# Small readers
# ---------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise rc.ReportCardError(f"{path}: not found") from exc
    except json.JSONDecodeError as exc:
        raise rc.ReportCardError(f"{path}: invalid JSON: {exc}") from exc


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def committed_hash(path_text: str) -> str | None:
    """SHA-256 of a repo-relative source path, when it resolves to a file.

    Only committed files are hashed: hashing an ephemeral local run fragment
    would make the payload drift on every re-render.
    """
    candidate = ROOT / path_text.split("#", 1)[0]
    if candidate.is_file():
        return rc.sha256_file(candidate)
    return None


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Adapter: canonical factory run folder
# ---------------------------------------------------------------------------

#: Fragments recorded as evidence when present. `eval-validity.json` and
#: `cost.json` are optional: absent means the corresponding report-card fields
#: stay `missing` — never zero-filled — so pre-existing run folders keep
#: compiling unchanged.
RUN_FRAGMENTS = (
    ("config.json", "run config"),
    ("dataset.json", "dataset manifest"),
    ("eval-baseline.json", "frozen baseline eval"),
    ("eval-candidate.json", "candidate eval"),
    ("decision.json", "decision record"),
    ("slice-metrics.json", "per-slice metrics"),
    ("eval-validity.json", "eval validity and leakage checks"),
    ("cost.json", "training and eval cost/time"),
    ("provenance.json", "reproducibility provenance"),
    ("report.md", "human report"),
    ("trace_review.md", "qualitative trace review"),
    ("artifact.json", "artifact metadata"),
    ("train.log", "training log"),
)


def named_slice(
    slices: dict[str, Any], eval_spec: dict[str, Any], key: str
) -> str | None:
    """Resolve `config.eval.<key>` to a slice name, or None.

    A gate's sample size and (for regression gates) its before/after pair live in
    `slice-metrics.json`, which is keyed by slice rather than by gate. The run
    config must say **explicitly** which slice carries a gate:

        "eval": { "primary_slice": "...", "regression_slice": "..." }

    Earlier revisions inferred this — by matching a slice whose scores equalled
    the gate's, and by name-token containment. Both were wrong in ways that
    produced confidently mislabeled evidence: score equality attached an
    unrelated 3-row router slice's `n` to a 400-row gate, and token containment
    picked a coincidental short slice name over the correctly-named specific one,
    turning a 19-point breadth regression into a reported +50-point pass. The
    spec requires that a missing measurement is never inferred, so the heuristics
    are gone: without an explicit pointer the field stays `missing`.
    """
    name = (eval_spec or {}).get(key)
    if not name:
        return None
    if not slices:
        # No slice-metrics.json at all: degrade to `missing` rather than abort,
        # so an incomplete run still compiles into an honest card.
        return None
    if not isinstance(slices.get(name), dict):
        # The fragment exists but the named slice does not — that is a config
        # error, not absent evidence, so fail loudly instead of silently
        # downgrading a gate the operator believes is populated.
        raise rc.ReportCardError(
            f"config.eval.{key} names slice `{name}`, which is not present in "
            f"slice-metrics.json (available: {sorted(slices)})"
        )
    return name


def compile_from_run(run_dir: Path) -> dict[str, Any]:
    if not run_dir.is_dir():
        raise rc.ReportCardError(f"{run_dir}: not a directory")

    config = read_json(run_dir / "config.json")
    dataset = read_json(run_dir / "dataset.json")
    baseline = read_json(run_dir / "eval-baseline.json")
    candidate = read_json(run_dir / "eval-candidate.json")
    decision = read_json(run_dir / "decision.json")
    slice_path = run_dir / "slice-metrics.json"
    slice_metrics = read_json(slice_path) if slice_path.is_file() else {}
    prov_path = run_dir / "provenance.json"
    provenance = read_json(prov_path) if prov_path.is_file() else {}
    artifact_path = run_dir / "artifact.json"
    artifact = read_json(artifact_path) if artifact_path.is_file() else None
    validity_path = run_dir / "eval-validity.json"
    validity_src = read_json(validity_path) if validity_path.is_file() else {}
    cost_path = run_dir / "cost.json"
    cost_src = read_json(cost_path) if cost_path.is_file() else {}

    run_id = config.get("run_id") or run_dir.name
    src = lambda name, pointer="": f"{name}#{pointer}" if pointer else name  # noqa: E731
    slices = slice_metrics.get("slices") or {}
    eval_spec = config.get("eval") or {}
    threshold = eval_spec.get("threshold") or {}

    # --- primary gate ------------------------------------------------------
    primary_name = eval_spec.get("primary") or candidate.get("suite") or "primary"
    base_score = baseline.get("score")
    cand_score = candidate.get("score")
    base_field = (
        rc.measured(base_score, [src("eval-baseline.json", "score")])
        if _numeric(base_score)
        else rc.missing(
            "The run folder records no baseline score.",
            [src("eval-baseline.json", "score")],
        )
    )
    cand_field = (
        rc.measured(cand_score, [src("eval-candidate.json", "score")])
        if _numeric(cand_score)
        else rc.missing(
            "The run folder records no candidate score.",
            [src("eval-candidate.json", "score")],
        )
    )

    primary_min = threshold.get("primary_min")
    threshold_field = (
        rc.measured(primary_min, [src("config.json", "eval.threshold.primary_min")])
        if _numeric(primary_min)
        else rc.missing(
            "No primary threshold was frozen in the run config.",
            [src("config.json", "eval.threshold")],
        )
    )
    passed = candidate.get("passed")
    if isinstance(passed, bool):
        passed_field = rc.measured(passed, [src("eval-candidate.json", "passed")])
    elif rc.has_value(cand_field) and rc.has_value(threshold_field):
        passed_field = rc.derived(
            float(cand_score) >= float(primary_min),
            derived_from=[
                src("eval-candidate.json", "score"),
                src("config.json", "eval.threshold.primary_min"),
            ],
        )
    else:
        passed_field = rc.missing(
            "Neither a recorded pass flag nor a frozen threshold is available.",
            [src("eval-candidate.json", "passed")],
        )

    primary_slice = named_slice(slices, eval_spec, "primary_slice")
    if primary_slice is not None and _numeric(slices[primary_slice].get("rows")):
        n_field = rc.measured(
            slices[primary_slice]["rows"],
            [src("slice-metrics.json", f"slices.{primary_slice}.rows")],
            note=(
                f"Sample size from slice `{primary_slice}`, named by "
                "config.eval.primary_slice."
            ),
        )
    else:
        n_field = rc.missing(
            "No sample size is available: the run schema carries no per-gate row "
            "count, and config.eval.primary_slice does not name a slice that has "
            "one.",
            [src("config.json", "eval.primary_slice"), src("slice-metrics.json")],
        )

    frozen_field = _frozen_field(validity_src, dataset, src)

    gates = [
        _gate(
            role="primary",
            name=primary_name,
            metric=candidate.get("suite") or primary_name,
            baseline=base_field,
            candidate=cand_field,
            threshold=threshold_field,
            passed=passed_field,
            sample_size=n_field,
            frontier=_frontier_field(validity_src, candidate.get("suite") or primary_name, src),
            suite=candidate.get("suite") or primary_name,
            command=candidate.get("command"),
            command_source=src("eval-candidate.json", "command"),
            date=candidate.get("date"),
            date_source=src("eval-candidate.json", "date"),
            frozen=frozen_field,
        )
    ]

    # --- regression gate ---------------------------------------------------
    regression_name = eval_spec.get("regression")
    if regression_name:
        gates.append(
            _regression_gate_from_slices(
                regression_name, slices, eval_spec, src, candidate, validity_src
            )
        )

    # --- slices ------------------------------------------------------------
    slice_entries = []
    for name in sorted(slices):
        payload = slices[name]
        if not isinstance(payload, dict):
            continue
        pointer = f"slices.{name}"
        slice_entries.append(
            {
                "name": name,
                "metric": payload.get("metric") or "unspecified",
                "baseline": _num_field(
                    payload.get("baseline"),
                    src("slice-metrics.json", f"{pointer}.baseline"),
                    "This slice records no baseline score.",
                ),
                "candidate": _num_field(
                    payload.get("candidate"),
                    src("slice-metrics.json", f"{pointer}.candidate"),
                    "This slice records no candidate score.",
                ),
                "delta": None,  # filled below
                "passed": _bool_field(
                    payload.get("pass"),
                    src("slice-metrics.json", f"{pointer}.pass"),
                    "This slice records no gate result.",
                ),
                "sample_size": _num_field(
                    payload.get("rows"),
                    src("slice-metrics.json", f"{pointer}.rows"),
                    "This slice records no row count.",
                ),
            }
        )
        entry = slice_entries[-1]
        entry["delta"] = rc.delta_field(
            entry["baseline"],
            entry["candidate"],
            src("slice-metrics.json", f"{pointer}.baseline"),
            src("slice-metrics.json", f"{pointer}.candidate"),
        )

    # --- performance -------------------------------------------------------
    performance = {}
    for key, unit in (
        ("latency_ms", "ms"),
        ("peak_rss_mb", "MB"),
        ("tokens_per_second", "tok/s"),
    ):
        value = candidate.get(key)
        performance[key] = (
            rc.measured(value, [src("eval-candidate.json", key)], unit=unit)
            if _numeric(value)
            else rc.missing(
                f"The candidate eval recorded no {key}. It is reported as not "
                "measured rather than as zero.",
                [src("eval-candidate.json", key)],
            )
        )
    for key, unit in (
        ("training_time_seconds", "s"),
        ("training_cost_usd", "USD"),
        ("eval_time_seconds", "s"),
    ):
        value = cost_src.get(key)
        pointer = src("cost.json", key)
        performance[key] = (
            rc.measured(value, [pointer], unit=unit, note=cost_src.get(f"{key}_note"))
            if _numeric(value)
            else rc.missing(
                "No cost.json fragment records this field, so no timing or cost "
                "measurement exists for this run.",
                [pointer],
            )
        )

    # --- eval validity -----------------------------------------------------
    limitations = []
    overall_note = (slice_metrics.get("overall") or {}).get("note")
    if overall_note:
        limitations.append(str(overall_note))
    for item in validity_src.get("known_limitations") or []:
        limitations.append(str(item))
    for gate in gates:
        if not rc.has_value(gate["frontier_ceiling"]):
            limitations.append(
                f"Gate `{gate['name']}` has no frontier-ceiling evidence, so its "
                "absolute score is not calibrated against frontier capability."
            )

    validity = {
        "frontier_ceiling": gates[0]["frontier_ceiling"],
        "frozen_eval": frozen_field,
        "leakage": _leakage_field(validity_src, src),
        "known_limitations": limitations,
    }

    # --- artifact / decision ----------------------------------------------
    artifact_block = {
        "artifact_id": (artifact or {}).get("artifact_id") or run_id,
        "kind": (artifact or {}).get("kind") or "no-artifact",
        "path": (artifact or {}).get("path"),
        "package_dir": (artifact or {}).get("package_dir"),
        "shipped": bool((artifact or {}).get("shipped")),
        "routing_constraint": (
            rc.measured(
                (artifact or {}).get("routing_constraint"),
                [src("artifact.json", "routing_constraint")],
            )
            if (artifact or {}).get("routing_constraint")
            else rc.missing(
                "The run folder records no routing constraint for this artifact.",
                [src("artifact.json", "routing_constraint")],
            )
        ),
    }

    next_action = decision.get("next_action")
    decision_block = {
        "decision": decision.get("decision"),
        "reason": decision.get("reason"),
        "failure_reason": decision.get("failure_reason"),
        "failure_reason_confidence": decision.get("failure_reason_confidence"),
        "lesson": decision.get("lesson"),
        "next_action": (
            rc.measured(next_action, [src("decision.json", "next_action")])
            if next_action
            else rc.not_applicable(
                "No next action is recorded for this decision.",
                [src("decision.json", "next_action")],
            )
        ),
        "blocked_by": list(decision.get("blocked_by") or []),
        "evidence_sources": list(decision.get("evidence_sources") or []),
    }

    # --- evidence ----------------------------------------------------------
    evidence = []
    for name, label in RUN_FRAGMENTS:
        if (run_dir / name).is_file():
            evidence.append(
                {
                    "label": label,
                    "path": f"runs/{run_id}/{name}",
                    "kind": "local-run-fragment",
                    "note": "Local run folder (gitignored); regenerate to inspect.",
                }
            )
    for cited in decision_block["evidence_sources"]:
        if cited.startswith(f"runs/{run_id}/"):
            continue
        entry = {"label": cited, "path": cited, "kind": "cited-evidence"}
        digest = committed_hash(cited)
        if digest:
            entry["sha256"] = digest
        evidence.append(entry)

    dataset_hashes = []
    for item in provenance.get("datasets") or []:
        path_text = item.get("path")
        digest = item.get("sha256")
        if not (path_text and digest):
            continue
        dataset_hashes.append(
            {
                "path": repo_relative(Path(path_text)),
                "rows": item.get("rows"),
                "sha256": digest,
            }
        )

    caveats = []
    for label, payload in (("Baseline", baseline), ("Candidate", candidate)):
        note = payload.get("notes")
        if note:
            caveats.append(f"{label} eval note: {note}")

    card = {
        "schema_version": rc.SCHEMA_VERSION,
        "report_card_id": run_id,
        "title": _run_title(config),
        "compiled_from": {
            "compiler": rc.COMPILER,
            "compiler_version": rc.COMPILER_VERSION,
            "source_kind": "factory-run",
            "source_id": run_id,
            "dataset_hashes": dataset_hashes,
        },
        "subject": {
            "target": rc.measured(config.get("target"), [src("config.json", "target")]),
            "owner_goal": rc.measured(
                config.get("owner_goal"), [src("config.json", "owner_goal")]
            ),
            "base_model": rc.measured(
                _model_label(config.get("base_model") or {}),
                [src("config.json", "base_model")],
            ),
            "candidate_model": rc.measured(
                candidate.get("model_id"), [src("eval-candidate.json", "model_id")]
            ),
            "method": rc.measured(
                (config.get("candidate") or {}).get("method"),
                [src("config.json", "candidate.method")],
            ),
            "artifact": artifact_block,
        },
        "decision": decision_block,
        "gates": gates,
        "slices": slice_entries,
        "performance": performance,
        "eval_validity": validity,
        "evidence": evidence,
        "caveats": caveats,
    }
    return rc.finalize(card)


def _frontier_field(validity_src: dict[str, Any], suite: str, src) -> dict[str, Any]:
    """Frontier-ceiling score for one suite, from the optional validity fragment.

    `docs/factory/eval-protocol.md` requires a frontier model to ~ace a
    benchmark before Mac-model accuracy on it means anything. Without that
    evidence the benchmark is an unvalidated ruler, so the field stays
    `missing` and the ship decision cannot read as verified.
    """
    frontier = validity_src.get("frontier") or {}
    # Per-suite only. A single global `score` used to fall through to every
    # gate, which attributed one probe of the primary benchmark to unrelated
    # suites — and cited a `by_suite` path that was not in the source file.
    # Frontier ceilings are a property of a benchmark, not of a run.
    by_suite = frontier.get("by_suite") or {}
    score = by_suite.get(suite)
    pointer = src("eval-validity.json", f"frontier.by_suite.{suite}")
    if not _numeric(score):
        return rc.missing(
            "No frontier-ceiling score is recorded for this benchmark. Per "
            "docs/factory/eval-protocol.md an unvalidated benchmark cannot "
            "certify a verified ship.",
            [pointer],
        )
    parts = [str(frontier[k]) for k in ("model", "date") if frontier.get(k)]
    return rc.measured(
        score,
        [pointer],
        note=("Frontier reference: " + ", ".join(parts) + ".") if parts else None,
    )


def _frozen_field(
    validity_src: dict[str, Any], dataset: dict[str, Any], src
) -> dict[str, Any]:
    """Frozen-eval identity, preferring the explicit fragment over the manifest."""
    frozen = validity_src.get("frozen_eval") or {}
    identity = frozen.get("id")
    if identity:
        detail = [str(identity)]
        if frozen.get("rows") is not None:
            detail.append(f"{frozen['rows']} rows")
        if frozen.get("sha256"):
            detail.append(f"sha256 {frozen['sha256']}")
        return rc.measured(
            ", ".join(detail),
            [src("eval-validity.json", "frozen_eval")],
            note=frozen.get("note"),
        )
    split = (dataset.get("processing") or {}).get("heldout_split")
    if split and "lock" in str(split).lower():
        return rc.measured(
            str(split),
            [src("dataset.json", "processing.heldout_split")],
            note=(
                "Identity comes from the dataset manifest's locked-split label; "
                "no eval-validity.json records a hashed frozen-eval identity."
            ),
        )
    return rc.missing(
        "Neither eval-validity.json nor the dataset manifest records a locked, "
        "identified held-out split.",
        [src("eval-validity.json", "frozen_eval")],
    )


def _leakage_field(validity_src: dict[str, Any], src) -> dict[str, Any]:
    """Train/eval overlap verdict from the optional validity fragment."""
    check = validity_src.get("overlap_check") or {}
    result = check.get("result")
    pointer = src("eval-validity.json", "overlap_check.result")
    if result in ("no-overlap", "overlap-detected"):
        return rc.measured(result, [pointer], note=check.get("note"))
    if result is not None:
        raise rc.ReportCardError(
            f"eval-validity.json: overlap_check.result must be `no-overlap` or "
            f"`overlap-detected`, got {result!r}"
        )
    return rc.missing(
        "No train/eval overlap check is recorded. Publication cannot certify "
        "the held-out set is uncontaminated.",
        [pointer],
    )


def _run_title(config: dict[str, Any]) -> str:
    target = config.get("target") or config.get("run_id") or "factory run"
    method = (config.get("candidate") or {}).get("method")
    return f"{target} — {method}" if method else str(target)


def _model_label(base: dict[str, Any]) -> str:
    label = str(base.get("id") or "unknown")
    extras = [str(base[k]) for k in ("precision", "revision") if base.get(k)]
    return f"{label} ({', '.join(extras)})" if extras else label


def _gate(
    *,
    role: str,
    name: str,
    metric: str,
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    threshold: dict[str, Any],
    passed: dict[str, Any],
    sample_size: dict[str, Any],
    frontier: dict[str, Any],
    suite: str,
    command: Any,
    command_source: str,
    date: Any,
    date_source: str,
    frozen: dict[str, Any],
    baseline_source: str = "baseline",
    candidate_source: str = "candidate",
) -> dict[str, Any]:
    return {
        "role": role,
        "name": name,
        "metric": metric,
        "baseline": baseline,
        "candidate": candidate,
        "delta": rc.delta_field(
            baseline,
            candidate,
            (baseline.get("sources") or [baseline_source])[0],
            (candidate.get("sources") or [candidate_source])[0],
        ),
        "threshold": threshold,
        "passed": passed,
        "sample_size": sample_size,
        "frontier_ceiling": frontier,
        "eval_identity": {
            "suite": suite,
            "command": (
                rc.measured(command, [command_source])
                if command
                else rc.missing(
                    "No eval command is recorded for this gate.", [command_source]
                )
            ),
            "date": (
                rc.measured(date, [date_source])
                if date
                else rc.missing("No eval date is recorded for this gate.", [date_source])
            ),
            "frozen": frozen,
        },
    }


def _regression_gate_from_slices(
    regression_name: str,
    slices: dict[str, Any],
    eval_spec: dict[str, Any],
    src,
    candidate: dict[str, Any],
    validity_src: dict[str, Any],
) -> dict[str, Any]:
    """Build the regression gate from the slice `config.eval.regression_slice` names."""
    match = named_slice(slices, eval_spec, "regression_slice")
    drop_max = (eval_spec.get("threshold") or {}).get("breadth_drop_max_pp")
    threshold_field = (
        rc.measured(
            drop_max,
            [src("config.json", "eval.threshold.breadth_drop_max_pp")],
            unit="pp max drop",
        )
        if _numeric(drop_max)
        else rc.missing(
            "No regression threshold was frozen in the run config.",
            [src("config.json", "eval.threshold")],
        )
    )
    if match is None:
        # Each field gets its own object: sharing one dict (or a shallow copy of
        # it) would alias the nested `sources` list across five fields.
        def absent() -> dict[str, Any]:
            return rc.missing(
                f"No before/after evidence is recorded for regression suite "
                f"`{regression_name}`: the run folder carries one baseline/candidate "
                "pair (the primary gate), and config.eval.regression_slice does not "
                "name the slice that holds this gate's scores.",
                [src("config.json", "eval.regression_slice"), src("slice-metrics.json")],
            )

        return _gate(
            role="regression",
            name=regression_name,
            metric="unspecified",
            baseline=absent(),
            candidate=absent(),
            threshold=threshold_field,
            passed=absent(),
            sample_size=absent(),
            frontier=_frontier_field(validity_src, regression_name, src),
            suite=regression_name,
            command=None,
            command_source=src("eval-candidate.json", "command"),
            date=candidate.get("date"),
            date_source=src("eval-candidate.json", "date"),
            frozen=absent(),
        )

    payload = slices[match]
    pointer = f"slices.{match}"
    note = f"From slice `{match}`, named by config.eval.regression_slice."
    baseline = _num_field(
        payload.get("baseline"),
        src("slice-metrics.json", f"{pointer}.baseline"),
        "This slice records no baseline score.",
        note=note,
    )
    cand = _num_field(
        payload.get("candidate"),
        src("slice-metrics.json", f"{pointer}.candidate"),
        "This slice records no candidate score.",
        note=note,
    )
    return _gate(
        role="regression",
        name=regression_name,
        metric=payload.get("metric") or "unspecified",
        baseline=baseline,
        candidate=cand,
        threshold=threshold_field,
        passed=_bool_field(
            payload.get("pass"),
            src("slice-metrics.json", f"{pointer}.pass"),
            "This slice records no gate result.",
        ),
        sample_size=_num_field(
            payload.get("rows"),
            src("slice-metrics.json", f"{pointer}.rows"),
            "This slice records no row count.",
        ),
        frontier=_frontier_field(validity_src, regression_name, src),
        suite=regression_name,
        command=None,
        command_source=src("eval-candidate.json", "command"),
        date=candidate.get("date"),
        date_source=src("eval-candidate.json", "date"),
        frozen=rc.missing(
            "The run folder does not record whether the regression suite is frozen.",
            [src("dataset.json")],
        ),
    )


def _num_field(
    value: Any, source: str, absent_note: str, note: str | None = None
) -> dict[str, Any]:
    if _numeric(value):
        return rc.measured(value, [source], note=note)
    return rc.missing(absent_note, [source])


def _bool_field(value: Any, source: str, absent_note: str) -> dict[str, Any]:
    if isinstance(value, bool):
        return rc.measured(value, [source])
    return rc.missing(absent_note, [source])


# ---------------------------------------------------------------------------
# Adapter: legacy specialist package
# ---------------------------------------------------------------------------

PACKAGE_FILES = (
    ("model_card.md", "model card"),
    ("eval_report.json", "eval report"),
    ("tinygpt.lock.json", "reproducibility lock"),
    ("prompt.md", "prompt contract"),
)


def compile_from_specialist(pkg_dir: Path) -> dict[str, Any]:
    if not pkg_dir.is_dir():
        raise rc.ReportCardError(f"{pkg_dir}: not a directory")
    report_path = pkg_dir / "eval_report.json"
    report = read_json(report_path)
    pkg_rel = repo_relative(pkg_dir)
    report_src = f"{pkg_rel}/eval_report.json"

    registry_path = ROOT / "specialists/registry.json"
    registry_entry: dict[str, Any] = {}
    registry_src = "specialists/registry.json"
    pkg_id = report.get("id") or pkg_dir.name
    if registry_path.is_file():
        for entry in read_json(registry_path).get("packages") or []:
            if entry.get("id") == pkg_id:
                registry_entry = entry
                break

    quality = report.get("evidence_quality")
    hist_note = (
        f"Recorded evidence quality: {quality}. "
        if quality
        else ""
    ) + (
        "Imported from a committed specialist package rather than a canonical "
        "factory-run folder, so it lacks current run provenance (command, "
        "hashes, raw predictions)."
    )

    scores = report.get("scores") or []
    if not scores:
        raise rc.ReportCardError(f"{report_src}: no scores recorded")

    gates = [
        _specialist_gate(score, idx, report, report_src, hist_note)
        for idx, score in enumerate(scores)
    ]

    # --- routing constraint -------------------------------------------------
    verdict = report.get("verdict") or report.get("decision")
    do_not_use = registry_entry.get("do_not_use_for") or []
    routing_sources = [f"{report_src}#verdict"]
    if do_not_use:
        routing_sources.append(f"{registry_src}#do_not_use_for")
    if verdict and _is_routed(verdict, do_not_use):
        routing_text = str(verdict).rstrip(" .;")
        if do_not_use:
            routing_text += ". Do not use for: " + "; ".join(str(x) for x in do_not_use)
        routing_text += "."
        routing_constraint = rc.measured(routing_text, routing_sources)
    else:
        routing_constraint = rc.missing(
            "The package records no routing or task-envelope constraint.",
            routing_sources,
        )

    # --- performance --------------------------------------------------------
    perf = report.get("performance") or {}
    perf_note = perf.get("missing_evidence")
    performance = {}
    for key, unit in (
        ("latency_ms", "ms"),
        ("peak_rss_mb", "MB"),
        ("tokens_per_second", "tok/s"),
        ("training_time_seconds", "s"),
        ("training_cost_usd", "USD"),
        ("eval_time_seconds", "s"),
    ):
        value = perf.get(key)
        pointer = f"{report_src}#performance.{key}"
        if _numeric(value):
            note = perf.get(f"{key.replace('_seconds', '').replace('_usd', '')}_note")
            performance[key] = rc.historical(
                value,
                [pointer],
                note=(f"{note} " if note else "") + hist_note,
                unit=unit,
            )
        else:
            performance[key] = rc.missing(
                perf_note
                or (
                    "The specialist package records no value for this metric. It "
                    "is reported as not measured rather than as zero."
                ),
                [pointer],
            )

    # --- eval validity ------------------------------------------------------
    limitations = []
    for gate in gates:
        if not rc.has_value(gate["frontier_ceiling"]):
            limitations.append(
                f"Gate `{gate['name']}` has no frontier-ceiling evidence, so its "
                "absolute score is not calibrated against frontier capability."
            )
    limitations.append(
        "Values come from a committed specialist package, not a canonical "
        "factory-run folder: eval commands, dataset hashes, and raw predictions "
        "are unavailable for independent replay."
    )

    validity = {
        "frontier_ceiling": gates[0]["frontier_ceiling"],
        "frozen_eval": rc.missing(
            "The package records no frozen held-out split identity.",
            [report_src],
        ),
        "leakage": rc.missing(
            "No train/eval overlap check is recorded for this package.",
            [report_src],
        ),
        "known_limitations": limitations,
    }

    # --- decision -----------------------------------------------------------
    shipped = bool(registry_entry) and registry_entry.get("storage", {}).get(
        "status"
    ) in ("weights-published", "metadata-published")
    decision_value = "ship" if shipped else "park"
    reason = str(verdict) if verdict else "No verdict is recorded in the package."

    decision_block = {
        "decision": decision_value,
        "reason": reason,
        "failure_reason": None,
        "failure_reason_confidence": "not-applicable",
        "lesson": None,
        "next_action": rc.missing(
            "The specialist package format records no machine-readable next "
            "action. The release action lives in the public artifact registry "
            "(docs/factory/public-artifacts.md) as prose.",
            [registry_src if registry_entry else report_src],
        ),
        "blocked_by": [],
        "evidence_sources": [report_src],
    }
    if decision_value != "ship":
        decision_block["failure_reason"] = (
            "The package is not registered with published storage, so it is not "
            "a shipped specialist."
        )
        decision_block["failure_reason_confidence"] = "inferred"
        decision_block["lesson"] = (
            "A specialist package is only a ship once the registry records "
            "published storage for it."
        )
        # The next action follows from the check that produced this decision:
        # the package has evidence but no published registry entry. That is a
        # consequence of recorded facts, not an invented recommendation.
        decision_block["next_action"] = rc.derived(
            "Register this package in specialists/registry.json with published "
            "storage, or compile its report card from a canonical factory run.",
            derived_from=[registry_src],
            note=(
                "Derived from the absence of a published registry entry for "
                f"`{pkg_id}`; the package format records no next action itself."
            ),
        )

    # --- artifact -----------------------------------------------------------
    artifact_block = {
        "artifact_id": pkg_id,
        "kind": registry_entry.get("kind") or "specialist-package",
        "path": report.get("artifact") or registry_entry.get("artifact_path"),
        "package_dir": registry_entry.get("package_path") or pkg_rel,
        "shipped": shipped,
        "routing_constraint": routing_constraint,
    }

    # --- evidence -----------------------------------------------------------
    evidence: list[dict[str, Any]] = []
    for name, label in PACKAGE_FILES:
        path = pkg_dir / name
        if not path.is_file():
            continue
        entry = {
            "label": label,
            "path": f"{pkg_rel}/{name}",
            "kind": "committed-package-file",
            "sha256": rc.sha256_file(path),
        }
        evidence.append(entry)
    if registry_entry:
        evidence.append(
            {
                "label": "specialist registry entry",
                "path": registry_src,
                "kind": "committed-registry",
                "sha256": rc.sha256_file(registry_path),
            }
        )
    for source in sorted({str(s.get("source")) for s in scores if s.get("source")}):
        entry = {
            "label": "recorded result source",
            "path": source,
            "kind": "historical-record",
            "note": "The document the legacy score was recorded in.",
        }
        digest = committed_hash(source)
        if digest:
            entry["sha256"] = digest
        evidence.append(entry)
    artifact_ref = artifact_block["path"]
    if artifact_ref:
        evidence.append(
            {
                "label": "published weights",
                "path": str(artifact_ref),
                "kind": "external-artifact",
                "note": "Public weight location; not hashed by this compiler.",
            }
        )

    caveats = [str(c) for c in report.get("caveats") or []]
    for item in do_not_use:
        caveats.append(f"Do not use for: {item}")

    title = registry_entry.get("name") or pkg_id
    card = {
        "schema_version": rc.SCHEMA_VERSION,
        "report_card_id": pkg_id,
        "title": str(title),
        "compiled_from": {
            "compiler": rc.COMPILER,
            "compiler_version": rc.COMPILER_VERSION,
            "source_kind": "specialist-package",
            "source_id": pkg_rel,
            "dataset_hashes": [],
        },
        "subject": {
            "target": (
                rc.measured(str(title), [f"{registry_src}#name"])
                if registry_entry
                else rc.measured(pkg_id, [f"{report_src}#id"])
            ),
            "owner_goal": rc.missing(
                "The specialist package format does not record the owner goal "
                "that framed the run.",
                [report_src],
            ),
            "base_model": rc.measured(
                _model_label(
                    {
                        "id": report.get("base"),
                        "precision": report.get("precision"),
                    }
                ),
                [f"{report_src}#base"],
            ),
            "candidate_model": rc.measured(pkg_id, [f"{report_src}#id"]),
            "method": rc.measured(
                report.get("training_method")
                or registry_entry.get("training")
                or "unspecified",
                [f"{report_src}#training_method"],
            ),
            "artifact": artifact_block,
        },
        "decision": decision_block,
        "gates": gates,
        "slices": [],
        "performance": performance,
        "eval_validity": validity,
        "evidence": evidence,
        "caveats": caveats,
    }
    return rc.finalize(card)


def _is_routed(verdict: str, do_not_use: list[Any]) -> bool:
    """True when the package states a narrowed safe envelope."""
    lowered = str(verdict).lower()
    markers = ("only", "do not use", "not the", "routed", "narrow")
    return bool(do_not_use) or any(m in lowered for m in markers)


def _specialist_gate(
    score: dict[str, Any],
    index: int,
    report: dict[str, Any],
    report_src: str,
    hist_note: str,
) -> dict[str, Any]:
    suite = score.get("suite") or f"suite-{index}"
    pointer = f"{report_src}#scores[{index}]"
    baseline_key, candidate_key = _score_keys(score, suite)

    baseline = rc.historical(
        score[baseline_key], [f"{pointer}.{baseline_key}"], note=hist_note
    )
    candidate = rc.historical(
        score[candidate_key], [f"{pointer}.{candidate_key}"], note=hist_note
    )
    rows = score.get("n")
    sample = (
        rc.historical(rows, [f"{pointer}.n"], note=hist_note)
        if _numeric(rows)
        else rc.missing("The legacy score records no row count.", [f"{pointer}.n"])
    )
    frontier = (
        rc.historical(score["frontier"], [f"{pointer}.frontier"], note=hist_note)
        if _numeric(score.get("frontier"))
        else rc.missing(
            "No frontier-ceiling score is recorded for this benchmark, so it is "
            "unverified as a ruler for absolute capability.",
            [pointer],
        )
    )

    role = "primary" if index == 0 else _classify_role(suite)
    delta = rc.delta_field(
        baseline, candidate, f"{pointer}.{baseline_key}", f"{pointer}.{candidate_key}"
    )
    # No threshold is recorded in the package format. A regression/breadth gate
    # can still be judged without one: scoring below the baseline IS the
    # regression. The primary gate cannot, so it stays `missing`.
    if role == "primary":
        passed = rc.missing(
            "The specialist package records no ship threshold for the primary "
            "gate, so a pass/fail result cannot be derived.",
            [pointer],
        )
    elif rc.has_value(delta):
        regressed = float(delta["value"]) < 0
        passed = rc.derived(
            not regressed,
            derived_from=[f"{pointer}.{baseline_key}", f"{pointer}.{candidate_key}"],
            note=(
                "No threshold was recorded. Derived as failing because the "
                "candidate scored below the baseline on a non-primary gate."
                if regressed
                else "No threshold was recorded. Derived as passing because the "
                "candidate did not score below the baseline."
            ),
        )
    else:
        passed = rc.missing(
            "Neither a threshold nor a derivable delta is available for this gate.",
            [pointer],
        )

    return {
        "role": role,
        "name": suite,
        "metric": suite,
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "threshold": rc.missing(
            "The specialist package format records no per-gate threshold.",
            [pointer],
        ),
        "passed": passed,
        "sample_size": sample,
        "frontier_ceiling": frontier,
        "eval_identity": {
            "suite": suite,
            "command": rc.missing(
                "The specialist package format records no eval command, so this "
                "gate cannot be replayed from the report card alone.",
                [pointer],
            ),
            "date": (
                rc.measured(
                    report.get("evaluation_date") or report.get("updated"),
                    [f"{report_src}#evaluation_date"],
                )
                if (report.get("evaluation_date") or report.get("updated"))
                else rc.missing("No evaluation date is recorded.", [report_src])
            ),
            "frozen": rc.missing(
                "The package does not record whether this suite is frozen.",
                [pointer],
            ),
        },
    }


def _score_keys(score: dict[str, Any], suite: str) -> tuple[str, str]:
    """Identify the baseline and candidate keys of a legacy score row.

    Fails closed rather than guessing: a row whose baseline/candidate pair
    cannot be identified unambiguously is a mapping gap to fix in the source,
    not something to infer.
    """
    numeric = [k for k, v in score.items() if k not in SCORE_META_KEYS and _numeric(v)]
    # Whole-token matching, not substring: `database_expert` contains "base" but
    # is a candidate, and misreading it as the baseline would silently invert the
    # delta's sign.
    baselines = [
        k
        for k in numeric
        if set(k.replace("-", "_").lower().split("_")) & set(BASELINE_KEY_HINTS)
    ]
    candidates = [k for k in numeric if k not in baselines]
    if len(baselines) != 1 or len(candidates) != 1:
        raise rc.ReportCardError(
            f"score `{suite}`: cannot identify exactly one baseline and one "
            f"candidate key (numeric keys: {sorted(numeric)}). Fix the source "
            "eval report rather than inferring a mapping."
        )
    return baselines[0], candidates[0]


def _classify_role(suite: str) -> str:
    lowered = suite.lower()
    return "breadth" if any(m in lowered for m in BREADTH_MARKERS) else "regression"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", help="canonical factory run folder (runs/<id>)")
    source.add_argument("--specialist", help="committed specialist package directory")
    p.add_argument("--out", help="directory to write report-card.json + report-card.html")
    p.add_argument("--json-out", help="explicit path for the JSON payload")
    p.add_argument("--html-out", help="explicit path for the static HTML report")
    p.add_argument(
        "--allow-report-only",
        action="store_true",
        help="permit a non-ship card with open blockers. Ship claims stay strict.",
    )
    p.add_argument(
        "--print",
        dest="print_json",
        action="store_true",
        help="print the JSON payload to stdout instead of writing files",
    )
    args = p.parse_args(argv)

    if not (args.out or args.json_out or args.html_out or args.print_json):
        p.error("one of --out, --json-out, --html-out, or --print is required")

    try:
        card = (
            compile_from_run(Path(args.run))
            if args.run
            else compile_from_specialist(Path(args.specialist))
        )
    except rc.ReportCardError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    errors = rc.validate(card, allow_report_only=args.allow_report_only)
    if errors:
        # Fail closed: diagnostics are printed locally, no artifact is written.
        print(
            f"FAIL: report card for {card.get('report_card_id')} did not validate "
            f"({len(errors)} problem(s)); no artifact was written.",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    payload = rc.dumps(card)
    page = rc.render_html(card)

    if args.print_json:
        sys.stdout.write(payload)

    targets: list[tuple[Path, str]] = []
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        targets.append((out / "report-card.json", payload))
        targets.append((out / "report-card.html", page))
    if args.json_out:
        targets.append((Path(args.json_out), payload))
    if args.html_out:
        targets.append((Path(args.html_out), page))

    for path, content in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"report card: wrote {path}")

    if not targets and not args.print_json:  # pragma: no cover - guarded above
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
