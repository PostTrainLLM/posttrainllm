"""One frozen two-fit pilot; hidden TEST grading starts after all rankings seal."""

import hashlib
import json
import sys
from datetime import datetime, timezone

from engine import Engine
from executor import execute
from predictor import FEATURES, METHODS, brier, charged_public, fit, select
from prepare import OUT, write


def read(name):
    return json.loads((OUT / name).read_text())


def hidden(task, pool, label):
    for row in pool:
        row["hidden"] = execute(
            row["code"],
            task["hidden"],
            f"{label}-{task['id']}-r{row['round']}-c{row['candidate']}-hidden",
        )


def freeze(resume=False):
    target = OUT / "execution-admission.json"
    if target.exists():
        if not resume:
            raise SystemExit("Execution admission exists; preserve original attempt.")
        assert not (OUT / "predictor-initial.json").exists()
        assert not (OUT / "sealed-test-selections.json").exists()
        assert len(list((OUT / "pools").glob("*.json"))) == 1
        assert read("resource-usage.json")["generated"] == 4
        prior = read("pools/shared-clamp-r1.json")
        assert len(prior) == 4 and all(not r["public"]["passed"] for r in prior)
        write(
            OUT / "tiny-gate-amendment.json",
            {
                "reason": "The initial gate incorrectly required coder competence for pipeline correctness. Exact generated TRAIN outputs failed assertions normally. Qualify the pipeline with the unchanged frontier positive control and these negative controls; reuse all four generated candidates without resampling.",
                "previous_admission_sha256": hashlib.sha256(
                    target.read_bytes()
                ).hexdigest(),
                "new_runner_sha256": hashlib.sha256(
                    open(__file__, "rb").read()
                ).hexdigest(),
                "test_outcomes_seen": False,
                "predictor_fits_so_far": 0,
                "prior_elapsed_seconds": read("resource-usage.json")["elapsed_seconds"],
            },
        )
        return read("contract.json")
    contract = read("contract.json")
    frontier = read("frontier-result.json")
    if not frontier["valid"]:
        frontier = read("frontier-result-syntax-regrade.json")
    assert frontier["valid"]
    assert (
        hashlib.sha256((OUT / "tasks.jsonl").read_bytes()).hexdigest()
        == contract["data_sha256"]
    )
    assert (
        hashlib.sha256(
            open(__file__.replace("run.py", "executor.py"), "rb").read()
        ).hexdigest()
        == frontier["executor_source_sha256"]
    )
    admission = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "source_sha256": {
            name: hashlib.sha256(
                open(__file__.replace("run.py", name), "rb").read()
            ).hexdigest()
            for name in [
                "run.py",
                "engine.py",
                "predictor.py",
                "executor.py",
                "calibrate.py",
            ]
        },
        "e2e": {
            "policy_seconds_per_task": 120,
            "round1": "shared initial pool charged independently to each policy",
            "round2": "fresh policy-specific pool, offset=10000+method_index*1000; public feedback only",
            "training_amortization": "entire predictor fit time divided by six TEST tasks; two fits charged to adapted",
            "diagnostic_execution": "all public cases recorded, but static/random ranking never sees them; excluded unused calls are explicit",
        },
        "models": "Initial ridge TRAIN R1; one update TRAIN R1+R2; DEV R2 chooses retention before TEST R2 generation.",
        "test_seal": "All TEST selections and model weights are written before any hidden TEST call.",
        "paid_usd": 0,
    }
    write(target, admission)
    return contract


def train_and_select(tasks, pools, engine):
    train, dev = (
        [t for t in tasks if t["split"] == "train"],
        [t for t in tasks if t["split"] == "dev"],
    )
    for task in train:
        hidden(task, pools[task["id"]][1], "training")
    parent = fit([r for t in train for r in pools[t["id"]][1]])
    write(OUT / "predictor-initial.json", parent)
    for index, task in enumerate(tasks):
        if task["split"] == "test":
            continue
        first = pools[task["id"]][1]
        choice = select(first, "execution", {}, index)["index"]
        pools[task["id"]][2] = engine.pool(task, index, 2, first[choice])
        hidden(
            task,
            pools[task["id"]][2],
            "training" if task["split"] == "train" else "development",
        )
    updated = fit([r for t in train for turn in [1, 2] for r in pools[t["id"]][turn]])
    write(OUT / "predictor-updated.json", updated)
    return retain_update(dev, pools, parent, updated)


def retain_update(dev, pools, parent, updated):
    dev_rows = [r for t in dev for r in pools[t["id"]][2]]
    models = {"frozen": parent, "adapted": updated}
    counts = {
        method: sum(
            pools[t["id"]][2][select(pools[t["id"]][2], method, models, 0)["index"]][
                "hidden"
            ]["passed"]
            for t in dev
        )
        for method in ["frozen", "adapted"]
    }
    retain = counts["adapted"] >= counts["frozen"] and brier(dev_rows, updated) < brier(
        dev_rows, parent
    )
    decision = {
        "retain_update": retain,
        "selected_success": counts,
        "brier": {
            "frozen": brier(dev_rows, parent),
            "updated": brier(dev_rows, updated),
        },
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }
    write(OUT / "development-decision.json", decision)
    models["adapted"] = updated if retain else parent
    return models


def cost(first, second, method, first_choice, second_choice, models):
    public = charged_public(first, method, first_choice) + charged_public(
        second, method, second_choice, final=True
    )
    train = (
        0
        if method in ["random", "static", "execution"]
        else models["frozen"]["seconds"]
    )
    if method == "adapted":
        train += read("predictor-updated.json")["seconds"]
    return {
        "generation_seconds": sum(r["generation_seconds"] for r in first + second),
        "generation_tokens": sum(r["generation_tokens"] for r in first + second),
        "execution_seconds": sum(r["seconds"] for r in public),
        "execution_calls": sum(r["calls"] for r in public),
        "selection_seconds": first_choice["seconds"] + second_choice["seconds"],
        "amortized_training_seconds": train / 6,
        "diagnostic_calls_excluded": sum(r["public"]["calls"] for r in first + second)
        - sum(r["calls"] for r in public),
    }


def test_pools(tasks, pools, engine, models):
    plans = []
    for index, task in enumerate(tasks):
        if task["split"] != "test":
            continue
        first = pools[task["id"]][1]
        common = engine.pool(
            task, index, 2, first[select(first, "execution", {}, index)["index"]]
        )
        pools[task["id"]][2] = common
        for method_index, method in enumerate(METHODS):
            choice1 = select(first, method, models, index)
            common_choice = select(common, method, models, index + 100)
            fresh = engine.pool(
                task,
                index,
                2,
                first[choice1["index"]],
                10000 + method_index * 1000,
                method,
            )
            choice2 = select(fresh, method, models, index + 100)
            charges = cost(first, fresh, method, choice1, choice2, models)
            charges["total_seconds"] = sum(
                charges[k]
                for k in [
                    "generation_seconds",
                    "execution_seconds",
                    "selection_seconds",
                    "amortized_training_seconds",
                ]
            )
            plans.append(
                {
                    "task": task["id"],
                    "method": method,
                    "first": choice1,
                    "common": common_choice,
                    "fresh": choice2,
                    "cost": charges,
                    "within_cap": charges["total_seconds"] <= 120,
                }
            )
    write(
        OUT / "sealed-test-selections.json",
        {
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "plans": plans,
            "models": models,
            "meaning": "No hidden TEST execution has occurred before this seal.",
        },
    )
    return plans


def grade_test(tasks, pools, plans):
    by_id = {task["id"]: task for task in tasks}
    for task in tasks:
        if task["split"] != "test":
            continue
        for turn in [1, 2]:
            hidden(task, pools[task["id"]][turn], "sealed-shared")
    for plan in plans:
        task = by_id[plan["task"]]
        fresh = read(f"pools/{plan['method']}-{task['id']}-r2.json")
        hidden(task, fresh, "sealed-" + plan["method"])
        first, common = pools[task["id"]][1], pools[task["id"]][2]
        plan.update(
            {
                "round1_passed": first[plan["first"]["index"]]["hidden"]["passed"],
                "selection_only_passed": common[plan["common"]["index"]]["hidden"][
                    "passed"
                ],
                "e2e_passed": fresh[plan["fresh"]["index"]]["hidden"]["passed"]
                and plan["within_cap"],
                "common_oracle": any(r["hidden"]["passed"] for r in common),
                "fresh_oracle": any(r["hidden"]["passed"] for r in fresh),
            }
        )
        write(OUT / "test-results.json", plans)
    write(OUT / "graded-shared-pools.json", pools)


def run():
    resume = "--resume-tiny-gate" in sys.argv
    contract = freeze(resume)
    tasks = [
        json.loads(line) for line in (OUT / "tasks.jsonl").read_text().splitlines()
    ]
    engine = Engine(contract)
    if resume:
        engine.started -= read("tiny-gate-amendment.json")["prior_elapsed_seconds"]
        engine.generated = 4
    pools = {}
    for index, task in enumerate(tasks):
        pools[task["id"]] = {
            1: read("pools/shared-clamp-r1.json")
            if resume and index == 0
            else engine.pool(task, index, 1)
        }
        if index == 0:
            assert all(
                r["generation_tokens"] > 0 and r["public"]["calls"] == 1
                for r in pools[task["id"]][1]
            )
            probe = select(pools[task["id"]][1], "execution", {}, 0)
            assert len(FEATURES) == 9 and probe["index"] == 0
            positive = read("executions/frontier-syntax-regrade-clamp/receipt.json")
            assert positive["passed"] and positive["calls"] == 1
            write(
                OUT / "tiny-gate.json",
                {
                    "passed": True,
                    "task": task["id"],
                    "meaning": "TRAIN-only actual generation plus frontier positive/execution negative controls; no required coder accuracy.",
                },
            )
    models = train_and_select(tasks, pools, engine)
    plans = test_pools(tasks, pools, engine, models)
    grade_test(tasks, pools, plans)
    engine.guard()
    write(
        OUT / "execution-complete.json",
        {"complete": True, "predictor_fits": 2, "generated": engine.generated},
    )


if __name__ == "__main__":
    run()
