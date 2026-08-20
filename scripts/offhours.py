#!/usr/bin/env python3
"""CLI for the local OffHours context-interference benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import offhours_analysis as analysis
import offhours_core as core
import offhours_store as store


def default_database(bundle: dict[str, Any]) -> Path:
    return (
        core.ROOT / bundle["config"]["artifacts"]["local_run_root"] / "offhours.sqlite"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OffHours local context-interference benchmark"
    )
    parser.add_argument("--config", type=Path, default=core.DEFAULT_CONFIG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate frozen pilot contracts")

    plan = subparsers.add_parser("plan", help="print a deterministic paired-day plan")
    plan.add_argument("--days", type=int, default=5)
    plan.add_argument("--tasks-per-day", type=int, default=40)
    plan.add_argument("--seed", type=int, default=42)

    run = subparsers.add_parser("run", help="execute or resume a local model run")
    run.add_argument(
        "--condition",
        action="append",
        choices=("clean", "filler", "neutral", "benign", "moderate", "crisis"),
    )
    run.add_argument("--days", type=int, default=5)
    run.add_argument("--tasks-per-day", type=int, default=40)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--run-id")
    run.add_argument("--db", type=Path)
    run.add_argument("--endpoint")
    run.add_argument("--api-key-env")
    run.add_argument("--model-file")
    run.add_argument("--quantization")
    run.add_argument("--server-name")
    run.add_argument("--server-version")

    status = subparsers.add_parser("status", help="show resumable run status")
    status.add_argument("--run-id", required=True)
    status.add_argument("--db", type=Path)

    analyze = subparsers.add_parser(
        "analyze", help="write aggregate JSON and Markdown reports"
    )
    analyze.add_argument("--run-id", required=True)
    analyze.add_argument("--db", type=Path)
    analyze.add_argument("--json-out", type=Path, required=True)
    analyze.add_argument("--markdown-out", type=Path, required=True)
    analyze.add_argument("--force", action="store_true")

    export = subparsers.add_parser(
        "export", help="export deterministic turn-level JSONL"
    )
    export.add_argument("--run-id", required=True)
    export.add_argument("--db", type=Path)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--force", action="store_true")
    return parser


def generated_run_id(seed: int) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"offhours-{timestamp}-s{seed}"


def command_run(args: argparse.Namespace, bundle: dict[str, Any]) -> dict[str, Any]:
    minimum = bundle["config"]["workload"]["days_per_condition_min"]
    if args.days < minimum:
        raise ValueError(
            f"measured pilot runs require at least {minimum} days per condition"
        )
    configured_conditions = [item["id"] for item in bundle["config"]["conditions"]]
    requested_conditions = set(args.condition or configured_conditions)
    conditions = [
        name for name in configured_conditions if name in requested_conditions
    ]
    run_id = args.run_id or generated_run_id(args.seed)
    database_path = (args.db or default_database(bundle)).resolve()
    overrides = {
        "base_url": args.endpoint,
        "api_key_env": args.api_key_env,
        "model_file": args.model_file,
        "quantization": args.quantization,
        "server_name": args.server_name,
        "server_version": args.server_version,
    }
    provenance = store.build_provenance(bundle, overrides)
    model_config = json.loads(json.dumps(bundle["config"]["model"]))
    if args.endpoint:
        model_config["base_url"] = args.endpoint
    client = core.OpenAICompatibleClient(
        model_config, base_url=args.endpoint, api_key_env=args.api_key_env
    )
    database = store.connect(database_path)
    try:
        store.prepare_run(
            database,
            bundle,
            store.RunSpec(
                run_id=run_id,
                days=args.days,
                tasks_per_day=args.tasks_per_day,
                seed=args.seed,
                conditions=conditions,
                provenance=provenance,
            ),
        )
        summary = store.execute_run(database, bundle, run_id, client)
    finally:
        database.close()
    return {**summary, "database": str(database_path)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        bundle = core.load_bundle(args.config)
        validation = core.validate_bundle(bundle)
        if args.command == "validate":
            result: Any = validation
        elif args.command == "plan":
            result = core.build_plan(bundle, args.days, args.tasks_per_day, args.seed)
        elif args.command == "run":
            result = command_run(args, bundle)
        else:
            database_path = (args.db or default_database(bundle)).resolve()
            database = store.connect(database_path)
            try:
                if args.command == "status":
                    result = store.run_summary(database, args.run_id)
                elif args.command == "analyze":
                    result = analysis.analyze(database, bundle, args.run_id)
                    analysis.write_report(
                        result, args.json_out, args.markdown_out, force=args.force
                    )
                    result = {
                        "run_id": args.run_id,
                        "json": str(args.json_out),
                        "markdown": str(args.markdown_out),
                    }
                else:
                    rows = store.export_jsonl(
                        database, args.run_id, args.out, force=args.force
                    )
                    result = {
                        "run_id": args.run_id,
                        "rows": rows,
                        "output": str(args.out),
                    }
            finally:
                database.close()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        print(f"offhours: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
