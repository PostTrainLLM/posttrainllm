#!/usr/bin/env python3
"""Render one compiled Character Chess split as Python-reference training text."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, TextIO

import chess_benchmark as benchmark
import chess_sft_corpus as corpus

MANIFEST_SCHEMA = "chess/character-training-text-manifest/v1"
SPLITS = ("train", "validation", "test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--split", choices=SPLITS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--maximum-rows", type=int)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--context-length", type=int, default=512)
    return parser.parse_args()


def _validated_sequence(row: Any, split: str, context_length: int) -> str | None:
    if not isinstance(row, dict) or row.get("schema_version") != corpus.ROW_SCHEMA:
        raise ValueError("unsupported compiled chess row")
    row_without_hash = {key: value for key, value in row.items() if key != "row_hash"}
    if row.get("row_hash") != benchmark.sha256_json(row_without_hash):
        raise ValueError("compiled chess row hash mismatch")
    if row.get("split") != split:
        return None
    target = row.get("target")
    legal_moves = row.get("legal_moves")
    prompt = row.get("input")
    if not isinstance(prompt, str) or not isinstance(target, str) or not isinstance(legal_moves, list):
        raise ValueError("compiled chess row fields are incomplete")
    if target not in legal_moves:
        raise ValueError("compiled chess target is not legal")
    sequence = f"{prompt}{target}\n"
    if len(sequence.encode("utf-8")) > context_length:
        raise ValueError("compiled chess sequence exceeds model context")
    return sequence


def render_training_text(
    input_path: Path,
    output: TextIO,
    *,
    split: str,
    maximum_rows: int | None,
    repeat: int,
    context_length: int,
) -> dict[str, Any]:
    if split not in SPLITS:
        raise ValueError("unsupported split")
    if maximum_rows is not None and maximum_rows < 1:
        raise ValueError("maximum_rows must be positive")
    if repeat < 1:
        raise ValueError("repeat must be positive")
    if repeat > 1 and (maximum_rows is None or maximum_rows > 10_000):
        raise ValueError("repeated rendering requires a bounded maximum_rows at most 10000")
    if context_length < 8:
        raise ValueError("context_length is too small")

    source_hash = hashlib.sha256()
    output_hash = hashlib.sha256()
    selected: list[str] = []
    selected_count = 0
    source_exhausted = True
    with input_path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            source_hash.update(raw_line.encode("utf-8"))
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            sequence = _validated_sequence(row, split, context_length)
            if sequence is None:
                continue
            if repeat == 1:
                output.write(sequence)
                output_hash.update(sequence.encode("utf-8"))
            else:
                selected.append(sequence)
            selected_count += 1
            if maximum_rows is not None and selected_count >= maximum_rows:
                source_exhausted = False
                break

    if repeat > 1:
        for _ in range(repeat):
            for sequence in selected:
                output.write(sequence)
                output_hash.update(sequence.encode("utf-8"))
    return {
        "schema_version": MANIFEST_SCHEMA,
        "source_consumed_sha256": source_hash.hexdigest(),
        "source_exhausted": source_exhausted,
        "split": split,
        "unique_rows": selected_count,
        "repeat": repeat,
        "rendered_sequences": selected_count * repeat,
        "context_length": context_length,
        "output_sha256": output_hash.hexdigest(),
    }


def main() -> int:
    args = parse_args()
    if args.output.resolve() == args.manifest.resolve():
        raise ValueError("output and manifest paths must differ")
    for target in (args.output, args.manifest):
        if target.exists():
            raise ValueError(f"refusing to overwrite {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
    output_tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False)
    manifest_tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.manifest.parent, delete=False)
    try:
        with output_tmp as handle:
            manifest = render_training_text(
                args.input,
                handle,
                split=args.split,
                maximum_rows=args.maximum_rows,
                repeat=args.repeat,
                context_length=args.context_length,
            )
        with manifest_tmp as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(output_tmp.name, args.output)
        os.replace(manifest_tmp.name, args.manifest)
    except Exception:
        for name in (output_tmp.name, manifest_tmp.name):
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass
        raise
    print(json.dumps({"output": str(args.output), "manifest": str(args.manifest), **manifest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
