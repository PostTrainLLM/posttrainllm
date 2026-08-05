#!/usr/bin/env python3
"""Build a gold-free sealed batch prompt for Devin GLM Chess verification."""

from __future__ import annotations

import argparse
from pathlib import Path

import chess

import chess_benchmark as benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite = benchmark.load_puzzle_suite(args.suite)
    if args.offset < 0 or not 1 <= args.limit or args.offset + args.limit > len(suite["puzzles"]):
        raise ValueError("batch limit is outside suite bounds")
    lines = [
        "GOAL:",
        "Choose one chess move for each independent position below.",
        "",
        "SCOPE:",
        f"Return exactly {args.limit} decisions, in the supplied order.",
        "Each state contains a six-field FEN, a zero-based PLY, and the complete sorted legal UCI move set.",
        "",
        "CONSTRAINTS:",
        "Do not use tools, files, code, an engine, search, an opening book, hidden state, or subagents.",
        "Reason only from the characters in this prompt.",
        "Choose exactly one move from that position's LEGAL list.",
        "Return only one JSON object with this shape:",
        '{"moves":[{"puzzle_id":"...","move":"e2e4"}]}',
        "No markdown, prose, analysis, or additional fields.",
        "",
        "VERIFY:",
        "Before returning, check that every puzzle_id appears exactly once and every move is copied exactly from its LEGAL list.",
        "",
        "RETURN:",
        "Return only the JSON object now. Do not reveal reasoning.",
        "",
        "POSITIONS:",
    ]
    for puzzle in suite["puzzles"][args.offset : args.offset + args.limit]:
        board = chess.Board(puzzle["fen"])
        state = benchmark.observation(board, int(puzzle["label"].get("source_ply", 0)))
        lines.append(f"ID={puzzle['id']};{benchmark.serialize_observation(state)}")
    text = "\n".join(lines) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite {args.output}") from exc
    print(f"wrote {args.limit} gold-free positions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
