#!/usr/bin/env python3
"""Shared text-only language-model policy contract for the 2048 experiment."""

from __future__ import annotations

import json
from typing import Any, Sequence

import game_2048 as game

STRICT_TRACK = "strict"
LEGAL_CONSTRAINED_TRACK = "legal-constrained-diagnostic"
TRACKS = (STRICT_TRACK, LEGAL_CONSTRAINED_TRACK)

ACTION_CHARACTERS = {"up": "U", "down": "D", "left": "L", "right": "R"}

SYSTEM_PROMPT = """You are a 2048 policy. You receive one text state:
B has exactly 16 row-major cells. Each character is the base-36 exponent of a
tile: 0 is empty, 1 is tile 2, 2 is tile 4, and b is tile 2048. S is score, M is
move count, and L lists the currently legal actions using U,D,L,R.
Choose the move that maximizes long-term 2048 score. Reply with exactly one
character from L and nothing else. Do not use tools, code, search, or rollouts."""


def validate_track(track: str) -> None:
    if track not in TRACKS:
        raise ValueError(f"evaluation track must be one of {TRACKS}")


def legal_characters(legal_actions: Sequence[str]) -> tuple[str, ...]:
    if not legal_actions:
        raise ValueError("language-model policy received no legal actions")
    try:
        characters = tuple(ACTION_CHARACTERS[action] for action in legal_actions)
    except KeyError as exc:
        raise ValueError(f"unknown legal action: {exc.args[0]}") from exc
    if len(characters) != len(set(characters)):
        raise ValueError("legal actions must be unique")
    return characters


def messages(observation: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": game.serialize_character_observation(observation)},
    ]


def flat_prompt(observation: dict[str, Any]) -> str:
    return f"{SYSTEM_PROMPT}\n\nState:\n{game.serialize_character_observation(observation)}"


def constrained_action_schema(legal_actions: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": list(legal_characters(legal_actions))}},
        "required": ["action"],
        "additionalProperties": False,
    }


def parse_constrained_output(raw: str) -> str:
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"action"}:
        raise ValueError("constrained output must contain only action")
    return game.parse_character_action(value["action"])
