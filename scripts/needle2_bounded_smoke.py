#!/usr/bin/env python3
"""Run Needle 2 against the frozen public smoke fixtures without executing calls."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path


PACE_TO_TOOL = {
    "chitchat": None,
    "unknown": None,
    "pureKnowledge": "answer_knowledge",
    "research": "research_topic",
    "screenDescription": "describe_screen",
    "screenAction": "perform_screen_action",
    "phoneLargeModel": "route_to_phone_model",
}


def read_text_fixture(path: Path) -> str:
    for line in path.read_text().splitlines():
        if line.startswith("USER: "):
            return line.removeprefix("USER: ")
    raise ValueError(f"missing USER line: {path}")


def load_cases(root: Path) -> list[dict[str, object]]:
    pace = json.loads(
        (
            root / "evals/everyday-benchmark/fixtures/pace-intent-public-dev-v1.json"
        ).read_text()
    )
    file_ops = json.loads(
        (
            root / "evals/everyday-benchmark/fixtures/file-ops-public-dev-v1.json"
        ).read_text()
    )
    cases = [
        {
            "id": f"pace/{case['id']}",
            "input": case["input_text"],
            "slice": "pace-intent",
            "expected_tool": PACE_TO_TOOL[case["expected_label"]],
        }
        for case in pace["instances"]
    ]
    cases.extend(
        {
            "id": f"file-ops/{case['id']}",
            "input": case["input_text"],
            "slice": "file-ops",
            "expected_tool": "perform_file_operation",
        }
        for case in file_ops["instances"]
    )
    for directory, slice_name, expected_tool in (
        ("evals/fm-fixtures-ambig-h2", "ambiguity", "ask_clarification"),
        ("evals/fm-fixtures-oos-h2", "out-of-scope", None),
        (
            "evals/fm-fixtures-destructive-h2",
            "destructive",
            "confirm_destructive_action",
        ),
    ):
        for path in sorted((root / directory).glob("*.txt")):
            cases.append(
                {
                    "id": f"{slice_name}/{path.stem}",
                    "input": read_text_fixture(path),
                    "slice": slice_name,
                    "expected_tool": expected_tool,
                }
            )
    return cases


def load_catalog_routes(
    root: Path, routing_path: Path | None
) -> tuple[dict[str, tuple[str, Path, set[str]]], str | None]:
    default_path = root / "evals/needle2/tools-v1.json"
    if routing_path is None:
        allowed = {tool["name"] for tool in json.loads(default_path.read_text())}
        return {
            slice_name: ("general", default_path, allowed)
            for slice_name in (
                "pace-intent",
                "file-ops",
                "ambiguity",
                "out-of-scope",
                "destructive",
            )
        }, None

    manifest = json.loads(routing_path.read_text())
    catalogs = {}
    for name, relative_path in manifest["catalogs"].items():
        path = root / relative_path
        allowed = {tool["name"] for tool in json.loads(path.read_text())}
        catalogs[name] = (path, allowed)

    routes = {}
    for slice_name, catalog_name in manifest["slice_routes"].items():
        path, allowed = catalogs[catalog_name]
        routes[slice_name] = (catalog_name, path, allowed)
    return routes, str(routing_path.relative_to(root))


def complete(endpoint: str, prompt: str) -> tuple[dict[str, object], float]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"input": prompt}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.load(response)
    return payload, (time.perf_counter() - started) * 1000


def complete_one_shot(
    binary: Path, tools: Path, prompt: str
) -> tuple[dict[str, object], float]:
    started = time.perf_counter()
    process = subprocess.run(
        [str(binary), "--tools", str(tools), "--prompt", prompt, "--max", "128"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return json.loads(process.stdout), (time.perf_counter() - started) * 1000


def reset(endpoint: str) -> None:
    request = urllib.request.Request(
        endpoint.removesuffix("/complete") + "/reset",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/complete")
    parser.add_argument("--binary", type=Path)
    parser.add_argument(
        "--catalog-routing",
        type=Path,
        help="Versioned manifest that maps public fixture families to catalogs.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()

    catalog_routes, routing_ref = load_catalog_routes(args.root, args.catalog_routing)
    results = []
    for case in load_cases(args.root):
        catalog_name, tools_path, allowed_tools = catalog_routes[str(case["slice"])]
        if args.binary:
            response, latency_ms = complete_one_shot(
                args.binary, tools_path, str(case["input"])
            )
        else:
            reset(args.endpoint)
            response, latency_ms = complete(args.endpoint, str(case["input"]))
        calls = response.get("function_calls")
        schema_valid = isinstance(calls, list) and all(
            isinstance(call, dict)
            and call.get("name") in allowed_tools
            and isinstance(call.get("arguments"), dict)
            for call in calls
        )
        names = [call["name"] for call in calls] if schema_valid else []
        expected = case["expected_tool"]
        exact = schema_valid and (
            names == [] if expected is None else names == [expected]
        )
        results.append(
            {
                **case,
                "catalog": catalog_name,
                "predicted_tools": names,
                "schema_valid": schema_valid,
                "exact": exact,
                "confidence": response.get("confidence"),
                "peak_ram_mb": response.get("peak_ram_mb"),
                "prefill_tps": response.get("prefill_tps"),
                "decode_tps": response.get("decode_tps"),
                "latency_ms": round(latency_ms, 3),
                "error": response.get("error"),
            }
        )

    latencies = [float(row["latency_ms"]) for row in results]
    by_slice = {}
    for slice_name in sorted({str(row["slice"]) for row in results}):
        subset = [row for row in results if row["slice"] == slice_name]
        by_slice[slice_name] = {
            "cases": len(subset),
            "exact": sum(bool(row["exact"]) for row in subset),
            "exact_rate": sum(bool(row["exact"]) for row in subset) / len(subset),
        }
    by_catalog = {}
    for catalog_name in sorted({str(row["catalog"]) for row in results}):
        subset = [row for row in results if row["catalog"] == catalog_name]
        by_catalog[catalog_name] = {
            "cases": len(subset),
            "exact": sum(bool(row["exact"]) for row in subset),
            "exact_rate": sum(bool(row["exact"]) for row in subset) / len(subset),
        }
    output = {
        "catalog_routing": routing_ref,
        "cases": len(results),
        "schema_validity": sum(bool(row["schema_valid"]) for row in results)
        / len(results),
        "tool_selection_exact": sum(bool(row["exact"]) for row in results)
        / len(results),
        "out_of_scope_false_action_count": sum(
            bool(row["predicted_tools"])
            for row in results
            if row["slice"] == "out-of-scope"
        ),
        "destructive_unconfirmed_action_count": sum(
            any(name != "confirm_destructive_action" for name in row["predicted_tools"])
            for row in results
            if row["slice"] == "destructive"
        ),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 3),
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "max": round(max(latencies), 3),
        },
        "by_slice": by_slice,
        "by_catalog": by_catalog,
        "results": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
