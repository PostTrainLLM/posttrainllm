#!/usr/bin/env python3
"""Compile public Lichess evaluations into deterministic Character Chess SFT rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from typing import Any, TextIO

import chess

import chess_benchmark as benchmark

CONFIG_SCHEMA = "chess/lichess-eval-corpus-config/v1"
ROW_SCHEMA = "chess/character-sft-row/v1"
MANIFEST_SCHEMA = "chess/character-sft-manifest/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--input", required=True, help="Decompressed JSONL path, or - for stdin"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported chess corpus config")
    if set(config) != {
        "schema_version",
        "config_id",
        "status",
        "source",
        "selection",
        "split",
        "encoding",
    }:
        raise ValueError("chess corpus config fields are incomplete")
    source = config["source"]
    selection = config["selection"]
    split = config["split"]
    encoding = config["encoding"]
    if source.get("license") != "CC0-1.0":
        raise ValueError("Lichess evaluation corpus must retain its CC0 declaration")
    if (
        encoding.get("schema_version") != ROW_SCHEMA
        or encoding.get("vocabulary") != "bytes-0-through-255"
    ):
        raise ValueError("unsupported character corpus encoding")
    for key in ("minimum_depth", "minimum_knodes"):
        if not isinstance(selection.get(key), int) or selection[key] < 0:
            raise ValueError(f"selection.{key} must be a non-negative integer")
    maximum = selection.get("maximum_rows")
    if maximum is not None and (not isinstance(maximum, int) or maximum < 1):
        raise ValueError("selection.maximum_rows must be null or a positive integer")
    required_split = {
        "seed",
        "modulus",
        "validation_bucket_start",
        "validation_bucket_end",
        "test_bucket_start",
        "test_bucket_end",
    }
    if set(split) != required_split or any(
        not isinstance(split[key], int) for key in required_split
    ):
        raise ValueError("split config fields are incomplete")
    modulus = split["modulus"]
    ranges = (
        split["validation_bucket_start"],
        split["validation_bucket_end"],
        split["test_bucket_start"],
        split["test_bucket_end"],
    )
    if not (
        modulus > 1 and 0 <= ranges[0] <= ranges[1] < ranges[2] <= ranges[3] < modulus
    ):
        raise ValueError(
            "split bucket ranges must be ordered, disjoint, and inside modulus"
        )
    expected = source.get("expected_sha256")
    if expected is not None and (not isinstance(expected, str) or len(expected) != 64):
        raise ValueError("source expected_sha256 must be null or a 64-character digest")
    return config


def canonical_fen(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError("missing-fen")
    fields = raw.split()
    if len(fields) == 4:
        raw = f"{raw} 0 1"
    elif len(fields) != 6:
        raise ValueError("fen-field-count")
    return benchmark.normalized_fen(raw)


def choose_evaluation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing-evaluations")
    candidates = [row for row in raw if isinstance(row, dict)]
    if not candidates:
        raise ValueError("malformed-evaluations")
    try:
        return max(
            candidates,
            key=lambda row: (int(row.get("depth", -1)), int(row.get("knodes", -1))),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("malformed-evaluation-depth") from exc


def extract_label(document: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    fen = canonical_fen(document.get("fen"))
    board = chess.Board(fen)
    evaluation = choose_evaluation(document.get("evals"))
    depth = evaluation.get("depth")
    knodes = evaluation.get("knodes")
    if not isinstance(depth, int) or isinstance(depth, bool):
        raise ValueError("malformed-depth")
    if not isinstance(knodes, int) or isinstance(knodes, bool):
        raise ValueError("malformed-knodes")
    if depth < config["selection"]["minimum_depth"]:
        raise ValueError("below-minimum-depth")
    if knodes < config["selection"]["minimum_knodes"]:
        raise ValueError("below-minimum-knodes")
    pvs = evaluation.get("pvs")
    if not isinstance(pvs, list) or not pvs or not isinstance(pvs[0], dict):
        raise ValueError("missing-principal-variation")
    line = pvs[0].get("line")
    if not isinstance(line, str) or not line.split():
        raise ValueError("empty-principal-variation")
    move_text = line.split()[0].lower()
    move = benchmark.parse_strict_uci(move_text, board).uci()
    if "cp" in pvs[0] and isinstance(pvs[0]["cp"], int):
        score = {"kind": "cp", "value": pvs[0]["cp"]}
    elif "mate" in pvs[0] and isinstance(pvs[0]["mate"], int):
        score = {"kind": "mate", "value": pvs[0]["mate"]}
    else:
        raise ValueError("missing-evaluation-score")
    return {"fen": fen, "move": move, "depth": depth, "knodes": knodes, "score": score}


def split_for_fen(fen: str, config: dict[str, Any]) -> tuple[str, int]:
    split = config["split"]
    digest = hashlib.sha256(f"{split['seed']}:{fen}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") % split["modulus"]
    if split["validation_bucket_start"] <= bucket <= split["validation_bucket_end"]:
        return "validation", bucket
    if split["test_bucket_start"] <= bucket <= split["test_bucket_end"]:
        return "test", bucket
    return "train", bucket


def compact_prompt(fen: str) -> str:
    board = chess.Board(fen)
    ply = (board.fullmove_number - 1) * 2 + (0 if board.turn == chess.WHITE else 1)
    return f"FEN={fen};PLY={ply};MOVE="


def make_row(label: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    split, bucket = split_for_fen(label["fen"], config)
    row = {
        "schema_version": ROW_SCHEMA,
        "id": f"lichess-eval-{hashlib.sha256(label['fen'].encode('utf-8')).hexdigest()[:20]}",
        "split": split,
        "split_bucket": bucket,
        "input": compact_prompt(label["fen"]),
        "target": label["move"],
        "fen": label["fen"],
        "legal_moves": list(benchmark.legal_uci(chess.Board(label["fen"]))),
        "source": {
            "dataset": "lichess-evaluations",
            "depth": label["depth"],
            "knodes": label["knodes"],
            "score": label["score"],
        },
    }
    row["row_hash"] = benchmark.sha256_json(row)
    return row


def _input_context(input_path: str):
    if input_path == "-":
        return nullcontext(sys.stdin)
    return Path(input_path).open("r", encoding="utf-8")


def compile_corpus(
    config: dict[str, Any], input_path: str, output: TextIO
) -> dict[str, Any]:
    source_hash = hashlib.sha256()
    output_hash = hashlib.sha256()
    counts: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    seen: set[str] = set()
    maximum = config["selection"]["maximum_rows"]
    source_exhausted = True
    with _input_context(input_path) as source:
        for line_number, raw_line in enumerate(source, 1):
            encoded = raw_line.encode("utf-8")
            source_hash.update(encoded)
            counts["lines_read"] += 1
            if not raw_line.strip():
                rejected["blank-line"] += 1
                continue
            try:
                document = json.loads(raw_line)
                if not isinstance(document, dict):
                    raise ValueError("non-object-row")
                label = extract_label(document, config)
                if label["fen"] in seen:
                    raise ValueError("duplicate-position")
                row = make_row(label, config)
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                reason = (
                    "malformed-json"
                    if isinstance(exc, json.JSONDecodeError)
                    else str(exc)
                )
                rejected[reason] += 1
                continue
            seen.add(label["fen"])
            rendered = (
                json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
                + "\n"
            )
            output.write(rendered)
            output_hash.update(rendered.encode("utf-8"))
            counts["accepted"] += 1
            splits[row["split"]] += 1
            if maximum is not None and counts["accepted"] >= maximum:
                source_exhausted = False
                break
    observed_source_hash = source_hash.hexdigest()
    expected = config["source"].get("expected_sha256")
    if expected is not None and source_exhausted and observed_source_hash != expected:
        raise ValueError("source SHA-256 does not match frozen config")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "config_id": config["config_id"],
        "config_hash": benchmark.sha256_json(config),
        "source": {
            **config["source"],
            "input": input_path,
            "consumed_sha256": observed_source_hash,
            "exhausted": source_exhausted,
        },
        "counts": {
            "lines_read": counts["lines_read"],
            "accepted": counts["accepted"],
            "rejected": sum(rejected.values()),
            "splits": {name: splits[name] for name in ("train", "validation", "test")},
            "rejection_reasons": dict(sorted(rejected.items())),
        },
        "output_sha256": output_hash.hexdigest(),
    }


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.output.resolve() == args.manifest.resolve():
        raise ValueError("output and manifest paths must differ")
    for target in (args.output, args.manifest):
        if target.exists():
            raise ValueError(f"refusing to overwrite {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
    output_tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.output.parent, delete=False
    )
    manifest_tmp = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=args.manifest.parent, delete=False
    )
    try:
        with output_tmp as handle:
            manifest = compile_corpus(config, args.input, handle)
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
    print(
        json.dumps(
            {
                "output": str(args.output),
                "manifest": str(args.manifest),
                **manifest["counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
