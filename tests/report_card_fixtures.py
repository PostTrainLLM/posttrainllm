#!/usr/bin/env python3
"""Fixture factory-run folders and specialist packages for report-card tests.

One fixture per supported outcome class, so schema and validator changes are
exercised against every shape the public surface has to render honestly —
including the shapes that MUST fail closed.

These are **fixtures, not evidence**: every model id, score, and command is
synthetic. Nothing here is a measured posttrainllm result, and nothing here is
published. Real evidence lives in canonical run folders and committed
specialist packages.

Usage:
    python3 tests/report_card_fixtures.py <case> <dest-dir>
    python3 tests/report_card_fixtures.py --list

Cases whose name starts with `bad-` are expected to fail validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

#: Fixture cases that must compile AND pass validation.
GOOD_CASES = (
    "ship-verified",
    "routed-ship",
    "report-only",
    "retry",
    "reject",
)

#: Fixture cases that must fail closed. A report card that cannot be traced to
#: its sources, or that hides a regression behind a ship claim, is not
#: publishable.
BAD_CASES = (
    "bad-missing-evidence-ship",
    "bad-undisclosed-routed-ship",
    "bad-leakage",
)

#: Cases whose source is a specialist package rather than a run folder.
SPECIALIST_CASES = ("historical",)

ALL_CASES = GOOD_CASES + SPECIALIST_CASES + BAD_CASES

#: Cases that need `--allow-report-only` to publish (non-ship with blockers).
NEEDS_REPORT_ONLY = ("report-only",)


def _write(dest: Path, name: str, payload: Any) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        (dest / name).write_text(payload, encoding="utf-8")
    else:
        (dest / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Shared run-folder scaffolding
# ---------------------------------------------------------------------------


def _config(run_id: str, primary_min: float = 0.9, drop_max: float = 3.0) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "target": "fixture-target",
        "owner_goal": "Exercise the report-card contract without compute.",
        "base_model": {
            "id": "fixture-base",
            "revision": "abc1234",
            "precision": "bf16",
        },
        "candidate": {
            "method": "sft-lora",
            "adapter_format": "tgla",
            "training_command": "posttrainllm sft fixture-base --data train.jsonl",
        },
        "eval": {
            "primary": "fixture-gate",
            "regression": "fixture-breadth",
            # Explicit gate -> slice pointers; the compiler never infers these.
            "primary_slice": "fixture_gate_rows",
            "regression_slice": "fixture_breadth",
            "threshold": {"primary_min": primary_min, "breadth_drop_max_pp": drop_max},
        },
    }


def _dataset() -> dict[str, Any]:
    return {
        "dataset_id": "fixture-dataset",
        "sources": [{"kind": "fixture", "path": "evals/fixture/train.jsonl", "rows": 40}],
        "processing": {"dedupe": True, "quality_filter": True, "heldout_split": "locked"},
        "counts": {"train_rows": 40, "heldout_rows": 20, "dropped_rows": 2},
    }


def _eval(model_id: str, score: float, passed: bool | None, perf: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_id": model_id,
        "command": f"posttrainllm eval-gate {model_id}",
        "suite": "fixture-gate",
        "score": score,
        "passed": passed,
        "date": "2026-07-20",
        "latency_ms": 42.0 if perf else None,
        "peak_rss_mb": 1280.0 if perf else None,
        "tokens_per_second": 77.0 if perf else None,
        "notes": "Synthetic fixture eval; no model was run.",
    }
    return payload


def _slices(baseline: float, candidate: float, breadth: tuple[float, float] | None) -> dict[str, Any]:
    slices: dict[str, Any] = {
        "fixture_gate_rows": {
            "rows": 20,
            "metric": "accuracy",
            "baseline": baseline,
            "candidate": candidate,
            "delta": round(candidate - baseline, 6),
            "pass": candidate >= baseline,
        },
        "fixture_hard_slice": {
            "rows": 6,
            "metric": "accuracy",
            "candidate": 0.5,
            "note": "Candidate-only slice: the fixture records no baseline here.",
        },
    }
    if breadth is not None:
        base_b, cand_b = breadth
        slices["fixture_breadth"] = {
            "rows": 30,
            "metric": "accuracy",
            "baseline": base_b,
            "candidate": cand_b,
            "delta": round(cand_b - base_b, 6),
            "pass": cand_b >= base_b,
        }
    return {
        "overall": {"rows": 20, "note": "Synthetic fixture slice metrics."},
        "slices": slices,
    }


def _validity(overlap: str = "no-overlap", frontier: float | None = 1.0) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "frozen_eval": {
            "id": "fixture-gate-v1",
            "rows": 20,
            "sha256": "f" * 64,
            "note": "Synthetic frozen fixture split.",
        },
        "overlap_check": {
            "result": overlap,
            "command": "python3 scripts/fixture_overlap_check.py",
            "note": (
                "Synthetic overlap check."
                if overlap == "no-overlap"
                else "Synthetic contaminated fixture: 4 held-out prompts appear in train."
            ),
        },
        "known_limitations": ["Synthetic fixture eval; not a real benchmark."],
    }
    if frontier is not None:
        payload["frontier"] = {
            "model": "fixture-frontier",
            "date": "2026-07-20",
            "command": "python3 scripts/fixture_frontier_probe.py",
            "by_suite": {"fixture-gate": frontier, "fixture-breadth": frontier},
        }
    return payload


def _cost() -> dict[str, Any]:
    return {
        "training_time_seconds": 900,
        "training_time_seconds_note": "Synthetic fixture timing.",
        "training_cost_usd": 0,
        "training_cost_usd_note": "Local run; no paid API was used.",
        "eval_time_seconds": 120,
    }


def _provenance(baseline_cmd: str, candidate_cmd: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "renderer": "tests/report_card_fixtures.py",
        "renderer_command": "python3 tests/report_card_fixtures.py <case> <dest>",
        "git": {"commit": "0" * 40, "branch": "fixture", "dirty": False},
        "commands": {
            "baseline": baseline_cmd,
            "candidate": candidate_cmd,
            "training": "posttrainllm sft fixture-base --data train.jsonl",
            "publish_check": "python3 scripts/check_factory_run_publish.py <run-dir>",
        },
        "datasets": [
            {"path": "evals/fixture/train.jsonl", "rows": 40, "sha256": "a" * 64}
        ],
    }


def _artifact(shipped: bool, routing: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_id": "fixture-adapter",
        "kind": "adapter",
        "path": "specialists/fixture-adapter",
        "base_model": "fixture-base",
        "format": "tgla",
        "package_dir": "specialists/fixture-adapter" if shipped else None,
        "shipped": shipped,
    }
    if routing:
        payload["routing_constraint"] = routing
    return payload


def _decision(
    decision: str,
    *,
    reason: str,
    failure_reason: str | None = None,
    confidence: str = "not-applicable",
    lesson: str | None = None,
    next_action: str | None = None,
    blocked_by: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "decision": decision,
        "reason": reason,
        "failure_reason": failure_reason,
        "failure_reason_confidence": confidence,
        "lesson": lesson,
        "next_action": next_action,
        "evidence_sources": ["eval-candidate.json", "slice-metrics.json"],
        "blocked_by": blocked_by or [],
    }


TRACE_REVIEW = """# Fixture Trace Review

## Trace Review

Synthetic fixture. No real traces exist, so reward hacking, hallucinated
schema, fake reasoning, format collapse, and plausible-but-wrong answers are
all recorded as unchecked.
"""


def _run(
    dest: Path,
    run_id: str,
    *,
    baseline_score: float,
    candidate_score: float,
    passed: bool | None,
    decision: dict[str, Any],
    artifact: dict[str, Any] | None,
    breadth: tuple[float, float] | None = (0.60, 0.62),
    validity: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    perf: bool = True,
) -> None:
    baseline = _eval("fixture-base", baseline_score, False)
    candidate = _eval("fixture-candidate", candidate_score, passed, perf=perf)
    _write(dest, "config.json", _config(run_id))
    _write(dest, "dataset.json", _dataset())
    _write(dest, "eval-baseline.json", baseline)
    _write(dest, "eval-candidate.json", candidate)
    _write(dest, "slice-metrics.json", _slices(baseline_score, candidate_score, breadth))
    _write(dest, "decision.json", decision)
    _write(dest, "provenance.json", _provenance(baseline["command"], candidate["command"]))
    _write(dest, "trace_review.md", TRACE_REVIEW)
    _write(dest, "train.log", "Synthetic fixture train log.\n")
    if artifact is not None:
        _write(dest, "artifact.json", artifact)
    if validity is not None:
        _write(dest, "eval-validity.json", validity)
    if cost is not None:
        _write(dest, "cost.json", cost)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def build(case: str, dest: Path) -> Path:
    """Write fixture `case` into `dest` and return the compiler source path."""
    if case == "ship-verified":
        # Complete evidence chain: measured gates, frontier-validated ruler,
        # identified frozen eval, passing overlap check, no blockers.
        _run(
            dest,
            "2026-07-20-fixture-ship-verified",
            baseline_score=0.70,
            candidate_score=0.95,
            passed=True,
            decision=_decision(
                "ship",
                reason="Primary gate cleared the frozen threshold with no regression.",
                next_action="Register the fixture specialist package.",
            ),
            artifact=_artifact(True),
            validity=_validity(),
            cost=_cost(),
        )
        return dest

    if case == "routed-ship":
        # Target improves, breadth regresses. Publishable only because the
        # routing constraint names the safe envelope.
        _run(
            dest,
            "2026-07-20-fixture-routed-ship",
            baseline_score=0.58,
            candidate_score=1.00,
            passed=True,
            decision=_decision(
                "ship",
                reason="Depth gate cleared, but breadth regressed; ship routed only.",
                next_action="Keep routed-only warnings in every public surface.",
            ),
            artifact=_artifact(
                True,
                routing="Safe only behind the fixture file-ops route; not a general planner.",
            ),
            breadth=(0.60, 0.42),
            validity=_validity(),
            cost=_cost(),
        )
        return dest

    if case == "report-only":
        # Honest non-ship with open blockers: needs --allow-report-only.
        _run(
            dest,
            "2026-07-20-fixture-report-only",
            baseline_score=0.70,
            candidate_score=0.88,
            passed=False,
            decision=_decision(
                "retry-eval",
                reason="Candidate improved but the eval cannot certify a ship yet.",
                failure_reason="No public execution benchmark exists for this target.",
                confidence="exact",
                lesson="A gate without a public benchmark cannot promote an artifact.",
                next_action="Build the public execution gate, then re-score.",
                blocked_by=["public benchmark bundle unavailable"],
            ),
            artifact=_artifact(False),
            perf=False,
        )
        return dest

    if case == "retry":
        # Non-ship, no blockers: publishable without --allow-report-only.
        _run(
            dest,
            "2026-07-20-fixture-retry",
            baseline_score=0.70,
            candidate_score=0.71,
            passed=False,
            decision=_decision(
                "retry-training",
                reason="The candidate barely moved the primary gate.",
                failure_reason="Training pressure was too low to change behaviour.",
                confidence="inferred",
                lesson="A one-point move at this step count is noise, not a recipe.",
                next_action="Rerun with a higher learning rate and more steps.",
            ),
            artifact=None,
            validity=_validity(),
        )
        return dest

    if case == "reject":
        _run(
            dest,
            "2026-07-20-fixture-reject",
            baseline_score=0.70,
            candidate_score=0.31,
            passed=False,
            decision=_decision(
                "reject",
                reason="The candidate collapsed well below the frozen baseline.",
                failure_reason="Policy collapse: the adapter degraded the base model.",
                confidence="exact",
                lesson="This recipe is ruled out for the target at any pressure.",
                next_action="Abandon this recipe and pick a different method.",
            ),
            artifact=_artifact(False),
            breadth=(0.60, 0.35),
            validity=_validity(),
            cost=_cost(),
        )
        return dest

    if case == "bad-missing-evidence-ship":
        # A ship claim whose primary candidate score was never recorded.
        _run(
            dest,
            "2026-07-20-fixture-bad-missing",
            baseline_score=0.70,
            candidate_score=0.95,
            passed=True,
            decision=_decision(
                "ship",
                reason="Claims a ship without a recorded candidate measurement.",
                next_action="Record the candidate eval.",
            ),
            artifact=_artifact(True),
            validity=_validity(),
            cost=_cost(),
        )
        broken = json.loads((dest / "eval-candidate.json").read_text(encoding="utf-8"))
        broken["score"] = None
        _write(dest, "eval-candidate.json", broken)
        return dest

    if case == "bad-undisclosed-routed-ship":
        # Breadth regressed and no routing constraint discloses the envelope.
        _run(
            dest,
            "2026-07-20-fixture-bad-routed",
            baseline_score=0.58,
            candidate_score=1.00,
            passed=True,
            decision=_decision(
                "ship",
                reason="Presents a regression-carrying candidate as a general win.",
                next_action="Disclose the routing constraint.",
            ),
            artifact=_artifact(True),
            breadth=(0.60, 0.42),
            validity=_validity(),
            cost=_cost(),
        )
        return dest

    if case == "bad-leakage":
        # Train/eval overlap was detected: publication is blocked outright,
        # but the measured candidate numbers stay in the payload.
        _run(
            dest,
            "2026-07-20-fixture-bad-leakage",
            baseline_score=0.70,
            candidate_score=0.99,
            passed=True,
            decision=_decision(
                "ship",
                reason="Scores are contaminated by train/eval overlap.",
                next_action="Rebuild the held-out split.",
            ),
            artifact=_artifact(True),
            validity=_validity(overlap="overlap-detected"),
            cost=_cost(),
        )
        return dest

    if case == "historical":
        # Legacy specialist package: recorded scores with no run provenance.
        _write(
            dest,
            "eval_report.json",
            {
                "id": "fixture-historical-specialist",
                "updated": "2026-07-20",
                "evaluation_date": "2026-05-01",
                "artifact": "hf://models/posttrainllm/fixture-historical-specialist",
                "base": "fixture-base",
                "precision": "bf16",
                "training_method": "fixture distillation",
                "evidence_quality": "historical-results-without-raw-predictions",
                "scores": [
                    {
                        "suite": "fixture_depth_gate",
                        "n": 12,
                        "stock_base": 0.58,
                        "fixture_candidate": 1.0,
                        "frontier": 1.0,
                        "source": "docs/factory/report-card.md",
                    },
                    {
                        "suite": "fixture_out_of_domain_breadth",
                        "n": 52,
                        "stock_base": 0.596,
                        "fixture_candidate": 0.423,
                        "delta": -0.173,
                        "source": "docs/factory/report-card.md",
                    },
                ],
                "performance": {
                    "training_cost_usd": 0,
                    "training_cost_note": "Local fixture run.",
                    "training_time_seconds": None,
                    "latency_ms": None,
                    "tokens_per_second": None,
                    "peak_rss_mb": None,
                    "missing_evidence": (
                        "Historical fixture: timing, memory, throughput, and raw "
                        "traces were not preserved."
                    ),
                },
                "verdict": "ship only as a routed fixture specialist; do not use as a general model",
                "caveats": ["Synthetic historical fixture; not a measured result."],
            },
        )
        _write(dest, "model_card.md", "# Fixture historical specialist\n\nSynthetic fixture.\n")
        _write(dest, "prompt.md", "Fixture prompt contract.\n")
        _write(dest, "tinygpt.lock.json", {"schema_version": 1, "fixture": True})
        return dest

    raise SystemExit(f"unknown fixture case: {case} (known: {', '.join(ALL_CASES)})")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--list", "-l"):
        print("\n".join(ALL_CASES))
        return 0
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    case, dest = argv[0], Path(argv[1])
    build(case, dest)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
