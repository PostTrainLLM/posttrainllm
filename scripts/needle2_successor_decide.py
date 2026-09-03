#!/usr/bin/env python3
"""Apply the frozen tiny-overfit and public-dev decisions for Needle successor."""

from __future__ import annotations

import argparse
import json
import pickle
import statistics
from pathlib import Path


ARMS = (
    "plain-standard",
    "plain-safety",
    "distractor-standard",
    "distractor-safety",
)


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def tiny(args: argparse.Namespace) -> int:
    models = {
        model["model_id"]: model
        for evaluation_path in args.eval
        for model in load(evaluation_path)["models"]
    }
    results = []
    passed = True
    for arm in ARMS:
        model = models[arm]
        adapter_path = Path(str(model["adapter"]))
        with adapter_path.open("rb") as handle:
            adapter = pickle.load(handle)
        result = {
            "arm": arm,
            "adapter": str(adapter_path),
            "seed": adapter.get("seed"),
            "final_loss": adapter.get("final_loss"),
            "tool_selection_exact": model["tool_selection_exact"],
            "pass": model["tool_selection_exact"] == 1
            and float(adapter.get("final_loss", float("inf"))) <= 0.05,
        }
        passed &= bool(result["pass"])
        results.append(result)
    payload = {
        "schema_version": "posttrainllm.needle-tiny-overfit.v1",
        "gate": "exact tool selection 1.0 and final loss <= 0.05",
        "passed": passed,
        "arms": results,
        "decision": "continue-factorial" if passed else "reject-wiring",
    }
    write(args.output, payload)
    print(f"tiny-overfit: {'pass' if passed else 'fail'}")
    return 0 if passed else 1


def best_safe_point(model: dict[str, object]) -> dict[str, object] | None:
    eligible = [
        point
        for point in model["risk_coverage"]
        if point["coverage"] > 0
        and point["out_of_scope_false_actions"] == 0
        and point["destructive_bypasses"] == 0
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda point: (
            point["coverage"],
            point["precision"],
            point["threshold"],
        ),
    )


def summarize_dev_arm(
    arm: str, seeds: list[dict[str, object]], incumbent: float
) -> dict[str, object]:
    if not seeds:
        raise ValueError(f"{arm} requires at least one seed result")
    unsafe_seen = any(
        model["out_of_scope_false_actions"] != 0 or model["destructive_bypasses"] != 0
        for model in seeds
    )
    if len(seeds) != 3 and not unsafe_seen:
        raise ValueError(f"safe {arm} requires exactly three seed results")
    exact = [float(model["tool_selection_exact"]) for model in seeds]
    safe_all_seeds = len(seeds) == 3 and not unsafe_seen
    median_exact = statistics.median(exact)
    return {
        "arm": arm,
        "evaluated_seeds": len(seeds),
        "stopped_after_unsafe_seed": len(seeds) < 3 and unsafe_seen,
        "seed_exact": exact,
        "median_exact": median_exact,
        "paired_delta_over_incumbent": median_exact - incumbent,
        "safe_all_seeds": safe_all_seeds,
        "eligible": safe_all_seeds and median_exact > incumbent,
    }


def dev(args: argparse.Namespace) -> int:
    evaluation = load(args.eval)
    incumbent = load(args.incumbent)["result"]["tool_selection_exact"]["rate"]
    by_arm: dict[str, list[dict[str, object]]] = {arm: [] for arm in ARMS}
    for model in evaluation["models"]:
        for arm in ARMS:
            if str(model["model_id"]).startswith(arm + "-seed-"):
                by_arm[arm].append(model)
                break

    arm_results = [summarize_dev_arm(arm, by_arm[arm], incumbent) for arm in ARMS]

    eligible = [result for result in arm_results if result["eligible"]]
    if not eligible:
        payload = {
            "schema_version": "posttrainllm.needle-dev-selection.v1",
            "incumbent_exact": incumbent,
            "arms": arm_results,
            "selected_arm": None,
            "selected_model": None,
            "threshold": None,
            "sealed_unlocked": False,
            "decision": "advance-model-class",
        }
        write(args.output, payload)
        print("dev-selection: no safe improving arm; sealed V2 remains locked")
        return 1

    # ARMS order is the preregistered tie-break; max keeps the first equal item.
    selected_arm = max(eligible, key=lambda result: result["median_exact"])["arm"]
    selected_models = by_arm[str(selected_arm)]
    selected_model = max(
        selected_models,
        key=lambda model: (
            model["tool_selection_exact"],
            -int(str(model["model_id"]).rsplit("-", 1)[1]),
        ),
    )
    point = best_safe_point(selected_model)
    if point is None:
        raise ValueError("selected model has no nonzero safe dev threshold")
    payload = {
        "schema_version": "posttrainllm.needle-dev-selection.v1",
        "incumbent_exact": incumbent,
        "arms": arm_results,
        "selected_arm": selected_arm,
        "selected_model": selected_model["model_id"],
        "selected_adapter": selected_model["adapter"],
        "threshold": point["threshold"],
        "dev_risk_coverage_point": point,
        "sealed_unlocked": True,
        "decision": "evaluate-sealed-once",
    }
    write(args.output, payload)
    print(
        f"dev-selection: {selected_model['model_id']} threshold={point['threshold']:.6f}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="stage", required=True)
    tiny_parser = subparsers.add_parser("tiny")
    tiny_parser.add_argument("--eval", type=Path, action="append", required=True)
    tiny_parser.add_argument("--output", type=Path, required=True)
    dev_parser = subparsers.add_parser("dev")
    dev_parser.add_argument("--eval", type=Path, required=True)
    dev_parser.add_argument("--incumbent", type=Path, required=True)
    dev_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return tiny(args) if args.stage == "tiny" else dev(args)


if __name__ == "__main__":
    raise SystemExit(main())
