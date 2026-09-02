#!/usr/bin/env python3
"""Apply the frozen browser-vs-native ASR promotion gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def compare(
    native: dict[str, Any], browser: dict[str, Any], browser_raw: dict[str, Any]
) -> dict[str, Any]:
    native_summary = native["summary"]
    browser_summary = browser["summary"]
    wer_delta_points = 100 * (browser_summary["wer"] - native_summary["wer"])
    gates = {
        "wer_delta_points": {
            "value": wer_delta_points,
            "maximum": 2.0,
            "passed": wer_delta_points <= 2.0,
        },
        "warm_realtime_factor": {
            "value": browser_summary["median_realtime_factor"],
            "minimum": 50.0,
            "passed": browser_summary["median_realtime_factor"] >= 50.0,
        },
        "repetition_regression": {
            "browser_events": browser_summary["hypothesis_repetition_events"],
            "native_events": native_summary["hypothesis_repetition_events"],
            "passed": browser_summary["hypothesis_repetition_events"]
            <= native_summary["hypothesis_repetition_events"],
        },
        "offline_warm_requests": {
            "value": len(browser_raw["external_warm_requests"]),
            "maximum": 0,
            "passed": not browser_raw["external_warm_requests"],
        },
    }
    return {
        "schema_version": "posttrainllm.parakeet-native-comparison.v1",
        "manifest_id": "parakeet-browser-native-paired-v1",
        "native": native_summary,
        "browser": browser_summary,
        "proper_noun_accuracy_delta": browser_summary["proper_noun_accuracy"]
        - native_summary["proper_noun_accuracy"],
        "model_download_bytes": browser_raw["model_download_bytes"],
        "adapter": browser_raw["adapter"],
        "gates": gates,
        "decision": "promote"
        if all(gate["passed"] for gate in gates.values())
        else "reject",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-score", required=True, type=Path)
    parser.add_argument("--browser-score", required=True, type=Path)
    parser.add_argument("--browser-raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        native = json.loads(args.native_score.read_text(encoding="utf-8"))
        browser = json.loads(args.browser_score.read_text(encoding="utf-8"))
        browser_raw = json.loads(args.browser_raw.read_text(encoding="utf-8"))
        result = compare(native, browser, browser_raw)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"compare-asr: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
