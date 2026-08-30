#!/usr/bin/env python3
"""Grade archived candidate moves with a pinned, evaluation-only Stockfish referee."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
from pathlib import Path
from typing import Any, Callable

import chess
import chess.engine

import chess_benchmark as benchmark

CONFIG_SCHEMA = "chess/move-quality-config/v1"
RESULT_SCHEMA = "chess/move-quality-result/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--candidate-policy-id")
    parser.add_argument("--stockfish")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported chess move-quality config")
    if set(config) != {
        "schema_version",
        "config_id",
        "status",
        "engine",
        "thresholds_cp",
    }:
        raise ValueError("move-quality config fields are incomplete")
    engine = config["engine"]
    if set(engine) != {
        "binary",
        "required_name_prefix",
        "threads",
        "hash_mb",
        "depth",
        "mate_score_cp",
    }:
        raise ValueError("move-quality engine fields are incomplete")
    if engine["threads"] != 1 or any(
        not isinstance(engine[key], int) or engine[key] < 1
        for key in ("hash_mb", "depth", "mate_score_cp")
    ):
        raise ValueError("move-quality engine limits are invalid")
    thresholds = config["thresholds_cp"]
    if set(thresholds) != {"blunder", "severe_blunder"}:
        raise ValueError("move-quality thresholds are incomplete")
    if not 0 < thresholds["blunder"] < thresholds["severe_blunder"]:
        raise ValueError("move-quality thresholds must be positive and ordered")
    return config


def summarize_losses(losses: list[int], thresholds: dict[str, int]) -> dict[str, Any]:
    if not losses:
        return {
            "scored_moves": 0,
            "average_centipawn_loss": None,
            "median_centipawn_loss": None,
            "blunder_rate": None,
            "severe_blunder_rate": None,
        }
    ordered = sorted(losses)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    return {
        "scored_moves": len(losses),
        "average_centipawn_loss": sum(losses) / len(losses),
        "median_centipawn_loss": median,
        "blunder_rate": sum(loss >= thresholds["blunder"] for loss in losses)
        / len(losses),
        "severe_blunder_rate": sum(
            loss >= thresholds["severe_blunder"] for loss in losses
        )
        / len(losses),
    }


class StockfishReferee:
    def __init__(self, binary: str, config: dict[str, Any]):
        self.config = config
        self.engine = chess.engine.SimpleEngine.popen_uci(binary)
        name = str(self.engine.id.get("name", ""))
        if not name.startswith(config["required_name_prefix"]):
            self.close()
            raise ValueError(f"Stockfish identity mismatch: {name!r}")
        self.identity = {"name": name, "author": self.engine.id.get("author")}
        self.engine.configure({"Threads": config["threads"], "Hash": config["hash_mb"]})

    def _score(self, board: chess.Board, root_move: chess.Move | None = None) -> int:
        kwargs = {"root_moves": [root_move]} if root_move is not None else {}
        info = self.engine.analyse(
            board, chess.engine.Limit(depth=self.config["depth"]), **kwargs
        )
        value = (
            info["score"].pov(board.turn).score(mate_score=self.config["mate_score_cp"])
        )
        if value is None:
            raise ValueError("Stockfish returned an unscorable position")
        return int(value)

    def score_move(self, board: chess.Board, move: chess.Move) -> tuple[int, int]:
        return self._score(board), self._score(board, move)

    def close(self) -> None:
        if getattr(self, "engine", None) is not None:
            try:
                self.engine.quit()
            finally:
                self.engine = None


def grade_trace(
    document: dict[str, Any],
    candidate_policy_id: str,
    thresholds: dict[str, int],
    score_move: Callable[[chess.Board, chess.Move], tuple[int, int]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    games = document.get("games")
    if not isinstance(games, list):
        raise ValueError("move-quality input must contain full-game traces")
    for game in games:
        for decision in game.get("decisions", []):
            if decision.get("policy_id") != candidate_policy_id or not decision.get(
                "legal"
            ):
                continue
            board = chess.Board(decision["pre_fen"])
            move = chess.Move.from_uci(decision["parsed_move"])
            if move not in board.legal_moves:
                raise ValueError("archived trace marks an illegal move as legal")
            best_cp, played_cp = score_move(board, move)
            if not all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in (best_cp, played_cp)
            ):
                raise ValueError("move scorer must return integer centipawn values")
            loss = max(0, best_cp - played_cp)
            rows.append(
                {
                    "game_id": game.get("game_id"),
                    "ply": decision["ply"],
                    "pre_fen": decision["pre_fen"],
                    "move": decision["parsed_move"],
                    "best_cp": best_cp,
                    "played_cp": played_cp,
                    "centipawn_loss": loss,
                    "blunder": loss >= thresholds["blunder"],
                    "severe_blunder": loss >= thresholds["severe_blunder"],
                }
            )
    return summarize_losses([row["centipawn_loss"] for row in rows], thresholds), rows


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    document = json.loads(args.input.read_text(encoding="utf-8"))
    policy_id = args.candidate_policy_id or document.get("candidate", {}).get(
        "policy_id"
    )
    if not isinstance(policy_id, str) or not policy_id:
        raise ValueError("candidate policy id is missing")
    requested_binary = args.stockfish or config["engine"]["binary"]
    binary = shutil.which(requested_binary) or requested_binary
    if not Path(binary).is_file():
        raise ValueError(f"Stockfish binary not found: {requested_binary}")
    referee = StockfishReferee(binary, config["engine"])
    try:
        aggregate, rows = grade_trace(
            document, policy_id, config["thresholds_cp"], referee.score_move
        )
    finally:
        referee.close()
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "evaluation-only-stockfish-referee",
        "config_id": config["config_id"],
        "config_hash": benchmark.sha256_json(config),
        "source": {
            "path": str(args.input),
            "sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
            "trace_hash": document.get("trace_hash"),
        },
        "candidate_policy_id": policy_id,
        "engine": {
            "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            "identity": referee.identity,
            **config["engine"],
            "role": "offline-referee-never-available-at-inference",
        },
        "thresholds_cp": config["thresholds_cp"],
        "runtime": {
            "python": platform.python_version(),
            "python_chess": chess.__version__,
        },
        "aggregate": aggregate,
        "decisions": rows,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **aggregate}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
