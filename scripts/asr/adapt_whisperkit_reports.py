#!/usr/bin/env python3
"""Convert pinned WhisperKit JSON reports into the shared ASR prediction schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def adapt(
    fixture: dict[str, Any], raw_receipt: dict[str, Any], report_dir: Path
) -> dict[str, Any]:
    reports = {path.stem: path for path in report_dir.glob("*.json")}
    expected = {item["id"] for item in fixture["items"]}
    if reports.keys() != expected:
        missing = sorted(expected - reports.keys())
        extra = sorted(reports.keys() - expected)
        raise ValueError(
            f"WhisperKit reports do not match fixture; missing={missing}, extra={extra}"
        )
    transcripts = []
    for item in fixture["items"]:
        report = json.loads(reports[item["id"]].read_text(encoding="utf-8"))
        timings = report["timings"]
        audio_seconds = float(timings["inputAudioSeconds"])
        decode_ms = float(timings["fullPipeline"]) * 1000
        if abs(audio_seconds - float(item["audio_seconds"])) > 0.05:
            raise ValueError(f"{item['id']}: WhisperKit audio duration drifted")
        if decode_ms <= 0:
            raise ValueError(f"{item['id']}: WhisperKit fullPipeline must be positive")
        transcripts.append(
            {
                "id": item["id"],
                "text": report["text"],
                "audio_seconds": audio_seconds,
                "decode_ms": decode_ms,
                "engine_metrics": timings,
            }
        )
    return {
        "schema_version": "posttrainllm.asr-predictions.v1",
        "fixture_id": fixture["fixture_id"],
        "model_id": raw_receipt["model_id"],
        "model_revision": raw_receipt["model_revision"],
        "execution_seed": raw_receipt["execution_seed"],
        "execution_order": raw_receipt["execution_order"],
        "transcripts": transcripts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--raw-receipt", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        raw_receipt = json.loads(args.raw_receipt.read_text(encoding="utf-8"))
        result = adapt(fixture, raw_receipt, args.report_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"adapt-whisperkit: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
