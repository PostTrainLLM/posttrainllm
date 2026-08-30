#!/usr/bin/env python3
"""Shared no-tools character policy contract for the chess benchmark."""

from __future__ import annotations

import json
from typing import Any, Sequence

import chess

import chess_benchmark as benchmark

STRICT_TRACK = "strict"
LEGAL_CONSTRAINED_TRACK = "legal-constrained-diagnostic"
TRACKS = (STRICT_TRACK, LEGAL_CONSTRAINED_TRACK)

SYSTEM_PROMPT = """You are a chess policy. You receive one character-only state.
FEN is the complete six-field chess position, PLY is the zero-based move index,
and LEGAL is the complete comma-separated set of currently legal UCI moves.
Choose the move that maximizes your chance of winning. Reply with exactly one
move from LEGAL and nothing else. Do not use tools, engines, code, search,
rollouts, opening books, or hidden state from earlier decisions."""


def validate_track(track: str) -> None:
    if track not in TRACKS:
        raise ValueError(f"evaluation track must be one of {TRACKS}")


def messages(state: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": benchmark.serialize_observation(state)},
    ]


def flat_prompt(state: dict[str, Any]) -> str:
    return f"{SYSTEM_PROMPT}\n\nState:\n{benchmark.serialize_observation(state)}"


def constrained_action_schema(legal_moves: Sequence[str]) -> dict[str, Any]:
    if not legal_moves:
        raise ValueError("legal move set cannot be empty")
    return {
        "type": "object",
        "properties": {"move": {"type": "string", "enum": list(legal_moves)}},
        "required": ["move"],
        "additionalProperties": False,
    }


def parse_constrained_output(raw: str, board: chess.Board) -> chess.Move:
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"move"}:
        raise ValueError("constrained output must contain only move")
    return benchmark.parse_strict_uci(value["move"], board)
