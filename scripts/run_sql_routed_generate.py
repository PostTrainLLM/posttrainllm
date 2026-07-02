#!/usr/bin/env python3
"""Route SQL prompts to specialist adapters and recombine predictions.

Static adapter composition traded off public SQL exact match against local
execution accuracy. This runner keeps adapters separate and chooses one per row:

- public/schema-only rows -> public text-to-SQL adapter
- local execution rows with SQLite DBs -> synthetic/execution adapter
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    confidence: float


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
        + ("\n" if rows else "")
    )


def route_for(row: dict, default: str, trust_route_field: bool = False) -> RouteDecision:
    if trust_route_field and row.get("route") in {"public", "synthetic"}:
        return RouteDecision(row["route"], "trusted_route_field", 1.0)
    if row.get("db"):
        return RouteDecision("synthetic", "sqlite_db_field", 0.99)
    if row.get("source") == "b-mc2/sql-create-context":
        return RouteDecision("public", "known_public_source", 0.99)

    schema = str(row.get("schema") or "")
    prompt = str(row.get("prompt") or "")
    text = f"{schema}\n{prompt}".lower()
    if "create table" in text and not row.get("db"):
        return RouteDecision("public", "create_table_schema_without_db", 0.95)
    if "schema:" in text and ";" in text and any(
        field in row for field in ("domain", "gold_sql", "question")
    ):
        return RouteDecision("synthetic", "compact_schema_prompt", 0.65)
    return RouteDecision(default, "default_route", 0.25)


def run_generate(
    tinygpt: str,
    base: str,
    lora: str,
    data: Path,
    out: Path,
    port: int,
    max_tokens: int,
) -> None:
    cmd = [
        tinygpt,
        "generate",
        base,
        "--lora",
        lora,
        "--data",
        str(data),
        "--out",
        str(out),
        "--out-field",
        "predicted_sql",
        "--max-tokens",
        str(max_tokens),
        "--serve-port",
        str(port),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tinygpt", default="native-mac/.build/debug/tinygpt")
    p.add_argument("--base")
    p.add_argument("--input", required=True)
    p.add_argument("--out")
    p.add_argument("--public-lora")
    p.add_argument("--synthetic-lora")
    p.add_argument("--default-route", choices=["public", "synthetic"], default="public")
    p.add_argument("--trust-route-field", action="store_true")
    p.add_argument("--routes-out")
    p.add_argument("--route-only", action="store_true")
    p.add_argument("--start-port", type=int, default=8160)
    p.add_argument("--max-tokens", type=int, default=96)
    args = p.parse_args()
    if not args.route_only:
        missing = [
            name
            for name in ("base", "out", "public_lora", "synthetic_lora")
            if not getattr(args, name)
        ]
        if missing:
            p.error("missing required generation args: " + ", ".join(f"--{m.replace('_', '-')}" for m in missing))

    rows = read_jsonl(Path(args.input))
    buckets = {"public": [], "synthetic": []}
    route_decisions = []
    for idx, row in enumerate(rows):
        routed = dict(row)
        decision = route_for(routed, args.default_route, args.trust_route_field)
        route = decision.route
        routed["_route_index"] = idx
        routed["_route"] = route
        routed["_route_reason"] = decision.reason
        routed["_route_confidence"] = decision.confidence
        buckets[route].append(routed)
        route_decisions.append(
            {
                "index": idx,
                "id": row.get("id", idx),
                "expected_route": row.get("route"),
                **asdict(decision),
            }
        )

    route_counts = dict(collections.Counter(d["route"] for d in route_decisions))
    if args.routes_out:
        write_jsonl(Path(args.routes_out), route_decisions)
    if args.route_only:
        print(f"routed-generate: route-only {len(rows)} rows {route_counts}")
        return

    with tempfile.TemporaryDirectory(prefix="tinygpt-sql-route-") as td:
        tmp = Path(td)
        outputs: dict[int, dict] = {}
        for offset, route in enumerate(["public", "synthetic"]):
            if not buckets[route]:
                continue
            in_path = tmp / f"{route}.jsonl"
            out_path = tmp / f"{route}-preds.jsonl"
            write_jsonl(in_path, buckets[route])
            lora = args.public_lora if route == "public" else args.synthetic_lora
            run_generate(
                args.tinygpt,
                str(args.base),
                lora,
                in_path,
                out_path,
                args.start_port + offset,
                args.max_tokens,
            )
            for pred in read_jsonl(out_path):
                idx = int(pred.pop("_route_index"))
                pred["_route"] = route
                pred["_route_reason"] = route_for(pred, args.default_route, args.trust_route_field).reason
                outputs[idx] = pred

    merged = [outputs[i] for i in range(len(rows))]
    write_jsonl(Path(args.out), merged)
    print(f"routed-generate: wrote {len(merged)} rows to {args.out} {route_counts}")


if __name__ == "__main__":
    main()
