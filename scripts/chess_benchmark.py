#!/usr/bin/env python3
"""Deterministic chess evaluation and replay helpers backed by python-chess."""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from pathlib import Path
from typing import Any, Protocol, Sequence

import chess

ENVIRONMENT_REVISION = "character-chess/v1"
OBSERVATION_REVISION = "chess/character-observation/v1"
PUZZLE_SUITE_SCHEMA = "chess/puzzle-suite/v1"
PUZZLE_RESULT_SCHEMA = "chess/puzzle-result/v1"
GAME_RESULT_SCHEMA = "chess/game-result/v1"
UCI_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$", re.ASCII)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite {path}") from exc


def normalized_fen(fen: str) -> str:
    if not isinstance(fen, str):
        raise ValueError("FEN must be text")
    board = chess.Board(fen)
    return board.fen(en_passant="fen")


def legal_uci(board: chess.Board) -> tuple[str, ...]:
    return tuple(sorted(move.uci() for move in board.legal_moves))


def observation(board: chess.Board, ply: int) -> dict[str, Any]:
    if not isinstance(ply, int) or isinstance(ply, bool) or ply < 0:
        raise ValueError("ply must be a non-negative integer")
    return {
        "fen": board.fen(en_passant="fen"),
        "ply": ply,
        "legal_moves": list(legal_uci(board)),
        "initial_fen": board.root().fen(en_passant="fen"),
        "history_uci": [move.uci() for move in board.move_stack],
    }


def serialize_observation(value: dict[str, Any]) -> str:
    fen = normalized_fen(value.get("fen"))
    ply = value.get("ply")
    if not isinstance(ply, int) or isinstance(ply, bool) or ply < 0:
        raise ValueError("observation ply must be a non-negative integer")
    board = chess.Board(fen)
    declared = value.get("legal_moves")
    if declared != list(legal_uci(board)):
        raise ValueError("observation legal moves do not match FEN")
    return f"FEN={fen};PLY={ply};LEGAL={','.join(declared)}"


def parse_strict_uci(raw: Any, board: chess.Board) -> chess.Move:
    if not isinstance(raw, str):
        raise ValueError("model move must be text")
    candidate = raw.strip().lower()
    if not UCI_PATTERN.fullmatch(candidate):
        raise ValueError("model output must contain exactly one UCI move")
    # board.parse_uci canonicalizes standard castling when a source uses the
    # Chess960-style king-to-rook-square encoding (for example e8h8 -> e8g8).
    move = board.parse_uci(candidate)
    if move not in board.legal_moves:
        raise ValueError("model output is not legal in the current position")
    return move


def load_puzzle_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(suite, dict) or suite.get("schema_version") != PUZZLE_SUITE_SCHEMA:
        raise ValueError("unsupported chess puzzle suite")
    puzzles = suite.get("puzzles")
    if not isinstance(puzzles, list) or not puzzles:
        raise ValueError("puzzle suite must contain puzzles")
    ids: list[str] = []
    for puzzle in puzzles:
        required = {"id", "fen", "best_moves", "themes", "split", "provenance", "label"}
        if not isinstance(puzzle, dict) or set(puzzle) != required:
            raise ValueError("puzzle fields are incomplete")
        board = chess.Board(puzzle["fen"])
        if puzzle["fen"] != board.fen(en_passant="fen"):
            raise ValueError(f"puzzle FEN is not canonical: {puzzle['id']}")
        best_moves = puzzle["best_moves"]
        if not isinstance(best_moves, list) or not best_moves:
            raise ValueError(f"puzzle has no best moves: {puzzle['id']}")
        if any(move not in legal_uci(board) for move in best_moves):
            raise ValueError(f"puzzle best move is illegal: {puzzle['id']}")
        ids.append(puzzle["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("puzzle ids must be unique")
    return suite


class TextPolicy(Protocol):
    policy_id: str
    revision: str

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> Any:
        ...


class RandomLegalPolicy:
    revision = "random-legal/v1"

    def __init__(self, seed: int, policy_id: str = "random-legal"):
        self.policy_id = policy_id
        self._rng = random.Random(seed)

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        del state
        if not legal_moves:
            raise ValueError("random policy received no legal moves")
        return self._rng.choice(list(legal_moves))


def evaluate_puzzles(policy: TextPolicy, suite: dict[str, Any]) -> dict[str, Any]:
    rows = []
    latencies = []
    for index, puzzle in enumerate(suite["puzzles"]):
        board = chess.Board(puzzle["fen"])
        state = observation(board, int(puzzle["label"].get("source_ply", 0)))
        started = time.perf_counter_ns()
        failure = None
        raw = None
        try:
            raw = policy.choose(state, state["legal_moves"])
            move = parse_strict_uci(raw, board)
            parsed = move.uci()
        except Exception as exc:  # Model/provider failures are evidence rows.
            if raw is None:
                raw = getattr(exc, "raw_output", None)
            parsed = None
            failure = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(latency_ms)
        rows.append(
            {
                "index": index,
                "puzzle_id": puzzle["id"],
                "input": serialize_observation(state),
                "fen": state["fen"],
                "legal_moves": state["legal_moves"],
                "best_moves": puzzle["best_moves"],
                "raw_output": raw,
                "parsed_move": parsed,
                "legal": parsed is not None,
                "exact": parsed in puzzle["best_moves"] if parsed is not None else False,
                "failure": failure,
                "latency_ms": latency_ms,
                "themes": puzzle["themes"],
            }
        )
    exact = sum(row["exact"] for row in rows)
    legal = sum(row["legal"] for row in rows)
    result = {
        "schema_version": PUZZLE_RESULT_SCHEMA,
        "environment_revision": ENVIRONMENT_REVISION,
        "observation_revision": OBSERVATION_REVISION,
        "suite_id": suite["suite_id"],
        "policy": {"policy_id": policy.policy_id, "revision": policy.revision},
        "aggregate": {
            "puzzles": len(rows),
            "exact": exact,
            "exact_move_accuracy": exact / len(rows),
            "legal": legal,
            "legal_rate": legal / len(rows),
            "mean_latency_ms": sum(latencies) / len(latencies),
            "total_wall_time_ms": sum(latencies),
        },
        "decisions": rows,
    }
    result["trace_hash"] = sha256_json(result)
    return result


def _outcome(board: chess.Board, claim_draw: bool = True) -> dict[str, Any] | None:
    value = board.outcome(claim_draw=claim_draw)
    if value is None:
        return None
    return {
        "winner": "white" if value.winner is chess.WHITE else "black" if value.winner is chess.BLACK else None,
        "result": value.result(),
        "termination": value.termination.name.lower().replace("_", "-"),
    }


def run_game(
    white: TextPolicy,
    black: TextPolicy,
    *,
    starting_fen: str = chess.STARTING_FEN,
    maximum_plies: int = 160,
) -> dict[str, Any]:
    if not 1 <= maximum_plies <= 512:
        raise ValueError("maximum plies must be from 1 through 512")
    board = chess.Board(normalized_fen(starting_fen))
    initial_fen = board.fen(en_passant="fen")
    decisions = []
    for ply in range(maximum_plies):
        existing = _outcome(board)
        if existing is not None:
            break
        side = "white" if board.turn == chess.WHITE else "black"
        policy = white if board.turn == chess.WHITE else black
        state = observation(board, ply)
        pre_fen = state["fen"]
        started = time.perf_counter_ns()
        failure = None
        raw = None
        policy_metadata = None
        try:
            raw = policy.choose(state, state["legal_moves"])
            metadata = getattr(policy, "last_decision_metadata", None)
            policy_metadata = json.loads(json.dumps(metadata)) if isinstance(metadata, dict) else None
            move = parse_strict_uci(raw, board)
            parsed = move.uci()
            board.push(move)
        except Exception as exc:
            metadata = getattr(policy, "last_decision_metadata", None)
            policy_metadata = json.loads(json.dumps(metadata)) if isinstance(metadata, dict) else None
            if raw is None:
                raw = getattr(exc, "raw_output", None)
            parsed = None
            failure = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        decisions.append(
            {
                "ply": ply,
                "side": side,
                "policy_id": policy.policy_id,
                "input": serialize_observation(state),
                "pre_fen": pre_fen,
                "legal_moves": state["legal_moves"],
                "raw_output": raw,
                "parsed_move": parsed,
                "legal": parsed is not None,
                "failure": failure,
                "policy_metadata": policy_metadata,
                "post_fen": board.fen(en_passant="fen"),
                "latency_ms": latency_ms,
            }
        )
        if failure is not None:
            game_outcome = {
                "winner": "black" if side == "white" else "white",
                "result": "0-1" if side == "white" else "1-0",
                "termination": "invalid-decision-forfeit",
            }
            break
    else:
        game_outcome = {"winner": None, "result": "1/2-1/2", "termination": "move-cap-draw"}
    if "game_outcome" not in locals():
        game_outcome = _outcome(board) or {"winner": None, "result": "1/2-1/2", "termination": "move-cap-draw"}
    result = {
        "schema_version": GAME_RESULT_SCHEMA,
        "environment_revision": ENVIRONMENT_REVISION,
        "initial_fen": initial_fen,
        "white": {"policy_id": white.policy_id, "revision": white.revision},
        "black": {"policy_id": black.policy_id, "revision": black.revision},
        "maximum_plies": maximum_plies,
        "outcome": game_outcome,
        "final_fen": board.fen(en_passant="fen"),
        "decisions": decisions,
    }
    result["trace_hash"] = sha256_json(result)
    return result
