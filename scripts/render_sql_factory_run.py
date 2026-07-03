#!/usr/bin/env python3
"""Render the current SQL routed POC as a canonical factory run folder.

This is intentionally metadata-only. It records the measured SQL evidence that
already exists in the repo docs/fixtures, but it does not start a model server,
train an adapter, or rerun a GPU eval.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ID = "2026-07-02-sql-routed-qwen06-v1"


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_report(payloads: dict[str, dict[str, Any]]) -> str:
    config = payloads["config"]
    dataset = payloads["dataset"]
    baseline = payloads["eval-baseline"]
    candidate = payloads["eval-candidate"]
    artifact = payloads["artifact"]
    decision = payloads["decision"]
    delta = candidate["score"] - baseline["score"]

    return f"""# qwen06-sql-routed-v1 — report artifact

## Decision

Decision: {decision["decision"]}

Reason: {decision["reason"]}

## Target

- Target: {config["target"]}
- Base model: {config["base_model"]["id"]}
- Candidate: {candidate["model_id"]}
- Training method: {config["candidate"]["method"]}
- Artifact: {artifact["path"]}

## Data

- Dataset: {dataset["dataset_id"]}
- Train rows: {dataset["counts"]["train_rows"]}
- Heldout rows: {dataset["counts"]["heldout_rows"]}
- Preference rows: 2156
- Filters: deterministic non-overlap for public/synthetic training fixtures
- Known gaps: b-mc2 has exact-match SQL only; public execution DBs are not local yet

## Eval

| Metric | Baseline | Candidate | Delta | Pass |
|---|---:|---:|---:|---|
| Synthetic SQLite execution, 50 rows | {baseline["score"]:.3f} | {candidate["score"]:.3f} | {delta:.3f} | yes |
| Synthetic SQLite exact, 50 rows | 0.140 | 0.840 | 0.700 | yes |
| Public b-mc2 exact, 64 rows | 0.484 T5-small | 0.531 routed public adapter | +0.047 | yes |
| Label-free router, 114 rows | n/a | 64 public / 50 synthetic high confidence | n/a | yes |

## Performance

| Metric | Value |
|---|---:|
| Train time | n/a, rendered from completed local runs |
| Eval time | n/a |
| Latency | n/a |
| tok/s | n/a |
| RAM / peak RSS | n/a |

## Failures

- What failed: public execution DB bundle is not local yet; output hygiene still relies on first-SELECT extraction.
- Likely cause: current public gate is exact match over schema text, not execution over populated DBs.
- Data fix: run the Spider execution gate once a Spider SQLite bundle is local.
- Training fix: use SQL-only preference data for output hygiene before package/ship.
- Eval fix: add clean-SQL and execution-accuracy gates to this run shape.

## Next Action

{decision["next_action"]}
"""


def build_payloads(run_id: str) -> dict[str, dict[str, Any]]:
    synthetic_train = ROOT / "evals/sql-poc-expanded/train.jsonl"
    synthetic_dev = ROOT / "evals/sql-poc-expanded/dev.jsonl"
    synthetic_prefs = ROOT / "evals/sql-poc-expanded/preferences.jsonl"
    public_train = ROOT / "evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl"
    public_dev = ROOT / "evals/sql-public-bmc2-train-v4-joinweighted/dev.jsonl"
    public_prefs = ROOT / "evals/sql-public-bmc2-train-v4-joinweighted/preferences.jsonl"
    mixed = ROOT / "evals/sql-routed-mixed-v1/mixed114.jsonl"

    synthetic_train_rows = line_count(synthetic_train)
    synthetic_dev_rows = line_count(synthetic_dev)
    synthetic_pref_rows = line_count(synthetic_prefs)
    public_train_rows = line_count(public_train)
    public_dev_rows = line_count(public_dev)
    public_pref_rows = line_count(public_prefs)
    mixed_rows = line_count(mixed)

    config = {
        "run_id": run_id,
        "target": "sql-routed-specialist-poc",
        "owner_goal": (
            "Publish the current SQL routed POC as a transparent factory report "
            "artifact with measured blockers before packaging."
        ),
        "base_model": {
            "id": "Qwen/Qwen3-0.6B",
            "revision": "c1899de289a04d12100db370d81485cdf75e47ca",
            "precision": "bf16",
        },
        "candidate": {
            "method": "routed-sft-lora",
            "adapter_format": "tgla",
            "training_command": (
                "see docs/specialists/b1-sql-poc.md for public-v4 and "
                "synthetic-expanded adapter recipes"
            ),
        },
        "eval": {
            "primary": "sql-poc-expanded-synthetic-execution",
            "regression": "sql-public-bmc2-exact-and-router-smoke",
            "threshold": {
                "primary_min": 0.86,
                "breadth_drop_max_pp": 0,
            },
        },
    }

    dataset = {
        "dataset_id": "sql-routed-mixed-v1",
        "sources": [
            {"kind": "synthetic-sft", "path": "evals/sql-poc-expanded/train.jsonl", "rows": synthetic_train_rows},
            {
                "kind": "synthetic-heldout",
                "path": "evals/sql-poc-expanded/dev.jsonl",
                "rows": synthetic_dev_rows,
            },
            {
                "kind": "synthetic-preference",
                "path": "evals/sql-poc-expanded/preferences.jsonl",
                "rows": synthetic_pref_rows,
            },
            {
                "kind": "public-sft",
                "path": "evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl",
                "rows": public_train_rows,
            },
            {
                "kind": "public-heldout",
                "path": "evals/sql-public-bmc2-train-v4-joinweighted/dev.jsonl",
                "rows": public_dev_rows,
            },
            {
                "kind": "public-preference",
                "path": "evals/sql-public-bmc2-train-v4-joinweighted/preferences.jsonl",
                "rows": public_pref_rows,
            },
            {"kind": "routed-eval", "path": "evals/sql-routed-mixed-v1/mixed114.jsonl", "rows": mixed_rows},
        ],
        "processing": {
            "dedupe": True,
            "quality_filter": True,
            "heldout_split": "locked public64 + synthetic50",
        },
        "counts": {
            "train_rows": synthetic_train_rows + public_train_rows,
            "heldout_rows": synthetic_dev_rows + public_dev_rows,
            "dropped_rows": 0,
        },
    }

    baseline = {
        "model_id": "Qwen/Qwen3-0.6B baseline",
        "command": "tinygpt generate + eval-sql over evals/sql-poc-expanded/dev.jsonl",
        "suite": "sql-poc-expanded-synthetic-execution",
        "score": 0.160,
        "passed": False,
        "date": "2026-07-02",
        "latency_ms": None,
        "peak_rss_mb": None,
        "tokens_per_second": None,
        "notes": "Synthetic SQLite execution baseline on 50 heldout rows; exact match was 0.140.",
    }

    candidate = {
        "model_id": "qwen06-sql-routed-v1",
        "command": "scripts/run_sql_routed_generate.py + eval-sql/score_sql_public_exact",
        "suite": "sql-poc-expanded-synthetic-execution",
        "score": 0.860,
        "passed": True,
        "date": "2026-07-02",
        "latency_ms": None,
        "peak_rss_mb": None,
        "tokens_per_second": None,
        "notes": (
            "Routed public-v4 + synthetic-expanded adapters: public b-mc2 exact 0.531 "
            "on 64 rows, synthetic exact 0.840 on 50 rows, router smoke 64/50 high-confidence."
        ),
    }

    artifact = {
        "artifact_id": "qwen06-sql-routed-v1",
        "kind": "report-routed-adapter",
        "path": "docs/factory/public-artifacts.md#qwen06-sql-routed-v1",
        "base_model": "Qwen/Qwen3-0.6B",
        "format": "report-only",
        "package_dir": None,
        "shipped": False,
    }

    decision = {
        "decision": "retry-eval",
        "reason": (
            "The routed setup is the current best SQL candidate and passes the current "
            "public exact plus synthetic execution gates, but it is not a shipped specialist "
            "until a public execution benchmark and performance measurements exist."
        ),
        "next_action": (
            "Run scripts/build_sql_spider_execution_gate.py against a local Spider DB "
            "bundle, score the routed candidate, then re-render this report with latency/RAM/tok-s."
        ),
        "blocked_by": [
            "public execution DB bundle not local",
            "latency/RAM/tok-s not measured",
            "clean-SQL output hygiene gate missing",
        ],
    }

    return {
        "config": config,
        "dataset": dataset,
        "eval-baseline": baseline,
        "eval-candidate": candidate,
        "artifact": artifact,
        "decision": decision,
    }


def render(out: Path, run_id: str, force: bool) -> None:
    if out.exists():
        if not force:
            raise SystemExit(f"{out} already exists; pass --force to overwrite")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    payloads = build_payloads(run_id)
    for name, payload in payloads.items():
        write_json(out / f"{name}.json", payload)
    (out / "train.log").write_text(
        "Rendered from completed local SQL runs; no training was started by this command.\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_report(payloads), encoding="utf-8")
    print(f"rendered SQL factory run: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=f"runs/{DEFAULT_RUN_ID}", help="Output run directory.")
    ap.add_argument("--run-id", default=DEFAULT_RUN_ID)
    ap.add_argument("--force", action="store_true", help="Overwrite an existing output directory.")
    args = ap.parse_args()
    render(Path(args.out), args.run_id, args.force)


if __name__ == "__main__":
    main()
