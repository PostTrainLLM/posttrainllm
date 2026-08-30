#!/usr/bin/env python3
"""Validate a Foundry evidence receipt for posttrainllm.

Reads a receipt from a file path or stdin (``-``) and asserts:

1. Required top-level fields and shape per ``docs/factory/foundry-evidence.md``.
2. No denylisted private-payload field names anywhere in the tree.
3. No string value exceeds the 4 KB metadata ceiling (catches accidental
   prompt/completion/log streaming).
4. Total receipt size is under the byte ceiling.
5. Every ``quality_claims`` entry has the full provenance set required to
   update a public quality claim: source_revision, model, eval_config,
   dataset_version, observed_at, artifact_location, retention.
6. ``publication_authority`` is ``manual`` (no auto-publish drift).
7. Every ``local_runs`` entry has ``publication == "pending-approval"``;
   completed decision evidence requires source revision, while active lifecycle
   discovery may honestly omit it.
8. Any projected lifecycle state is schema-v1, bounded, and operational only.

Exit code 0 = clean, 1 = validation failure, 2 = IO/usage error.

Usage:

    python3 scripts/factory/check_foundry_receipt.py receipt.json
    python3 scripts/factory/foundry_receipt.py --check        # self-check
    cat receipt.json | python3 scripts/factory/check_foundry_receipt.py -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
RECEIPT_BYTE_CEILING = 256 * 1024
STRING_CEILING = 4096

DENYLIST_FIELDS = (
    "prompt",
    "completion",
    "gold",
    "prediction",
    "trajectory",
    "raw_log",
    "train_log_contents",
    "checkpoint",
    "adapter_bytes",
    "weights",
    "weight_bytes",
    "optimizer_state",
    "api_key",
    "token",
    "secret",
    "password",
    "credential",
    "dataset_rows_text",
    "dataset_content",
    "prompt_text",
    "output_text",
)

REQUIRED_TOP = (
    "schema_version",
    "project",
    "generated_at",
    "source_revision",
    "ci",
    "public_site",
    "playground",
    "artifacts",
    "local_runs",
    "nightly",
    "publication_authority",
    "accepted_exceptions",
    "blocked",
)

REQUIRED_CLAIM_PROVENANCE = (
    "metric",
    "source_revision",
    "model",
    "eval_config",
    "dataset_version",
    "observed_at",
    "artifact_location",
    "retention",
)


def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def walk_private(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(bad in key_lower for bad in DENYLIST_FIELDS):
                fail(f"private field at {path}.{k} (denylisted)", errors)
            walk_private(v, f"{path}.{k}", errors)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk_private(v, f"{path}[{i}]", errors)
    elif isinstance(value, str):
        if len(value) > STRING_CEILING:
            fail(
                f"oversize string at {path} ({len(value)}b > {STRING_CEILING}b)", errors
            )


def validate(receipt: dict[str, Any], raw_bytes: int, errors: list[str]) -> None:
    if raw_bytes > RECEIPT_BYTE_CEILING:
        fail(f"receipt is {raw_bytes}b over {RECEIPT_BYTE_CEILING}b ceiling", errors)
    for field in REQUIRED_TOP:
        if field not in receipt:
            fail(f"missing top-level field: {field}", errors)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        fail(f"schema_version must be {SCHEMA_VERSION}", errors)
    if receipt.get("project") != "posttrainllm":
        fail(f"project must be 'posttrainllm', got {receipt.get('project')!r}", errors)
    if receipt.get("publication_authority") != "manual":
        fail(
            f"publication_authority must be 'manual', got {receipt.get('publication_authority')!r}",
            errors,
        )
    sr = receipt.get("source_revision") or {}
    if not sr.get("commit"):
        fail("source_revision.commit missing", errors)

    walk_private(receipt, "$", errors)

    for i, art in enumerate(receipt.get("artifacts", [])):
        if not art.get("id"):
            fail(f"artifacts[{i}].id missing", errors)
        for j, claim in enumerate(art.get("quality_claims", [])):
            for field in REQUIRED_CLAIM_PROVENANCE:
                if not claim.get(field):
                    fail(
                        f"artifacts[{i}].quality_claims[{j}].{field} missing — claim cannot update a public quality claim",
                        errors,
                    )

    for i, run in enumerate(receipt.get("local_runs", [])):
        if run.get("publication") != "pending-approval":
            fail(
                f"local_runs[{i}].publication must be 'pending-approval', got {run.get('publication')!r}",
                errors,
            )
        lifecycle = run.get("lifecycle") or {}
        if run.get("decision") and not run.get("source_revision"):
            fail(f"local_runs[{i}].source_revision missing", errors)
        if lifecycle:
            if lifecycle.get("schema_version") != 1:
                fail(f"local_runs[{i}].lifecycle.schema_version must be 1", errors)
            if lifecycle.get("phase") not in (
                "created",
                "data-ready",
                "training",
                "trained",
                "evaluating",
                "evaluated",
                "packaging",
                "packaged",
                "reporting",
                "decided",
                "failed",
            ):
                fail(f"local_runs[{i}].lifecycle.phase invalid", errors)
            if (
                not isinstance(lifecycle.get("revision"), int)
                or lifecycle["revision"] < 1
            ):
                fail(f"local_runs[{i}].lifecycle.revision invalid", errors)
            failure = lifecycle.get("failure")
            if failure:
                if lifecycle.get("phase") != "failed":
                    fail(
                        f"local_runs[{i}].lifecycle.failure requires failed phase",
                        errors,
                    )
                if len(str(failure.get("code", ""))) > 64:
                    fail(f"local_runs[{i}].lifecycle.failure.code oversized", errors)
                if len(str(failure.get("summary", ""))) > 240:
                    fail(f"local_runs[{i}].lifecycle.failure.summary oversized", errors)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="receipt JSON path, or '-' for stdin")
    args = p.parse_args()

    if args.source == "-":
        raw = sys.stdin.read()
    else:
        path = Path(args.source)
        if not path.is_file():
            print(f"check_foundry_receipt: {path} is not a file", file=sys.stderr)
            return 2
        raw = path.read_text(encoding="utf-8")

    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"check_foundry_receipt: invalid JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(receipt, dict):
        print("check_foundry_receipt: receipt must be a JSON object", file=sys.stderr)
        return 2

    errors: list[str] = []
    validate(receipt, len(raw.encode("utf-8")), errors)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print("OK: receipt is valid and privacy-safe", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
