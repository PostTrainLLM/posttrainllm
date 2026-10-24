"""Frozen decision splits and source-bound subscription-Codex ceiling gates.

Contract: docs/factory/specialist-labs.md. Gold labels never enter frontier prompts.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

from common import ROOT, digest, file_hash, frontier_answers, write_json, write_rows
from decision import identity, metrics, validate_splits


def prepare(rows, out, seed=7):
    validate_splits({"source": rows})
    if len(rows) < 20 or any("answer" not in row for row in rows):
        raise ValueError("prepare requires >=20 distinct labeled examples")
    rows = sorted(rows, key=identity)
    random.Random(seed).shuffle(rows)
    holdout = max(1, len(rows) // 10)
    groups = {
        "calibration": rows[:holdout],
        "test": rows[holdout : holdout * 2],
        "regression": rows[holdout * 2 : holdout * 3],
        "train": rows[holdout * 3 :],
    }
    validate_splits(groups)
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    for name, items in groups.items():
        write_rows(out / f"{name}.jsonl", items)
    write_json(
        out / "splits.json",
        {
            "seed": seed,
            "source_sha256": digest(rows),
            "splits": {
                name: {
                    "count": len(items),
                    "identities": [identity(row) for row in items],
                }
                for name, items in groups.items()
            },
        },
    )


def ceiling(rows, out):
    validate_splits({"ceiling": rows})
    sys.path.insert(0, str(ROOT))
    from scripts.factory.frontier_cli import answer_schema

    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    schema = out / "schema.json"
    write_json(schema, answer_schema())
    request = [
        {"id": row["id"], "question": row["question"], "options": row["options"]}
        for row in rows
    ]
    prompt = (
        "Choose the correct option label for every independent question. Return one answer per id. No tools or files.\n"
        + json.dumps(request)
    )
    write_json(out / "request.json", request)
    started = time.monotonic()
    answers, kinds = frontier_answers(schema, out, prompt)
    mapping = {row["id"]: row["answer"].strip() for row in answers}
    valid = len(mapping) == len(answers) == len(rows) and all(
        mapping.get(row["id"]) == row["answer"] for row in rows
    )
    write_json(
        out / "ceiling.json",
        {
            "schema": "decision-ceiling-v1",
            "valid": valid,
            "identities": sorted(identity(row) for row in rows),
            "gold_sha256": digest(
                sorted((identity(row), row["answer"]) for row in rows)
            ),
            "request_sha256": digest(request),
            "answers_sha256": file_hash(out / "answers.json"),
            "validator_sha256": file_hash(__file__),
            "model": "gpt-6.1-sol",
            "observed_item_types": sorted(set(kinds)),
            "elapsed_seconds": time.monotonic() - started,
            "paid_usd": 0,
        },
    )
    if not valid:
        raise ValueError(
            "frontier ceiling failed; no local decision accuracy is permitted"
        )


def evaluate(records, ceiling_receipt, calibration=None, baseline=None, threshold=0):
    if (
        ceiling_receipt.get("schema") != "decision-ceiling-v1"
        or not ceiling_receipt.get("valid")
        or ceiling_receipt.get("validator_sha256") != file_hash(__file__)
        or ceiling_receipt.get("identities")
        != sorted(row["identity"] for row in records)
        or ceiling_receipt.get("gold_sha256")
        != digest(sorted((r["identity"], r["answer"]) for r in records))
    ):
        raise ValueError("missing, failed, stale or mismatched frontier ceiling")
    result = {
        "candidate": metrics(records, calibration, threshold),
        "decision": "report-only; gates required for ship",
    }
    if baseline is not None:
        candidate_gold = {(r["identity"], r["answer"]) for r in records}
        if candidate_gold != {(r["identity"], r["answer"]) for r in baseline} or len(
            baseline
        ) != len(records):
            raise ValueError("baseline and candidate examples/gold must match")
        result["baseline"] = metrics(baseline)
        result["accuracy_delta"] = (
            result["candidate"]["accuracy"] - result["baseline"]["accuracy"]
        )
    return result
