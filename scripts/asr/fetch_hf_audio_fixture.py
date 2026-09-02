#!/usr/bin/env python3
"""Fetch and verify the audio rows declared by an ASR reference fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://datasets-server.huggingface.co/rows"
MAX_BYTES = 1 << 30
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def validate_item(item: dict[str, Any], allow_unpinned: bool) -> tuple[int, float]:
    digest = item.get("audio_sha256")
    if digest is None and allow_unpinned:
        pass
    elif not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise ValueError(f"{item['id']}: audio_sha256 is not frozen")
    audio_bytes = int(item["audio_bytes"])
    audio_seconds = float(item["audio_seconds"])
    if audio_bytes <= 0 or audio_seconds <= 0:
        raise ValueError(f"{item['id']}: audio metadata must be positive")
    return audio_bytes, audio_seconds


def validate_fixture(fixture: dict[str, Any], allow_unpinned: bool = False) -> None:
    items = fixture["items"]
    if not items:
        raise ValueError("fixture contains no items")
    ids = [item["id"] for item in items]
    offsets = [item["row_index"] for item in items]
    if len(ids) != len(set(ids)) or len(offsets) != len(set(offsets)):
        raise ValueError("fixture ids and row offsets must be unique")
    measurements = [validate_item(item, allow_unpinned) for item in items]
    total_bytes = sum(item[0] for item in measurements)
    total_seconds = sum(item[1] for item in measurements)
    if total_bytes > MAX_BYTES:
        raise ValueError("fixture declares more than 1 GiB of audio")
    source = fixture["source"]
    if total_bytes != int(source["total_audio_bytes"]):
        raise ValueError("fixture byte total does not match item metadata")
    if abs(total_seconds - float(source["total_audio_seconds"])) > 1e-6:
        raise ValueError("fixture duration total does not match item metadata")


def get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "posttrainllm-fixture/1"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def download(url: str, path: Path) -> tuple[int, str]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "posttrainllm-fixture/1"}
    )
    digest = hashlib.sha256()
    size = 0
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        path.open("wb") as handle,
    ):
        while chunk := response.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("fixture download exceeded 1 GiB")
            digest.update(chunk)
            handle.write(chunk)
    return size, digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--allow-unpinned", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        validate_fixture(fixture, allow_unpinned=args.allow_unpinned)
        source = fixture["source"]
        args.out.mkdir(parents=True, exist_ok=True)
        observed = []
        total_bytes = 0
        for item in fixture["items"]:
            query = urllib.parse.urlencode(
                {
                    "dataset": source["dataset"],
                    "config": source["config"],
                    "split": source["split"],
                    "offset": item["row_index"],
                    "length": 1,
                }
            )
            payload = get_json(f"{BASE_URL}?{query}")
            row = payload["rows"][0]["row"]
            if row["id"] != item["id"] or row["text"] != item["reference"]:
                raise ValueError(f"{item['id']}: Dataset Viewer row identity drifted")
            audio = row["audio"]
            source_url = audio[0]["src"] if isinstance(audio, list) else audio["src"]
            target = args.out / f"{item['id']}.flac"
            size, digest = download(source_url, target)
            total_bytes += size
            expected = item.get("audio_sha256")
            if expected is None and not args.allow_unpinned:
                raise ValueError(f"{item['id']}: audio_sha256 is not frozen")
            if expected is not None and digest != expected:
                raise ValueError(f"{item['id']}: audio SHA-256 mismatch")
            observed.append(
                {"id": item["id"], "path": str(target), "bytes": size, "sha256": digest}
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        urllib.error.URLError,
    ) as exc:
        print(f"fetch-asr-fixture: {exc}", file=sys.stderr)
        return 1
    receipt = {
        "schema_version": "posttrainllm.asr-fixture-fetch.v1",
        "fixture_id": fixture["fixture_id"],
        "total_bytes": total_bytes,
        "items": observed,
    }
    rendered = f"{json.dumps(receipt, indent=2)}\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
