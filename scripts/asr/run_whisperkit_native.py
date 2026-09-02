#!/usr/bin/env python3
"""Run a pinned local WhisperKit CLI once on the frozen paired ASR fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def mulberry32(seed: int):
    state = seed & 0xFFFFFFFF

    def random() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        value = state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFFFFFF
        value ^= (
            value + (((value ^ (value >> 7)) * (value | 61)) & 0xFFFFFFFF)
        ) & 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 4294967296

    return random


def shuffled(items: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    result = list(items)
    random = mulberry32(seed)
    for index in range(len(result) - 1, 0, -1):
        swap = int(random() * (index + 1))
        result[index], result[swap] = result[swap], result[index]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--audio-dir", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--cli-version", required=True)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--generation-config-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        observed_version = subprocess.run(
            [args.cli, "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if observed_version != args.cli_version:
            raise ValueError(f"WhisperKit CLI version mismatch: {observed_version}")
        metadata = (
            args.model_path.parent
            / ".cache/huggingface/download"
            / args.model_path.name
            / "config.json.metadata"
        )
        observed_revision = metadata.read_text(encoding="utf-8").splitlines()[0]
        if observed_revision != args.model_revision:
            raise ValueError(f"native model revision mismatch: {observed_revision}")
        if sha256(args.model_path / "config.json") != args.config_sha256:
            raise ValueError("native config SHA-256 mismatch")
        if (
            sha256(args.model_path / "generation_config.json")
            != args.generation_config_sha256
        ):
            raise ValueError("native generation config SHA-256 mismatch")

        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        seed = int(fixture.get("execution_seed", 13802))
        items = shuffled(fixture["items"], seed)
        audio_paths = []
        for item in items:
            audio_path = args.audio_dir / f"{item['id']}.flac"
            if sha256(audio_path) != item["audio_sha256"]:
                raise ValueError(f"{item['id']}: audio SHA-256 mismatch")
            audio_paths.append(audio_path)
        args.report_dir.mkdir(parents=True, exist_ok=False)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)

        command = [str(args.cli), "transcribe"]
        for audio_path in audio_paths:
            command.extend(["--audio-path", str(audio_path)])
        command.extend(
            [
                "--model-path",
                str(args.model_path),
                "--language",
                "en",
                "--without-timestamps",
                "--skip-special-tokens",
                "--report",
                "--report-path",
                str(args.report_dir),
                "--concurrent-worker-count",
                "1",
                "--chunking-strategy",
                "none",
                "--audio-encoder-compute-units",
                "cpuAndNeuralEngine",
                "--text-decoder-compute-units",
                "cpuAndNeuralEngine",
                "--verbose",
            ]
        )
        started = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True)
        elapsed = time.monotonic() - started
        receipt = {
            "schema_version": "posttrainllm.whisperkit-raw.v1",
            "fixture_id": fixture["fixture_id"],
            "model_id": "openai-whisper-large-v3-turbo-whisperkit-coreml",
            "model_revision": (
                f"whisperkit-cli={args.cli_version}; model={args.model_revision}; "
                f"config={args.config_sha256}; generation_config="
                f"{args.generation_config_sha256}"
            ),
            "execution_seed": seed,
            "execution_order": [item["id"] for item in items],
            "command": command,
            "elapsed_seconds": elapsed,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "report_dir": str(args.report_dir),
            "report_files": sorted(path.name for path in args.report_dir.iterdir()),
        }
        args.receipt.write_text(f"{json.dumps(receipt, indent=2)}\n", encoding="utf-8")
        if completed.returncode:
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        print(json.dumps(receipt, indent=2))
        return 0
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"run-whisperkit-native: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
