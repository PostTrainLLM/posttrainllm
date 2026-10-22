"""Derive the report-only rejection from frozen selections and real receipts."""

import hashlib
import json
import random
import statistics
import subprocess
import sys

from predictor import METHODS, brier
from prepare import GROUNDING, OUT, ROOT, write


def read(name):
    return json.loads((OUT / name).read_text())


def summary(rows, method):
    selected = [row for row in rows if row["method"] == method]
    costs = [row["cost"] for row in selected]
    return {
        "count": len(selected),
        "selection_only_passed": sum(r["selection_only_passed"] for r in selected),
        "end_to_end_passed": sum(r["e2e_passed"] for r in selected),
        "previously_solved_regressions": sum(
            r["round1_passed"] and not r["e2e_passed"] for r in selected
        ),
        "common_pool_oracle": sum(r["common_oracle"] for r in selected),
        "fresh_pool_oracle": sum(r["fresh_oracle"] for r in selected),
        **cost_summary(costs, all(r["within_cap"] for r in selected)),
    }


def cost_summary(costs, within_caps):
    return {
        "execution_calls": sum(c["execution_calls"] for c in costs),
        "charged_seconds": sum(c["total_seconds"] for c in costs),
        "median_task_seconds": statistics.median(c["total_seconds"] for c in costs),
        "selection_seconds": sum(c["selection_seconds"] for c in costs),
        "amortized_training_seconds": sum(
            c["amortized_training_seconds"] for c in costs
        ),
        "generation_tokens": sum(c["generation_tokens"] for c in costs),
        "generation_tps": sum(c["generation_tokens"] for c in costs)
        / sum(c["generation_seconds"] for c in costs),
        "diagnostic_calls_excluded": sum(c["diagnostic_calls_excluded"] for c in costs),
        "within_all_task_caps": within_caps,
    }


def paired(rows, method, baseline, metric):
    baseline_rows = {r["task"]: r for r in rows if r["method"] == baseline}
    delta = [
        int(r[metric]) - int(baseline_rows[r["task"]][metric])
        for r in rows
        if r["method"] == method
    ]
    rng = random.Random(201)
    samples = sorted(
        statistics.mean(rng.choices(delta, k=len(delta))) for _ in range(10000)
    )
    return {
        "delta": statistics.mean(delta),
        "paired_95_percentile_ci": [samples[249], samples[9749]],
        "unit": "held-out problem",
        "samples": 10000,
        "seed": 201,
    }


def accounting(rows):
    pools = [json.loads(path.read_text()) for path in (OUT / "pools").glob("*.json")]
    all_rows = [row for pool in pools for row in pool]
    assert len(all_rows) == 264
    generation = sum(row["generation_seconds"] for row in all_rows)
    public = sum(row["public"]["seconds"] for row in all_rows)
    receipts = [
        json.loads(path.read_text())
        for path in (OUT / "executions").glob("*-hidden/receipt.json")
    ]
    hidden = sum(row["seconds"] for row in receipts)
    # Residual includes model setup, JSON/loop and two fit costs. Charge its
    # entirety to every policy, rather than silently treating setup as free.
    residual = max(
        0, read("resource-usage.json")["elapsed_seconds"] - generation - public - hidden
    )
    for row in rows:
        row["cost"]["shared_overhead_allocation_seconds"] = residual / 6
        row["cost"]["total_seconds"] += residual / 6
        row["within_cap"] = row["cost"]["total_seconds"] <= 120
        row["e2e_passed"] = row["e2e_passed"] and row["within_cap"]
    return {
        "measured_global_seconds": read("resource-usage.json")["elapsed_seconds"],
        "generation_seconds": generation,
        "public_seconds": public,
        "hidden_grading_seconds": hidden,
        "unattributed_shared_overhead_seconds": residual,
        "all_generated": len(all_rows),
        "invalid_candidates": sum(row["public"]["invalid"] for row in all_rows),
        "public_timeouts": sum(
            row["public"]["stop_reason"] is not None and not row["public"]["invalid"]
            for row in all_rows
        ),
        "limit": "Setup/serialization are conservatively allocated as a measured residual; separate model-load latency was not instrumented. Shared-host timings are not an acceleration claim.",
    }


def factory_inputs(receipt):
    contract = read("contract.json")
    write(
        OUT / "config.json",
        {
            "run_id": OUT.name,
            "target": "Mac-local repair selection",
            "candidate": {
                "method": "ordinary ridge outcome classifier; fixed stock 1.7B coder",
                "training_command": ".venv/bin/python scripts/repair_selection/run.py --resume-tiny-gate",
            },
            "eval": {
                "primary": "Hidden all-pass repair success under equal 120-second per-task caps"
            },
            "contract": contract,
        },
    )
    write(
        OUT / "dataset.json",
        {
            "counts": {
                **contract["counts"],
                "train_rows": 8,
                "dev_rows": 4,
                "heldout_rows": 6,
            },
            "sources": [
                {
                    "path": str((OUT / "tasks.jsonl").relative_to(ROOT)),
                    "sha256": contract["data_sha256"],
                    "rows": 18,
                }
            ],
            "processing": {
                "split": "underlying-problem/template disjoint; TRAIN updates only; DEV retention before TEST"
            },
        },
    )
    for name, method in [("baseline", "static"), ("candidate", "frozen")]:
        row = receipt["systems"][method]
        write(
            OUT / f"eval-{name}.json",
            {
                "model_id": f"fixed-qwen17-{method}-selector",
                "suite": "repair-selection-201-v1",
                "score": row["end_to_end_passed"] / row["count"],
                "passed": True,
                "date": "2026-10-22",
                "command": ".venv/bin/python scripts/repair_selection/report.py",
                "train_time": row["amortized_training_seconds"],
                "eval_time": row["charged_seconds"],
                "latency_ms": row["median_task_seconds"] * 1000,
                "peak_rss_mb": receipt["resources"]["peak_rss_bytes"] / 1024**2,
                "tokens_per_second": row["generation_tps"],
                "cost_usd": 0,
                "execution_calls": row["execution_calls"],
            },
        )


def fragments(receipt):
    factory_inputs(receipt)
    write(
        OUT / "decision.json",
        {
            "decision": "reject",
            "reason": receipt["decision"],
            "failure_reason": "Learned selection ties static/direct/random at the finite candidate-pool ceiling; DEV rejects feedback update.",
            "failure_reason_confidence": "exact",
            "next_action": "Close this bounded experiment; no automatic model/data scale-up.",
            "lesson": "A selector cannot repair an all-wrong candidate pool. The simple baselines already reach this finite pool ceiling; a learned policy earns no extra execution cost.",
            "evidence_sources": [
                "sealed-test-selections.json",
                "test-results.json",
                "development-decision.json",
                "summary.json",
            ],
        },
    )
    write(
        OUT / "slice-metrics.json",
        {
            "overall": receipt["comparisons"],
            "slices": {
                method: {
                    "baseline": 2 / 6,
                    "candidate": row["end_to_end_passed"] / row["count"],
                    "delta": row["end_to_end_passed"] / row["count"] - 2 / 6,
                    "rows": 6,
                }
                for method, row in receipt["systems"].items()
            },
        },
    )
    (OUT / "trace_review.md").write_text(
        "# Trace Review\n\nAll policies solve chunks and invert_groups. Other common pools have no hidden-test-passing candidate. Publicly passing nested_numeric_sum candidates still fail hidden type cases. The update worsens DEV Brier and is rejected before hidden TEST. Adapted-policy rows therefore use the retained frozen parent. No coder weights change, no recursive-improvement claim, and no production integration.\n"
    )
    (OUT / "train.log").write_text(
        json.dumps(
            {
                "initial": read("predictor-initial.json"),
                "updated": read("predictor-updated.json"),
                "development": read("development-decision.json"),
            },
            indent=2,
        )
        + "\n"
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/factory/assemble_factory_run.py"),
            str(OUT),
            "--force",
            "--publish-check",
        ],
        check=True,
    )


def frontier_proof():
    original = read("frontier-result.json")
    result = (
        original if original["valid"] else read("frontier-result-syntax-regrade.json")
    )
    assert result["valid"]
    return {
        "passed": result["passed"],
        "count": result["count"],
        "model": original["model"],
        "answers_sha256": hashlib.sha256(
            (OUT / "frontier-answers.json").read_bytes()
        ).hexdigest(),
        "correction": None
        if original["valid"]
        else "Original17/18 was an over-restrictive AST filter rejecting valid dict.fromkeys; all exact original answers pass after correction.",
    }


def report():
    assert read("execution-complete.json")["complete"]
    contract, rows = read("contract.json"), read("test-results.json")
    assert (
        read("development-decision.json")["selected_at"]
        < read("sealed-test-selections.json")["sealed_at"]
    )
    assert len(rows) == 30 and read("execution-complete.json")["predictor_fits"] == 2
    costs = accounting(rows)
    systems = {method: summary(rows, method) for method in METHODS}
    assert all(
        row["end_to_end_passed"] == 2 and row["common_pool_oracle"] == 2
        for row in systems.values()
    )
    shared = read("graded-shared-pools.json")
    test_rows = [
        r for task in shared.values() for r in task["2"] if r["split"] == "test"
    ]
    frozen = read("predictor-initial.json")
    receipt = {
        "issue": 201,
        "counts": contract["counts"],
        "model": contract["model"]["model"],
        "runtime": {
            **contract["runtime"],
            "numpy": json.loads((GROUNDING / "runtime-lock.json").read_text())["numpy"],
        },
        "data_sha256": contract["data_sha256"],
        "frontier": frontier_proof(),
        "execution_admission_sha256": hashlib.sha256(
            (OUT / "execution-admission.json").read_bytes()
        ).hexdigest(),
        "test_selections_sha256": hashlib.sha256(
            (OUT / "sealed-test-selections.json").read_bytes()
        ).hexdigest(),
        "revision": contract["model"]["revision"],
        "contract_sha256": hashlib.sha256(
            (OUT / "contract.json").read_bytes()
        ).hexdigest(),
        "systems": systems,
        "comparisons": {
            method: paired(rows, method, "static", "e2e_passed")
            for method in ["frozen", "adapted"]
        },
        "development": read("development-decision.json"),
        "test_brier_frozen": brier(test_rows, frozen),
        "adapted_policy": "DEV rejected the update; TEST adapted-policy rows use the frozen parent.",
        "resources": read("resource-usage.json"),
        "accounting": costs,
        "bfcl": {
            "passed": 16,
            "count": 20,
            "source": str((GROUNDING / "bfcl-baseline-result.json").relative_to(ROOT)),
            "meaning": "Reuse exact unchanged stock coder, runtime and calibrated BFCL prompt; coder not updated.",
        },
        "decision": "Reject learned selection for this pilot: no gain over cheaper static/random or direct execution; reject feedback update on DEV.",
        "limitations": contract["limitations"],
        "local_run": str(OUT.relative_to(ROOT)),
        "paid_usd": 0,
    }
    write(OUT / "summary.json", receipt)
    write(ROOT / "evals/repair-selection-201-v1.json", receipt)
    fragments(receipt)
    print(
        json.dumps(
            {"decision": receipt["decision"], "systems": systems, "costs": costs},
            indent=2,
        )
    )


if __name__ == "__main__":
    report()
