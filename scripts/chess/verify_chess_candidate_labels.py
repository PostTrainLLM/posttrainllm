#!/usr/bin/env python3
"""Deep Stockfish verification for a deterministic Chess candidate pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path
from typing import Any, Sequence

import chess
import chess.engine

import chess_benchmark as benchmark

REPORT_SCHEMA = "chess/deep-label-report/v1"
CONFIG_SCHEMA = "chess/deep-label-verification/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exclude-suite", type=Path, required=True)
    parser.add_argument("--engine", default="stockfish")
    parser.add_argument("--output-suite", type=Path, required=True)
    parser.add_argument("--output-slice", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported deep-label verification config")
    depths = config.get("verification_depths")
    if (
        not isinstance(depths, list)
        or len(depths) != 2
        or any(not isinstance(value, int) for value in depths)
    ):
        raise ValueError("verification depths must contain exactly two integers")
    if depths != sorted(set(depths)) or depths[0] < 1:
        raise ValueError("verification depths must be unique and increasing")
    if not isinstance(config.get("multipv"), int) or config["multipv"] < 2:
        raise ValueError("multipv must be at least two")
    if (
        not isinstance(config.get("minimum_final_gap_cp"), int)
        or config["minimum_final_gap_cp"] < 0
    ):
        raise ValueError("minimum final gap must be a non-negative integer")
    if (
        not isinstance(config.get("verification_slice_count"), int)
        or config["verification_slice_count"] < 1
    ):
        raise ValueError("verification slice count must be positive")
    return config


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_score(info: dict[str, Any], turn: chess.Color, mate_score: int) -> int:
    return info["score"].pov(turn).score(mate_score=mate_score)


def pv_is_legal(board: chess.Board, pv: Sequence[chess.Move]) -> bool:
    replay = board.copy(stack=False)
    for move in pv:
        if move not in replay.legal_moves:
            return False
        replay.push(move)
    return True


def summarize_analysis(
    board: chess.Board,
    infos: Sequence[dict[str, Any]],
    *,
    depth: int,
    mate_score: int,
) -> dict[str, Any]:
    if len(infos) < 2:
        raise ValueError(
            "engine analysis must contain at least two principal variations"
        )
    variations = []
    for rank, info in enumerate(infos, start=1):
        pv = list(info.get("pv", []))
        if not pv:
            raise ValueError("engine analysis is missing a principal variation")
        pov = info["score"].pov(board.turn)
        variations.append(
            {
                "rank": rank,
                "move": pv[0].uci(),
                "score_cp": numeric_score(info, board.turn, mate_score),
                "mate_in": pov.mate(),
                "pv": [move.uci() for move in pv[:8]],
                "pv_legal": pv_is_legal(board, pv[:8]),
            }
        )
    return {
        "depth": depth,
        "top_move": variations[0]["move"],
        "best_score_cp": variations[0]["score_cp"],
        "second_score_cp": variations[1]["score_cp"],
        "gap_cp": variations[0]["score_cp"] - variations[1]["score_cp"],
        "equivalent_forced_mates": variations[0]["mate_in"] is not None
        and variations[1]["mate_in"] is not None,
        "variations": variations,
    }


def admission_reasons(
    shallow: dict[str, Any],
    deep: dict[str, Any],
    *,
    minimum_gap_cp: int,
    duplicate: bool,
) -> list[str]:
    reasons = []
    if duplicate:
        reasons.append("duplicate-position")
    if shallow["top_move"] != deep["top_move"]:
        reasons.append("top-move-changed")
    if deep["gap_cp"] < minimum_gap_cp:
        reasons.append("insufficient-final-gap")
    if deep["equivalent_forced_mates"]:
        reasons.append("multiple-forced-mate-moves")
    if not all(
        row["pv_legal"]
        for analysis in (shallow, deep)
        for row in analysis["variations"]
    ):
        reasons.append("illegal-principal-variation")
    return reasons


def select_verification_slice(
    puzzles: Sequence[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    if count > len(puzzles):
        raise ValueError("verification slice is larger than the admitted pool")
    ordered = sorted(
        puzzles, key=lambda row: (row["label"]["legal_move_count"], row["id"])
    )
    buckets = [ordered[index::4] for index in range(4)]
    rng = random.Random(seed)
    for bucket in buckets:
        rng.shuffle(bucket)
    chosen = []
    while len(chosen) < count:
        progressed = False
        for bucket in buckets:
            if bucket and len(chosen) < count:
                chosen.append(bucket.pop())
                progressed = True
        if not progressed:
            break
    return chosen


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    candidates = benchmark.load_puzzle_suite(args.candidates)
    excluded = benchmark.load_puzzle_suite(args.exclude_suite)
    excluded_fens = {row["fen"] for row in excluded["puzzles"]}
    engine_path_text = shutil.which(args.engine)
    if engine_path_text is None:
        raise ValueError(f"engine executable unavailable: {args.engine}")
    engine_path = Path(engine_path_text).resolve()
    depths = config["verification_depths"]
    rows = []
    admitted = []
    seen: set[str] = set()
    with chess.engine.SimpleEngine.popen_uci(str(engine_path)) as engine:
        engine.configure({"Threads": 1, "Hash": 128})
        engine_name = engine.id.get("name", "unknown")
        for candidate in candidates["puzzles"]:
            board = chess.Board(candidate["fen"])
            analyses = []
            for depth in depths:
                info = engine.analyse(
                    board,
                    chess.engine.Limit(depth=depth),
                    multipv=min(config["multipv"], board.legal_moves.count()),
                )
                if not isinstance(info, list):
                    info = [info]
                analyses.append(
                    summarize_analysis(
                        board,
                        info,
                        depth=depth,
                        mate_score=config["mate_score_cp"],
                    )
                )
            duplicate = candidate["fen"] in excluded_fens or candidate["fen"] in seen
            seen.add(candidate["fen"])
            reasons = admission_reasons(
                analyses[0],
                analyses[1],
                minimum_gap_cp=config["minimum_final_gap_cp"],
                duplicate=duplicate,
            )
            row = {
                "candidate_id": candidate["id"],
                "fen": candidate["fen"],
                "provisional_best_moves": candidate["best_moves"],
                "analyses": analyses,
                "admitted": not reasons,
                "rejection_reasons": reasons,
            }
            rows.append(row)
            if not reasons:
                final = analyses[-1]
                admitted.append(
                    {
                        **candidate,
                        "best_moves": [final["top_move"]],
                        "split": "candidate-only",
                        "provenance": {
                            **candidate["provenance"],
                            "deep_verifier_revision": "verify-chess-candidate-labels/v1",
                        },
                        "label": {
                            "engine": engine_name,
                            "depth": depths[-1],
                            "source_ply": candidate["label"].get("source_ply", 0),
                            "legal_move_count": board.legal_moves.count(),
                            "best_score_cp": final["best_score_cp"],
                            "second_score_cp": final["second_score_cp"],
                            "gap_cp": final["gap_cp"],
                            "principal_variation": final["variations"][0]["pv"],
                            "verification": analyses,
                        },
                    }
                )
    stability_count = sum(
        row["analyses"][0]["top_move"] == row["analyses"][1]["top_move"] for row in rows
    )
    report = {
        "schema_version": REPORT_SCHEMA,
        "candidate_suite_id": candidates["suite_id"],
        "engine": {
            "name": engine_name,
            "path_basename": engine_path.name,
            "binary_sha256": file_sha256(engine_path),
            "threads": 1,
            "hash_mb": 128,
        },
        "config": config,
        "aggregate": {
            "candidates": len(rows),
            "stable_top_move": stability_count,
            "stability_rate": stability_count / len(rows),
            "admitted": len(admitted),
            "admission_rate": len(admitted) / len(rows),
        },
        "candidates": rows,
    }
    report["trace_hash"] = benchmark.sha256_json(report)
    admitted_suite = {
        "schema_version": benchmark.PUZZLE_SUITE_SCHEMA,
        "suite_id": "chess-tactics-deep-admitted-v1",
        "status": "candidate-only-not-frozen-evidence",
        "generator": {
            "revision": "verify-chess-candidate-labels/v1",
            "source_suite_id": candidates["suite_id"],
            "report_trace_hash": report["trace_hash"],
        },
        "puzzles": admitted,
    }
    slice_rows = select_verification_slice(
        admitted,
        min(config["verification_slice_count"], len(admitted)),
        config["verification_slice_seed"],
    )
    verification_slice = {
        "schema_version": benchmark.PUZZLE_SUITE_SCHEMA,
        "suite_id": "chess-tactics-candidate-verification-v1",
        "status": "candidate-verification-only-not-frozen-evidence",
        "generator": {
            "revision": "verify-chess-candidate-labels/v1",
            "source_suite_id": admitted_suite["suite_id"],
            "selection": "legal-move-count-stratified-four-bucket",
            "seed": config["verification_slice_seed"],
        },
        "puzzles": slice_rows,
    }
    benchmark.write_json_exclusive(args.output_report, report)
    benchmark.write_json_exclusive(args.output_suite, admitted_suite)
    benchmark.write_json_exclusive(args.output_slice, verification_slice)
    print(
        json.dumps(
            {
                "candidates": len(rows),
                "stable": stability_count,
                "admitted": len(admitted),
                "slice": len(slice_rows),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
