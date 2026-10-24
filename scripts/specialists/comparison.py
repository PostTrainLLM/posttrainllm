"""Held-out, base-bound before/after reports using the existing factory compiler.

Contract: docs/factory/specialist-labs.md. No ship or parity claim is inferred.
"""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

import numpy as np

from common import ROOT, digest, read_json, write_json


def check_decision_ceiling(heldout, receipt):
    import decision

    dummy = [{"identity": decision.identity(r), "answer": r["answer"]} for r in heldout]
    from common import file_hash
    import decision_eval

    if (
        receipt.get("schema") != "decision-ceiling-v1"
        or not receipt.get("valid")
        or receipt.get("validator_sha256") != file_hash(decision_eval.__file__)
        or receipt.get("identities") != sorted(r["identity"] for r in dummy)
        or receipt.get("gold_sha256")
        != digest(sorted((r["identity"], r["answer"]) for r in dummy))
    ):
        raise ValueError(
            "validate this held-out benchmark with Codex first, then supply its ceiling receipt"
        )


def score_decision(model, groups, receipt, excluded, kind, budget):
    import decision
    from decision_eval import evaluate

    heldout = groups["test"] + groups["regression"]
    started = time.monotonic()
    calibration_scores = [model.score(r) for r in groups["calibration"]]
    fit = decision.calibrate(calibration_scores, excluded)
    scores = []
    for index, row in enumerate(heldout):
        scores.append(model.score(row))
        budget.progress(index + 1, len(heldout), phase=f"evaluating {kind}")
    result = evaluate(scores, receipt, fit)["candidate"]
    cut = len(groups["test"])
    result.update(
        primary=decision.metrics(scores[:cut], fit),
        regression=decision.metrics(scores[cut:], fit),
        calibration=fit,
        scores=scores,
        model_identity=model.model_identity,
        latency_ms=(time.monotonic() - started)
        * 1000
        / (len(heldout) + len(calibration_scores)),
    )
    return result


def verify_training_rows(runtime, metadata, rows):
    run_id = metadata.get("run_id")
    if run_id is None:
        return  # Legacy CLI artifacts retain their identity-only training contract.
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise ValueError("invalid training run identity")
    request = read_json(runtime.state_root / "jobs" / run_id / "request.json")
    if digest(request["payload"]["rows"]) != digest(rows):
        raise ValueError("candidate was trained on different rows or labels")


def decision_compare(runtime, payload, budget):
    import decision

    groups = payload["splits"]
    if set(groups) != {"train", "calibration", "test", "regression"}:
        raise ValueError("comparison needs the four frozen decision splits")
    decision.validate_splits(groups)
    path = runtime.artifact_path(payload["artifact"], "decision")
    metadata = read_json(path / "specialist.json")
    if set(metadata["train_identities"]) != {
        decision.identity(r) for r in groups["train"]
    }:
        raise ValueError("candidate was trained on a different split")
    heldout = groups["test"] + groups["regression"]
    # Validate the ceiling before loading a model or exposing any accuracy.
    receipt = payload.get("ceiling", {})
    check_decision_ceiling(heldout, receipt)
    verify_training_rows(runtime, metadata, groups["train"])
    excluded = [{"identity": decision.identity(r)} for r in groups["train"] + heldout]
    results = []
    for kind in ("baseline", "candidate"):
        model = decision.DecisionModel(
            runtime.decision_model
            if kind == "baseline" or runtime.backend == "mlx"
            else str(path),
            runtime.backend,
            runtime.decision_revision
            if kind == "baseline" or runtime.backend == "mlx"
            else None,
            budget=budget,
            adapter=str(path)
            if kind == "candidate" and runtime.backend == "mlx"
            else None,
        )
        if kind == "baseline" and model.model_identity != metadata["base_identity"]:
            raise ValueError("selected baseline does not match the candidate's base")
        result = score_decision(model, groups, receipt, excluded, kind, budget)
        results.append(result)
        del model
        gc.collect()
    return {
        "metric": "accuracy",
        "direction": "higher",
        "baseline": results[0],
        "candidate": results[1],
        "sample_size": len(groups["test"]),
        "regression_size": len(groups["regression"]),
        "dataset_sha256": digest(groups),
        "ceiling": receipt,
        "metadata": metadata,
    }


def check_forecast_windows(payload, metadata):
    train = payload["train_rows"]
    if metadata["train_sha256"] != digest(train):
        raise ValueError("candidate was trained on different series windows")
    horizon = payload["horizon"]
    origins = payload["origins"]
    if len(origins) != 2 or origins[1] < origins[0] + horizon:
        raise ValueError("comparison needs disjoint primary and regression windows")
    values = payload["series"]["values"]
    for row in train:
        end = len(row["context"][0]) + len(row["target"][0])
        if (
            end > min(origins)
            or row["context"] != [r[: len(row["context"][0])] for r in values]
            or row["target"] != [r[len(row["context"][0]) : end] for r in values]
        ):
            raise ValueError(
                "training windows overlap or do not match the held-out series history"
            )


def forecast_metrics(rows, identity, elapsed):
    return {
        "primary": {"negative_mae": -rows[0]["model_mae"]},
        "regression": {"negative_mae": -rows[1]["model_mae"]},
        "mae": float(np.mean([r["model_mae"] for r in rows])),
        "pinball": float(np.mean([r["pinball"] for r in rows])),
        "seasonal_naive_mae": float(np.mean([r["naive_mae"] for r in rows])),
        "model_identity": identity,
        "latency_ms": elapsed * 500,
        "windows": rows,
    }


def forecast_compare(runtime, payload, budget):
    import forecast

    path = runtime.artifact_path(payload["artifact"], "forecast")
    metadata = read_json(path / "specialist.json")
    check_forecast_windows(payload, metadata)
    horizon, origins = payload["horizon"], payload["origins"]
    results = []
    for kind in ("baseline", "candidate"):
        model = forecast.load(
            runtime.forecast_model if kind == "baseline" else str(path),
            runtime.forecast_revision if kind == "baseline" else None,
            budget=budget,
        )
        if kind == "baseline" and model.source_identity != metadata["base_identity"]:
            raise ValueError("selected baseline does not match the candidate's base")
        started = time.monotonic()
        result = forecast.backtest(
            model, payload["series"], horizon, origins, payload["season"], budget
        )
        rows = result["rows"]
        results.append(
            forecast_metrics(rows, model.source_identity, time.monotonic() - started)
        )
        budget.progress(len(results), 2, phase=f"evaluated {kind}")
        del model
        gc.collect()
    return {
        "metric": "negative_mae",
        "direction": "higher",
        "baseline": results[0],
        "candidate": results[1],
        "sample_size": results[0]["windows"][0]["observed_targets"],
        "regression_size": results[0]["windows"][1]["observed_targets"],
        "dataset_sha256": digest(payload["series"]),
        "metadata": metadata,
    }


def report_validity(result, limits):
    metric = result["metric"]
    return {
        "known_limitations": limits,
        "frozen_eval": {
            "id": result["dataset_sha256"],
            "sha256": result["dataset_sha256"],
            "rows": result["sample_size"] + result["regression_size"],
        },
        "overlap_check": {
            "result": "no-overlap",
            "note": "Compared the candidate's recorded training identities/windows against these held-out splits.",
        },
        "frontier": {"by_suite": {metric: 1.0, "regression": 1.0}}
        if result.get("ceiling", {}).get("valid")
        else {},
    }


def report(folder, result, budget):
    """Adapt measured fragments into the canonical, validated report-only card."""
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    from build_fine_tune_report_card import compile_from_run
    import fine_tune_report_card as rc

    out = Path(folder) / "report"
    out.mkdir()
    metric = result["metric"]
    baseline, candidate = result["baseline"], result["candidate"]
    primary = candidate["primary"][metric]
    delta = primary - baseline["primary"][metric]
    regression_delta = candidate["regression"][metric] - baseline["regression"][metric]
    limits = [
        "Bounded local comparison, not upstream parity or a general model qualification.",
        "No automatic ship decision. Inspect primary and regression results before selecting another run.",
    ]
    fragments = {
        "config.json": {
            "run_id": Path(folder).name,
            "target": f"{metric} held-out comparison",
            "owner_goal": "Measure whether a local fine-tune helped on frozen data",
            "base_model": {"id": baseline["model_identity"]},
            "candidate": {"method": "local specialist adaptation"},
            "eval": {
                "primary": "heldout",
                "regression": "regression",
                "primary_slice": "heldout",
                "regression_slice": "regression",
                "threshold": {
                    "primary_min": baseline["primary"][metric],
                    "breadth_drop_max_pp": 0,
                },
            },
        },
        "dataset.json": {"sha256": result["dataset_sha256"]},
        "eval-baseline.json": {
            "suite": metric,
            "score": baseline["primary"][metric],
            "model_id": baseline["model_identity"],
        },
        "eval-candidate.json": {
            "suite": metric,
            "score": primary,
            "model_id": candidate["model_identity"],
            "passed": delta >= 0 and regression_delta >= 0,
            "latency_ms": candidate["latency_ms"],
            "peak_rss_mb": budget.measurements()["process_peak_rss_bytes"] / 2**20,
        },
        "decision.json": {
            "decision": "retry-eval",
            "reason": "Report-only: small held-out comparison; no deployment qualification.",
            "blocked_by": ["broader frozen capability and regression evidence"],
            "failure_reason": "Broader qualification evidence has not been collected.",
            "failure_reason_confidence": "missing-evidence",
            "lesson": "Inspect held-out deltas separately from training loss; a completed update does not establish useful improvement.",
            "evidence_sources": [f"runs/{Path(folder).name}/comparison.json"],
            "next_action": "Inspect both slices before deciding whether further training is worthwhile.",
        },
        "slice-metrics.json": {
            "slices": {
                name: {
                    "metric": metric,
                    "baseline": baseline[kind][metric],
                    "candidate": candidate[kind][metric],
                    "rows": result[size],
                }
                for name, kind, size in [
                    ("heldout", "primary", "sample_size"),
                    ("regression", "regression", "regression_size"),
                ]
            }
        },
        "cost.json": {
            "training_time_seconds": result["metadata"].get("elapsed_seconds"),
            "training_cost_usd": 0,
            "eval_time_seconds": budget.measurements()["elapsed_seconds"],
        },
        "eval-validity.json": report_validity(result, limits),
        "comparison.json": {k: v for k, v in result.items() if k != "metadata"},
    }
    for name, value in fragments.items():
        write_json(out / name, value)
    card = compile_from_run(out)
    errors = rc.validate(card, allow_report_only=True)
    if errors:
        raise ValueError("report contract failed: " + "; ".join(errors))
    write_json(out / "report-card.json", card)
    (out / "report-card.html").write_text(rc.render_html(card))
    return {
        "comparison": {k: v for k, v in result.items() if k != "metadata"},
        "report_card": card,
        "primary_delta": delta,
        "regression_delta": regression_delta,
        "decision": "report-only",
    }
