
# These modules moved to sibling group folders when scripts/ was grouped;
# add those folders to the import path so this archived script still runs.
import sys as _sys
from pathlib import Path as _Path
for _g in ["chess"]:
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / _g))

#!/usr/bin/env python3
"""Generate novel development tactics from deterministic shallow engine play."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

import chess
import chess.engine

import chess_benchmark as benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--engine", default="stockfish")
    parser.add_argument("--play-depth", type=int, default=8)
    parser.add_argument("--label-depth", type=int, default=12)
    parser.add_argument("--minimum-gap-cp", type=int, default=220)
    parser.add_argument("--suite-id", default="chess-tactics-development-v1")
    parser.add_argument("--id-prefix", default="chess-dev")
    parser.add_argument("--status", default="development-only-not-frozen-evidence")
    return parser.parse_args()


def numeric_score(info: dict[str, Any], turn: chess.Color) -> int:
    return info["score"].pov(turn).score(mate_score=100_000)


def main() -> int:
    args = parse_args()
    if not 4 <= args.count <= 100:
        raise ValueError("development puzzle count must be from 4 through 100")
    engine_path = shutil.which(args.engine)
    if engine_path is None:
        raise ValueError(f"engine executable unavailable: {args.engine}")
    rng = random.Random(args.seed)
    puzzles: list[dict[str, Any]] = []
    seen: set[str] = set()
    attempts = 0
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        while len(puzzles) < args.count and attempts < args.count * 80:
            attempts += 1
            board = chess.Board()
            target_ply = rng.randint(14, 58)
            candidate = None
            for ply in range(target_ply):
                if board.is_game_over(claim_draw=True):
                    break
                infos = engine.analyse(
                    board,
                    chess.engine.Limit(depth=args.play_depth),
                    multipv=min(4, board.legal_moves.count()),
                )
                if not isinstance(infos, list):
                    infos = [infos]
                ranked = [info["pv"][0] for info in infos if info.get("pv")]
                if not ranked:
                    break
                if ply >= 10 and rng.random() < 0.18:
                    alternatives = [move for move in board.legal_moves if move not in ranked[:1]]
                    move = rng.choice(alternatives) if alternatives else ranked[0]
                else:
                    move = ranked[min(int(rng.random() ** 2 * len(ranked)), len(ranked) - 1)]
                board.push(move)
                if ply < 12 or board.is_game_over(claim_draw=True) or board.legal_moves.count() < 2:
                    continue
                labels = engine.analyse(
                    board,
                    chess.engine.Limit(depth=args.label_depth),
                    multipv=2,
                )
                if not isinstance(labels, list) or len(labels) < 2:
                    continue
                best = numeric_score(labels[0], board.turn)
                second = numeric_score(labels[1], board.turn)
                gap = best - second
                if gap < args.minimum_gap_cp:
                    continue
                best_move = labels[0]["pv"][0].uci()
                fen = board.fen(en_passant="fen")
                if fen in seen:
                    continue
                candidate = {
                    "fen": fen,
                    "best_move": best_move,
                    "gap_cp": gap,
                    "best_score_cp": best,
                    "second_score_cp": second,
                    "source_ply": board.ply(),
                    "legal_move_count": board.legal_moves.count(),
                    "principal_variation": [move.uci() for move in labels[0].get("pv", [])[:6]],
                }
                break
            if candidate is None:
                continue
            seen.add(candidate["fen"])
            index = len(puzzles) + 1
            puzzles.append(
                {
                    "id": f"{args.id_prefix}-{index:03d}",
                    "fen": candidate["fen"],
                    "best_moves": [candidate["best_move"]],
                    "themes": ["engine-generated", "tactical-gap"],
                    "split": "development-only",
                    "provenance": {
                        "origin": "deterministic Stockfish shallow self-play with injected non-best moves",
                        "generator_revision": "build-chess-development-suite/v1",
                        "generator_seed": args.seed,
                        "attempt": attempts,
                    },
                    "label": {
                        "engine": "Stockfish 18",
                        "depth": args.label_depth,
                        **{key: value for key, value in candidate.items() if key != "fen" and key != "best_move"},
                    },
                }
            )
    if len(puzzles) != args.count:
        raise ValueError(f"generated only {len(puzzles)} of {args.count} requested puzzles")
    suite = {
        "schema_version": benchmark.PUZZLE_SUITE_SCHEMA,
        "suite_id": args.suite_id,
        "status": args.status,
        "generator": {
            "revision": "build-chess-development-suite/v1",
            "seed": args.seed,
            "engine": "Stockfish 18",
            "play_depth": args.play_depth,
            "label_depth": args.label_depth,
            "minimum_gap_cp": args.minimum_gap_cp,
            "attempts": attempts,
        },
        "puzzles": puzzles,
    }
    benchmark.write_json_exclusive(args.output, suite)
    print(json.dumps({"output": str(args.output), "puzzles": len(puzzles), "attempts": attempts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
