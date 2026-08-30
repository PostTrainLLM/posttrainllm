#!/usr/bin/env python3
"""Deterministic, dependency-free 2048 environment and no-model baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

BOARD_SIZE = 4
CELL_COUNT = BOARD_SIZE * BOARD_SIZE
ACTIONS = ("up", "down", "left", "right")
ENVIRONMENT_REVISION = "deterministic-2048/v1"
EPISODE_SCHEMA = "game-2048/episode/v1"
COHORT_SCHEMA = "game-2048/cohort-result/v1"
RUNNER_REVISION = "paired-seed-runner/v1"
POLICY_ADAPTER_REVISION = "game-2048/policy-adapter/v1"
CHARACTER_OBSERVATION_REVISION = "game-2048/character-observation/v1"
TILE_EXPONENT_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
ACTION_CHARACTERS = {"up": "U", "down": "D", "left": "L", "right": "R"}
CHARACTER_ACTIONS = {
    character: action for action, character in ACTION_CHARACTERS.items()
}
MASK_64 = (1 << 64) - 1

Board = tuple[int, ...]
Clock = Callable[[], int]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"refusing to overwrite {path}") from exc


def _is_tile(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (value == 0 or value > 0 and value & (value - 1) == 0)
    )


def board_tuple(board: Sequence[int]) -> Board:
    if len(board) != CELL_COUNT:
        raise ValueError(f"board must contain exactly {CELL_COUNT} cells")
    if not all(_is_tile(value) for value in board):
        raise ValueError("board cells must be zero or positive powers of two")
    return tuple(board)


def board_hash(board: Sequence[int]) -> str:
    return sha256_json(list(board_tuple(board)))


def serialize_character_observation(observation: dict[str, Any]) -> str:
    """Serialize visible state as compact text; no image or spatial encoder."""
    board = board_tuple(observation.get("board", []))
    encoded_cells: list[str] = []
    for value in board:
        exponent = value.bit_length() - 1 if value else 0
        if exponent >= len(TILE_EXPONENT_ALPHABET):
            raise ValueError("tile exponent exceeds the character observation alphabet")
        encoded_cells.append(TILE_EXPONENT_ALPHABET[exponent])
    score = observation.get("score")
    move_count = observation.get("move_count")
    if not isinstance(score, int) or isinstance(score, bool) or score < 0:
        raise ValueError("observation score must be a non-negative integer")
    if (
        not isinstance(move_count, int)
        or isinstance(move_count, bool)
        or move_count < 0
    ):
        raise ValueError("observation move_count must be a non-negative integer")
    legal = observation.get("legal_actions")
    if (
        not isinstance(legal, list)
        or len(legal) != len(set(legal))
        or any(action not in ACTIONS for action in legal)
    ):
        raise ValueError("observation legal_actions must be a unique action list")
    legal_characters = "".join(
        ACTION_CHARACTERS[action] for action in ACTIONS if action in legal
    )
    return f"B={''.join(encoded_cells)};S={score};M={move_count};L={legal_characters}"


def parse_character_action(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("model action must be text")
    character = raw.strip().upper()
    if character not in CHARACTER_ACTIONS:
        raise ValueError("model output must contain exactly one action character")
    return CHARACTER_ACTIONS[character]


def _line_indices(action: str) -> tuple[tuple[int, ...], ...]:
    if action == "left":
        return tuple(
            tuple(row * BOARD_SIZE + column for column in range(BOARD_SIZE))
            for row in range(BOARD_SIZE)
        )
    if action == "right":
        return tuple(
            tuple(row * BOARD_SIZE + column for column in reversed(range(BOARD_SIZE)))
            for row in range(BOARD_SIZE)
        )
    if action == "up":
        return tuple(
            tuple(row * BOARD_SIZE + column for row in range(BOARD_SIZE))
            for column in range(BOARD_SIZE)
        )
    if action == "down":
        return tuple(
            tuple(row * BOARD_SIZE + column for row in reversed(range(BOARD_SIZE)))
            for column in range(BOARD_SIZE)
        )
    raise ValueError(f"unknown action: {action!r}")


def merge_line(line: Sequence[int]) -> tuple[tuple[int, ...], int]:
    compact = [value for value in line if value]
    merged: list[int] = []
    score_delta = 0
    index = 0
    while index < len(compact):
        value = compact[index]
        if index + 1 < len(compact) and compact[index + 1] == value:
            value *= 2
            score_delta += value
            index += 2
        else:
            index += 1
        merged.append(value)
    merged.extend([0] * (BOARD_SIZE - len(merged)))
    return tuple(merged), score_delta


def move_without_spawn(board: Sequence[int], action: str) -> tuple[Board, int]:
    source = board_tuple(board)
    target = list(source)
    score_delta = 0
    for positions in _line_indices(action):
        merged, line_score = merge_line([source[position] for position in positions])
        score_delta += line_score
        for position, value in zip(positions, merged):
            target[position] = value
    return tuple(target), score_delta


def legal_actions_for(board: Sequence[int]) -> tuple[str, ...]:
    source = board_tuple(board)
    return tuple(
        action for action in ACTIONS if move_without_spawn(source, action)[0] != source
    )


class SplitMix64:
    """Pinned integer PRNG with explicitly observable state."""

    def __init__(self, seed: int):
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError("PRNG seed must be an integer")
        self.state = seed & MASK_64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK_64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK_64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK_64
        return (value ^ (value >> 31)) & MASK_64

    def randbelow(self, upper: int) -> int:
        if not isinstance(upper, int) or upper <= 0:
            raise ValueError("upper bound must be a positive integer")
        limit = (1 << 64) - ((1 << 64) % upper)
        while True:
            value = self.next_u64()
            if value < limit:
                return value % upper


def derive_stream_seed(seed: int, stream: str) -> int:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("game seed must be an integer")
    digest = hashlib.sha256(
        canonical_bytes(
            {
                "environment_revision": ENVIRONMENT_REVISION,
                "seed": seed,
                "stream": stream,
            }
        )
    ).digest()
    return int.from_bytes(digest[:8], "big")


@dataclass(frozen=True)
class Spawn:
    index: int
    value: int

    def as_dict(self) -> dict[str, int]:
        return {
            "index": self.index,
            "row": self.index // BOARD_SIZE,
            "column": self.index % BOARD_SIZE,
            "value": self.value,
        }


class Game2048:
    def __init__(self, seed: int):
        self.seed = seed
        self._rng = SplitMix64(derive_stream_seed(seed, "environment/v1"))
        self.board: Board = (0,) * CELL_COUNT
        self.score = 0
        self.move_count = 0
        self.reset_spawns = (self._spawn(), self._spawn())

    @property
    def rng_state(self) -> int:
        return self._rng.state

    @property
    def legal_actions(self) -> tuple[str, ...]:
        return legal_actions_for(self.board)

    @property
    def terminal(self) -> bool:
        return not self.legal_actions

    def observation(self) -> dict[str, Any]:
        return {
            "board": list(self.board),
            "score": self.score,
            "move_count": self.move_count,
            "legal_actions": list(self.legal_actions),
        }

    def _spawn(self) -> Spawn:
        empty = [index for index, value in enumerate(self.board) if value == 0]
        if not empty:
            raise ValueError("cannot spawn on a full board")
        index = empty[self._rng.randbelow(len(empty))]
        value = 4 if self._rng.randbelow(10) == 0 else 2
        changed = list(self.board)
        changed[index] = value
        self.board = tuple(changed)
        return Spawn(index, value)

    def _record(
        self,
        pre: dict[str, Any],
        action: Any,
        valid: bool,
        failure: str | None,
        score_delta: int,
        spawn: Spawn | None,
        rng_before: int,
    ) -> dict[str, Any]:
        terminal = self.terminal
        return {
            "seed": self.seed,
            "step_index": pre["move_count"],
            "pre_move_board": pre["board"],
            "legal_actions": pre["legal_actions"],
            "chosen_action": action if isinstance(action, str) else None,
            "raw_action": action
            if isinstance(action, (str, int, float, bool)) or action is None
            else repr(action),
            "valid": valid,
            "failure": failure,
            "post_move_board": list(self.board),
            "score_delta": score_delta,
            "cumulative_score": self.score,
            "move_count": self.move_count,
            "maximum_tile": max(self.board),
            "spawn": spawn.as_dict() if spawn else None,
            "environment_rng_state_before": rng_before,
            "environment_rng_state_after": self._rng.state,
            "terminal": terminal,
            "terminal_reason": "no-legal-actions" if terminal else None,
        }

    def reject_decision(self, action: Any, failure: str) -> dict[str, Any]:
        pre = self.observation()
        rng_before = self._rng.state
        return self._record(pre, action, False, failure, 0, None, rng_before)

    def step(self, action: Any) -> dict[str, Any]:
        pre = self.observation()
        rng_before = self._rng.state
        if not isinstance(action, str) or action not in ACTIONS:
            return self._record(
                pre, action, False, "unknown-action", 0, None, rng_before
            )
        moved, score_delta = move_without_spawn(self.board, action)
        if moved == self.board:
            return self._record(
                pre, action, False, "no-state-change", 0, None, rng_before
            )
        self.board = moved
        self.score += score_delta
        self.move_count += 1
        spawn = self._spawn()
        return self._record(pre, action, True, None, score_delta, spawn, rng_before)


class Policy(Protocol):
    policy_id: str
    revision: str

    def choose(
        self, observation: dict[str, Any], legal_actions: Sequence[str]
    ) -> Any: ...


class RandomLegalPolicy:
    policy_id = "random-legal"
    revision = "1"

    def __init__(self, game_seed: int):
        self._rng = SplitMix64(derive_stream_seed(game_seed, "policy/random-legal/v1"))

    def choose(self, observation: dict[str, Any], legal_actions: Sequence[str]) -> str:
        del observation
        if not legal_actions:
            raise ValueError("random policy received no legal actions")
        return legal_actions[self._rng.randbelow(len(legal_actions))]


def _tile_exponent(value: int) -> int:
    return value.bit_length() - 1 if value else 0


def monotonicity(board: Sequence[int]) -> int:
    source = board_tuple(board)
    total = 0
    lines = list(_line_indices("left")) + list(_line_indices("up"))
    for positions in lines:
        values = [_tile_exponent(source[position]) for position in positions]
        increasing = -sum(
            max(0, values[index] - values[index + 1]) for index in range(BOARD_SIZE - 1)
        )
        decreasing = -sum(
            max(0, values[index + 1] - values[index]) for index in range(BOARD_SIZE - 1)
        )
        total += max(increasing, decreasing)
    return total


def heuristic_value(
    board: Sequence[int], score_delta: int, weights: dict[str, int]
) -> int:
    source = board_tuple(board)
    maximum = max(source)
    corners = (source[0], source[BOARD_SIZE - 1], source[-BOARD_SIZE], source[-1])
    features = {
        "immediate_score": score_delta,
        "empty_cells": source.count(0),
        "monotonicity": monotonicity(source),
        "maximum_tile_corner": _tile_exponent(maximum) if maximum in corners else 0,
    }
    return sum(weights[name] * value for name, value in features.items())


class GreedyOnePlyPolicy:
    policy_id = "greedy-one-ply"
    revision = "1"

    def __init__(self, weights: dict[str, int], action_order: Sequence[str]):
        required = {
            "immediate_score",
            "empty_cells",
            "monotonicity",
            "maximum_tile_corner",
        }
        if set(weights) != required or not all(
            isinstance(value, int) for value in weights.values()
        ):
            raise ValueError(
                f"greedy weights must be integer values for {sorted(required)}"
            )
        if set(action_order) != set(ACTIONS) or len(action_order) != len(ACTIONS):
            raise ValueError(
                "greedy action_order must contain every action exactly once"
            )
        self.weights = dict(weights)
        self.action_order = tuple(action_order)

    def _value(self, board: Board, score_delta: int) -> int:
        return heuristic_value(board, score_delta, self.weights)

    def choose(self, observation: dict[str, Any], legal_actions: Sequence[str]) -> str:
        board = board_tuple(observation["board"])
        legal = set(legal_actions)
        ranked: list[tuple[int, int, str]] = []
        for tie_rank, action in enumerate(self.action_order):
            if action in legal:
                moved, score_delta = move_without_spawn(board, action)
                ranked.append((self._value(moved, score_delta), -tie_rank, action))
        if not ranked:
            raise ValueError("greedy policy received no legal actions")
        return max(ranked)[2]


@dataclass
class SearchBudget:
    limit: int
    used: int = 0
    exhausted: bool = False

    def consume(self) -> bool:
        if self.used >= self.limit:
            self.exhausted = True
            return False
        self.used += 1
        return True


class ExpectimaxBoundedPolicy:
    policy_id = "expectimax-bounded"
    revision = "1"

    def __init__(self, config: dict[str, Any]):
        validate_teacher_policy_config(config)
        self.search_depth = config["search_depth"]
        self.max_nodes_per_decision = config["max_nodes_per_decision"]
        self.chance_cell_limit = config["chance_cell_limit"]
        self.action_order = tuple(config["action_order"])
        self.weights = dict(config["weights"])
        self.spawn_distribution = {
            int(tile): probability
            for tile, probability in config["spawn_distribution"].items()
        }
        self.configuration_sha256 = sha256_json(config)
        self.last_search_stats: dict[str, Any] = {}

    def _leaf_value(self, board: Board) -> float:
        return float(heuristic_value(board, 0, self.weights))

    def _sample_empty_cells(self, board: Board) -> tuple[int, ...]:
        empty = tuple(index for index, value in enumerate(board) if value == 0)
        if len(empty) <= self.chance_cell_limit:
            return empty
        return tuple(
            empty[index * len(empty) // self.chance_cell_limit]
            for index in range(self.chance_cell_limit)
        )

    def _player_value(self, board: Board, depth: int, budget: SearchBudget) -> float:
        if not budget.consume() or depth <= 0:
            return self._leaf_value(board)
        legal = legal_actions_for(board)
        if not legal:
            return self._leaf_value(board)
        values = []
        legal_set = set(legal)
        for action in self.action_order:
            if action in legal_set:
                moved, score_delta = move_without_spawn(board, action)
                values.append(
                    score_delta * self.weights["immediate_score"]
                    + self._chance_value(moved, depth - 1, budget)
                )
        return max(values)

    def _chance_value(self, board: Board, depth: int, budget: SearchBudget) -> float:
        if not budget.consume():
            return self._leaf_value(board)
        cells = self._sample_empty_cells(board)
        if not cells:
            return self._player_value(board, depth, budget)
        value = 0.0
        cell_probability = 1.0 / len(cells)
        for index in cells:
            for tile, tile_probability in sorted(self.spawn_distribution.items()):
                spawned = list(board)
                spawned[index] = tile
                value += (
                    cell_probability
                    * tile_probability
                    * self._player_value(tuple(spawned), depth, budget)
                )
        return value

    def choose(self, observation: dict[str, Any], legal_actions: Sequence[str]) -> str:
        board = board_tuple(observation["board"])
        legal = set(legal_actions)
        ordered = [action for action in self.action_order if action in legal]
        if not ordered:
            raise ValueError("expectimax policy received no legal actions")
        quotient, remainder = divmod(self.max_nodes_per_decision, len(ordered))
        ranked: list[tuple[float, int, str]] = []
        budgets = []
        for tie_rank, action in enumerate(ordered):
            budget = SearchBudget(quotient + int(tie_rank < remainder))
            budgets.append(budget)
            moved, score_delta = move_without_spawn(board, action)
            value = score_delta * self.weights["immediate_score"] + self._chance_value(
                moved,
                self.search_depth - 1,
                budget,
            )
            ranked.append((value, -tie_rank, action))
        self.last_search_stats = {
            "search_depth": self.search_depth,
            "node_expansions": sum(budget.used for budget in budgets),
            "max_nodes_per_decision": self.max_nodes_per_decision,
            "budget_exhausted": any(budget.exhausted for budget in budgets),
            "root_actions": len(ordered),
        }
        return max(ranked)[2]


def validate_environment_config(config: dict[str, Any]) -> None:
    expected = {
        "schema_version": "game-2048/environment-config/v1",
        "environment_revision": ENVIRONMENT_REVISION,
        "board_size": BOARD_SIZE,
        "initial_tiles": 2,
        "actions": list(ACTIONS),
        "spawn_distribution": {"2": 9, "4": 1},
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"environment config {key} must be {value!r}")
    prng = config.get("prng")
    if (
        not isinstance(prng, dict)
        or prng.get("algorithm") != "splitmix64"
        or prng.get("revision") != "1"
    ):
        raise ValueError("environment config must pin splitmix64 revision 1")


def validate_evaluation_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "game-2048/evaluation-config/v1":
        raise ValueError("unsupported evaluation config schema")
    if config.get("environment_revision") != ENVIRONMENT_REVISION:
        raise ValueError("evaluation config environment revision mismatch")
    namespaces = config.get("seed_namespaces")
    required_namespaces = {
        "development",
        "trajectory_training",
        "algorithmic_diagnostic",
        "frozen_evaluation",
    }
    if not isinstance(namespaces, dict) or set(namespaces) != required_namespaces:
        raise ValueError(
            f"seed_namespaces must contain exactly {sorted(required_namespaces)}"
        )
    ranges: list[tuple[int, int, str]] = []
    for name, namespace in namespaces.items():
        if not isinstance(namespace, dict):
            raise ValueError(f"seed namespace {name} must be an object")
        start, end = namespace.get("range_start"), namespace.get("range_end")
        seeds = namespace.get("fixture_seeds")
        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            raise ValueError(f"seed namespace {name} has an invalid range")
        if not isinstance(seeds, list) or any(
            not isinstance(seed, int) or seed < start or seed > end for seed in seeds
        ):
            raise ValueError(f"seed namespace {name} has invalid fixture seeds")
        if len(seeds) != len(set(seeds)):
            raise ValueError(f"seed namespace {name} repeats fixture seeds")
        ranges.append((start, end, name))
    for index, (start, end, name) in enumerate(ranges):
        for other_start, other_end, other_name in ranges[index + 1 :]:
            if max(start, other_start) <= min(end, other_end):
                raise ValueError(f"seed namespaces {name} and {other_name} overlap")
    seeds = namespaces["development"]["fixture_seeds"]
    budgets = config.get("budgets", {})
    if not seeds or len(seeds) > budgets.get("max_games", 0):
        raise ValueError("development fixture seeds must fit the max_games budget")
    if (
        budgets.get("max_moves_per_game", 0) <= 0
        or budgets.get("per_move_milliseconds", 0) <= 0
    ):
        raise ValueError("evaluation budgets must be positive")
    baselines = config.get("baselines")
    if not isinstance(baselines, list) or [
        entry.get("policy_id") for entry in baselines
    ] != [
        "random-legal",
        "greedy-one-ply",
    ]:
        raise ValueError(
            "development baselines must be random-legal then greedy-one-ply"
        )
    if any(entry.get("revision") != "1" for entry in baselines):
        raise ValueError("development baseline revisions must be pinned to 1")
    uncertainty = config.get("uncertainty", {})
    if (
        uncertainty.get("paired_bootstrap_revision") != "1"
        or uncertainty.get("bootstrap_samples", 0) <= 0
    ):
        raise ValueError("paired bootstrap revision and sample count must be pinned")
    admission = config.get("benchmark_admission", {})
    required_admission = {
        "frontier_strict_invalid_decisions_maximum",
        "frontier_constrained_paired_mean_score_delta_over_random_minimum",
        "frontier_constrained_paired_bootstrap_lower_bound_minimum",
        "frontier_constrained_paired_win_rate_minimum",
        "frontier_constrained_mean_score_ratio_over_random_minimum",
    }
    if set(admission) != required_admission:
        raise ValueError("benchmark admission thresholds are incomplete")
    if admission["frontier_strict_invalid_decisions_maximum"] != 0:
        raise ValueError("frontier strict-track invalid decision maximum must be zero")
    for field in (
        "frontier_constrained_paired_mean_score_delta_over_random_minimum",
        "frontier_constrained_paired_bootstrap_lower_bound_minimum",
    ):
        value = admission[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"benchmark admission threshold must be positive: {field}")
    win_rate = admission["frontier_constrained_paired_win_rate_minimum"]
    if (
        not isinstance(win_rate, (int, float))
        or isinstance(win_rate, bool)
        or not 0.5 < win_rate <= 1
    ):
        raise ValueError(
            "frontier admission paired win rate must be above one half through one"
        )
    score_ratio = admission["frontier_constrained_mean_score_ratio_over_random_minimum"]
    if (
        not isinstance(score_ratio, (int, float))
        or isinstance(score_ratio, bool)
        or score_ratio < 1.1
    ):
        raise ValueError("frontier admission mean score ratio must be at least 1.1")
    thresholds = config.get("proof_thresholds", {})
    required_thresholds = {
        "candidate_parameter_count_maximum",
        "larger_llm_paired_mean_score_delta_minimum",
        "larger_llm_paired_win_rate_minimum",
        "larger_llm_paired_bootstrap_lower_bound_minimum",
        "invalid_decisions_maximum",
    }
    if set(thresholds) != required_thresholds:
        raise ValueError("proof thresholds are incomplete")
    parameter_maximum = thresholds["candidate_parameter_count_maximum"]
    score_delta = thresholds["larger_llm_paired_mean_score_delta_minimum"]
    win_rate = thresholds["larger_llm_paired_win_rate_minimum"]
    bootstrap_lower_bound = thresholds[
        "larger_llm_paired_bootstrap_lower_bound_minimum"
    ]
    invalid_maximum = thresholds["invalid_decisions_maximum"]
    if parameter_maximum != 50_000_000:
        raise ValueError("candidate parameter ceiling must be exactly 50000000")
    if (
        not isinstance(score_delta, (int, float))
        or isinstance(score_delta, bool)
        or score_delta <= 0
    ):
        raise ValueError(
            "larger-LLM paired mean score delta threshold must be positive"
        )
    if (
        not isinstance(win_rate, (int, float))
        or isinstance(win_rate, bool)
        or not 0.5 < win_rate <= 1
    ):
        raise ValueError(
            "larger-LLM paired win-rate threshold must be above one half through one"
        )
    if (
        not isinstance(bootstrap_lower_bound, (int, float))
        or isinstance(bootstrap_lower_bound, bool)
        or bootstrap_lower_bound <= 0
    ):
        raise ValueError("larger-LLM bootstrap lower-bound threshold must be positive")
    if (
        not isinstance(invalid_maximum, int)
        or isinstance(invalid_maximum, bool)
        or invalid_maximum < 0
    ):
        raise ValueError("invalid decision threshold must be a non-negative integer")


def validate_teacher_policy_config(config: dict[str, Any]) -> None:
    if config.get("policy_id") != "expectimax-bounded" or config.get("revision") != "1":
        raise ValueError("teacher policy must be expectimax-bounded revision 1")
    if (
        not isinstance(config.get("search_depth"), int)
        or not 1 <= config["search_depth"] <= 3
    ):
        raise ValueError("teacher search_depth must be an integer from 1 through 3")
    if (
        not isinstance(config.get("max_nodes_per_decision"), int)
        or not 4 <= config["max_nodes_per_decision"] <= 4096
    ):
        raise ValueError("teacher max_nodes_per_decision must be from 4 through 4096")
    if (
        not isinstance(config.get("chance_cell_limit"), int)
        or not 1 <= config["chance_cell_limit"] <= CELL_COUNT
    ):
        raise ValueError("teacher chance_cell_limit must be from 1 through 16")
    action_order = config.get("action_order")
    if (
        not isinstance(action_order, list)
        or len(action_order) != len(ACTIONS)
        or set(action_order) != set(ACTIONS)
    ):
        raise ValueError("teacher action_order must contain every action exactly once")
    weights = config.get("weights")
    required_weights = {
        "immediate_score",
        "empty_cells",
        "monotonicity",
        "maximum_tile_corner",
    }
    if (
        not isinstance(weights, dict)
        or set(weights) != required_weights
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in weights.values()
        )
    ):
        raise ValueError(
            f"teacher weights must be integer values for {sorted(required_weights)}"
        )
    spawn = config.get("spawn_distribution")
    if not isinstance(spawn, dict) or set(spawn) != {"2", "4"}:
        raise ValueError(
            "teacher spawn distribution must contain exactly tiles 2 and 4"
        )
    if not all(
        isinstance(probability, (int, float))
        and not isinstance(probability, bool)
        and probability > 0
        for probability in spawn.values()
    ):
        raise ValueError("teacher spawn probabilities must be positive numbers")
    if not math.isclose(sum(spawn.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("teacher spawn probabilities must sum to one")


def validate_teacher_calibration_config(
    config: dict[str, Any], development_config: dict[str, Any]
) -> None:
    validate_evaluation_config(development_config)
    if config.get("schema_version") != "game-2048/teacher-calibration-config/v1":
        raise ValueError("unsupported teacher calibration config schema")
    if config.get("environment_revision") != ENVIRONMENT_REVISION:
        raise ValueError("teacher calibration environment revision mismatch")
    if config.get("benchmark_role") != "algorithmic-diagnostic-only":
        raise ValueError("bounded search must remain an algorithmic diagnostic only")
    expected_ref = {
        "config_id": development_config["config_id"],
        "revision": development_config["revision"],
        "sha256": sha256_json(development_config),
    }
    if config.get("development_config_ref") != expected_ref:
        raise ValueError(
            "teacher calibration development config reference or hash mismatch"
        )
    budgets = config.get("budgets")
    if not isinstance(budgets, dict) or set(budgets) != {
        "max_games",
        "max_moves_per_game",
        "per_move_milliseconds",
    }:
        raise ValueError("teacher calibration budgets are incomplete")
    seeds = development_config["seed_namespaces"]["development"]["fixture_seeds"]
    if budgets["max_games"] != len(seeds):
        raise ValueError(
            "teacher calibration must use exactly the tracked development seeds"
        )
    if not all(
        isinstance(budgets[name], (int, float)) and budgets[name] > 0
        for name in budgets
    ):
        raise ValueError("teacher calibration budgets must be positive")
    validate_teacher_policy_config(config.get("teacher", {}))
    scope = config.get("scope")
    expected_scope = {
        "seed_namespace": "development",
        "frozen_evaluation_allowed": False,
        "trajectory_generation_allowed": False,
        "model_loading_allowed": False,
        "training_allowed": False,
    }
    if scope != expected_scope:
        raise ValueError(
            "teacher calibration scope must remain development-only and no-model"
        )


def make_policy(entry: dict[str, Any], game_seed: int) -> Policy:
    if entry["policy_id"] == "random-legal" and entry["revision"] == "1":
        return RandomLegalPolicy(game_seed)
    if entry["policy_id"] == "greedy-one-ply" and entry["revision"] == "1":
        return GreedyOnePlyPolicy(entry["weights"], entry["action_order"])
    if entry["policy_id"] == "expectimax-bounded" and entry["revision"] == "1":
        return ExpectimaxBoundedPolicy(entry)
    raise ValueError(
        f"unsupported policy {entry.get('policy_id')}@{entry.get('revision')}"
    )


def _policy_ref(policy: Policy) -> dict[str, str]:
    reference = {"policy_id": policy.policy_id, "revision": policy.revision}
    configuration_sha256 = getattr(policy, "configuration_sha256", None)
    if configuration_sha256:
        reference["configuration_sha256"] = configuration_sha256
    return reference


def episode_trace_payload(episode: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "schema_version",
        "environment_revision",
        "seed",
        "policy",
        "max_moves",
        "initial_observation",
        "records",
        "final_observation",
        "terminal_reason",
    )
    return {field: episode[field] for field in fields}


def validate_episode(episode: dict[str, Any]) -> None:
    if (
        episode.get("schema_version") != EPISODE_SCHEMA
        or episode.get("environment_revision") != ENVIRONMENT_REVISION
    ):
        raise ValueError("unsupported episode contract")
    records = episode.get("records")
    if not isinstance(records, list):
        raise ValueError("episode records must be a list")
    if (
        sum(record["score_delta"] for record in records)
        != episode["final_observation"]["score"]
    ):
        raise ValueError("episode reward sum does not equal final score")
    expected_hash = sha256_json(episode_trace_payload(episode))
    if episode.get("trace_hash") != expected_hash:
        raise ValueError("episode trace hash mismatch")
    replayed = replay_episode(episode, validate=False)
    if canonical_bytes(episode_trace_payload(replayed)) != canonical_bytes(
        episode_trace_payload(episode)
    ):
        raise ValueError("episode replay does not reproduce the recorded trajectory")


def replay_episode(episode: dict[str, Any], *, validate: bool = True) -> dict[str, Any]:
    env = Game2048(episode["seed"])
    initial_observation = env.observation()
    records = []
    for expected in episode["records"]:
        failure = expected.get("failure")
        if failure in {"policy-exception", "time-budget-exceeded", "malformed-action"}:
            actual = env.reject_decision(expected.get("raw_action"), failure)
            actual["chosen_action"] = expected.get("chosen_action")
            actual["raw_action"] = expected.get("raw_action")
        else:
            actual = env.step(expected.get("raw_action"))
        records.append(actual)
    if records and not records[-1]["valid"]:
        terminal_reason = f"invalid-decision:{records[-1]['failure']}"
    elif not env.legal_actions:
        terminal_reason = "no-legal-actions"
    elif env.move_count >= episode["max_moves"]:
        terminal_reason = "move-budget-exhausted"
    else:
        raise ValueError(
            "episode ends before a terminal, invalid-decision, or move-budget condition"
        )
    replayed = {
        "schema_version": EPISODE_SCHEMA,
        "environment_revision": ENVIRONMENT_REVISION,
        "seed": episode["seed"],
        "policy": episode["policy"],
        "max_moves": episode["max_moves"],
        "initial_observation": initial_observation,
        "records": records,
        "final_observation": env.observation(),
        "terminal_reason": terminal_reason,
    }
    replayed["trace_hash"] = sha256_json(episode_trace_payload(replayed))
    if validate:
        validate_episode(replayed)
    return replayed


def run_episode(
    policy: Policy,
    game_seed: int,
    *,
    max_moves: int,
    per_move_milliseconds: float,
    clock_ns: Clock = time.perf_counter_ns,
) -> dict[str, Any]:
    env = Game2048(game_seed)
    initial_observation = env.observation()
    records: list[dict[str, Any]] = []
    latencies_ns: list[int] = []
    terminal_reason: str | None = None
    while terminal_reason is None:
        legal = env.legal_actions
        if not legal:
            terminal_reason = "no-legal-actions"
            break
        if env.move_count >= max_moves:
            terminal_reason = "move-budget-exhausted"
            break
        started = clock_ns()
        try:
            action = policy.choose(env.observation(), legal)
            failure = None
        except Exception as exc:  # Candidate adapters fail closed at the boundary.
            action = f"{type(exc).__name__}: {exc}"
            failure = "policy-exception"
        latency_ns = max(0, clock_ns() - started)
        latencies_ns.append(latency_ns)
        if failure:
            record = env.reject_decision(action, failure)
        elif latency_ns > per_move_milliseconds * 1_000_000:
            record = env.reject_decision(action, "time-budget-exceeded")
        elif not isinstance(action, str):
            record = env.reject_decision(action, "malformed-action")
        else:
            record = env.step(action)
        records.append(record)
        if not record["valid"]:
            terminal_reason = f"invalid-decision:{record['failure']}"
        elif record["terminal"]:
            terminal_reason = "no-legal-actions"
    final = env.observation()
    episode = {
        "schema_version": EPISODE_SCHEMA,
        "environment_revision": ENVIRONMENT_REVISION,
        "seed": game_seed,
        "policy": _policy_ref(policy),
        "max_moves": max_moves,
        "initial_observation": initial_observation,
        "records": records,
        "final_observation": final,
        "terminal_reason": terminal_reason,
        "decision_latencies_ns": latencies_ns,
        "metrics": {
            "score": final["score"],
            "maximum_tile": max(final["board"]),
            "reached_2048": max(final["board"]) >= 2048,
            "decisions": len(records),
            "legal_decisions": sum(record["valid"] for record in records),
            "legal_move_rate": sum(record["valid"] for record in records) / len(records)
            if records
            else 1.0,
            "move_count": final["move_count"],
            "terminal_completion": terminal_reason == "no-legal-actions",
        },
    }
    episode["trace_hash"] = sha256_json(episode_trace_payload(episode))
    validate_episode(episode)
    return episode


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile of an empty sequence")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def aggregate_episodes(
    episodes: Sequence[dict[str, Any]], wall_time_ns: int
) -> dict[str, Any]:
    if not episodes:
        raise ValueError("cannot aggregate an empty episode list")
    scores = [episode["metrics"]["score"] for episode in episodes]
    maximum_tiles = [episode["metrics"]["maximum_tile"] for episode in episodes]
    move_counts = [episode["metrics"]["move_count"] for episode in episodes]
    latencies_ns = [
        latency for episode in episodes for latency in episode["decision_latencies_ns"]
    ]
    legal = sum(episode["metrics"]["legal_decisions"] for episode in episodes)
    decisions = sum(episode["metrics"]["decisions"] for episode in episodes)
    latency_seconds = sum(latencies_ns) / 1_000_000_000
    return {
        "games": len(episodes),
        "score": {
            "mean": statistics.fmean(scores),
            "median": statistics.median(scores),
            "p25": percentile(scores, 0.25),
            "p75": percentile(scores, 0.75),
            "minimum": min(scores),
            "maximum": max(scores),
        },
        "maximum_tile": {
            "mean": statistics.fmean(maximum_tiles),
            "median": statistics.median(maximum_tiles),
            "distribution": dict(
                sorted(Counter(str(value) for value in maximum_tiles).items())
            ),
        },
        "reach_2048_rate": sum(value >= 2048 for value in maximum_tiles)
        / len(episodes),
        "legal_move_rate": legal / decisions if decisions else 1.0,
        "invalid_decisions": decisions - legal,
        "move_count": {
            "mean": statistics.fmean(move_counts),
            "median": statistics.median(move_counts),
            "minimum": min(move_counts),
            "maximum": max(move_counts),
        },
        "terminal_completion_rate": sum(
            episode["metrics"]["terminal_completion"] for episode in episodes
        )
        / len(episodes),
        "trace_identity": [
            {"seed": episode["seed"], "sha256": episode["trace_hash"]}
            for episode in episodes
        ],
        "performance": {
            "warm_decision_latency_ms": {
                "p50": percentile(latencies_ns, 0.5) / 1_000_000
                if latencies_ns
                else None,
                "p95": percentile(latencies_ns, 0.95) / 1_000_000
                if latencies_ns
                else None,
            },
            "decisions_per_second": decisions / latency_seconds
            if latency_seconds
            else None,
            "model_load_time_ms": 0,
            "evaluation_wall_time_ms": wall_time_ns / 1_000_000,
        },
    }


def paired_bootstrap(
    deltas: Sequence[float], samples: int, seed: int
) -> dict[str, Any]:
    if not deltas:
        raise ValueError("paired bootstrap requires at least one delta")
    rng = SplitMix64(seed)
    means = []
    for _ in range(samples):
        means.append(
            statistics.fmean(deltas[rng.randbelow(len(deltas))] for _ in deltas)
        )
    return {
        "revision": "1",
        "samples": samples,
        "confidence": 0.95,
        "lower": percentile(means, 0.025),
        "upper": percentile(means, 0.975),
    }


def stable_episode_projection(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed": episode["seed"],
        "score": episode["metrics"]["score"],
        "maximum_tile": episode["metrics"]["maximum_tile"],
        "reached_2048": episode["metrics"]["reached_2048"],
        "legal_move_rate": episode["metrics"]["legal_move_rate"],
        "move_count": episode["metrics"]["move_count"],
        "terminal_completion": episode["metrics"]["terminal_completion"],
        "terminal_reason": episode["terminal_reason"],
        "trace_hash": episode["trace_hash"],
    }


def quality_projection(cohort: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for entry in cohort["entries"]:
        aggregate = dict(entry["aggregate"])
        aggregate.pop("performance")
        entries.append(
            {
                "policy": entry["policy"],
                "episodes": [
                    stable_episode_projection(episode) for episode in entry["episodes"]
                ],
                "aggregate": aggregate,
            }
        )
    return {
        "schema_version": "game-2048/tiny-cohort-fixture/v1",
        "config_id": cohort["config_id"],
        "environment_revision": cohort["environment_revision"],
        "runner_revision": cohort["runner_revision"],
        "policy_adapter_revision": cohort["policy_adapter_revision"],
        "entries": entries,
        "paired_comparisons": cohort["paired_comparisons"],
        "quality_hash": cohort["quality_hash"],
    }


def tracked_fixture_projection(cohort: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "game-2048/tiny-cohort-fixture/v1",
        "config_id": cohort["config_id"],
        "environment_revision": cohort["environment_revision"],
        "runner_revision": cohort["runner_revision"],
        "policy_adapter_revision": cohort["policy_adapter_revision"],
        "quality_hash": cohort["quality_hash"],
        "policies": [
            {
                "policy": entry["policy"],
                "mean_score": entry["aggregate"]["score"]["mean"],
                "reach_2048_rate": entry["aggregate"]["reach_2048_rate"],
                "invalid_decisions": entry["aggregate"]["invalid_decisions"],
                "terminal_completion_rate": entry["aggregate"][
                    "terminal_completion_rate"
                ],
                "games": [
                    stable_episode_projection(episode) for episode in entry["episodes"]
                ],
            }
            for entry in cohort["entries"]
        ],
        "paired_comparisons": cohort["paired_comparisons"],
    }


def _paired_comparison(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    seeds: Sequence[int],
    uncertainty: dict[str, Any],
) -> dict[str, Any]:
    baseline_by_seed = {episode["seed"]: episode for episode in baseline["episodes"]}
    candidate_by_seed = {episode["seed"]: episode for episode in candidate["episodes"]}
    deltas = [
        candidate_by_seed[seed]["metrics"]["score"]
        - baseline_by_seed[seed]["metrics"]["score"]
        for seed in seeds
    ]
    return {
        "baseline": baseline["policy"],
        "candidate": candidate["policy"],
        "score_deltas_by_seed": [
            {"seed": seed, "delta": delta} for seed, delta in zip(seeds, deltas)
        ],
        "paired_mean_score_delta": statistics.fmean(deltas),
        "paired_win_rate": sum(delta > 0 for delta in deltas) / len(deltas),
        "paired_tie_rate": sum(delta == 0 for delta in deltas) / len(deltas),
        "paired_bootstrap_95_ci": paired_bootstrap(
            deltas,
            uncertainty["bootstrap_samples"],
            uncertainty["seed"],
        ),
    }


def run_cohort(
    config: dict[str, Any],
    *,
    policy_configs: Sequence[dict[str, Any]] | None = None,
    cohort_id: str | None = None,
    cohort_revision: str | None = None,
    budgets: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    clock_ns: Clock = time.perf_counter_ns,
) -> dict[str, Any]:
    validate_evaluation_config(config)
    seeds = config["seed_namespaces"]["development"]["fixture_seeds"]
    selected_policies = list(
        policy_configs if policy_configs is not None else config["baselines"]
    )
    selected_budgets = budgets if budgets is not None else config["budgets"]
    if len(seeds) > selected_budgets["max_games"]:
        raise ValueError("selected seeds exceed the cohort max_games budget")
    entries = []
    for policy_config in selected_policies:
        started = clock_ns()
        episodes = []
        for seed in seeds:
            # A throwaway instance warms the same code path without advancing the scored policy stream.
            warm = make_policy(policy_config, seed)
            warm_env = Game2048(seed)
            warm.choose(warm_env.observation(), warm_env.legal_actions)
            policy = make_policy(policy_config, seed)
            episodes.append(
                run_episode(
                    policy,
                    seed,
                    max_moves=selected_budgets["max_moves_per_game"],
                    per_move_milliseconds=selected_budgets["per_move_milliseconds"],
                    clock_ns=clock_ns,
                )
            )
        wall_time_ns = max(0, clock_ns() - started)
        entries.append(
            {
                "policy": _policy_ref(policy),
                "policy_configuration_sha256": sha256_json(policy_config),
                "episodes": episodes,
                "aggregate": aggregate_episodes(episodes, wall_time_ns),
            }
        )
    uncertainty = config["uncertainty"]
    comparisons = [
        _paired_comparison(
            entries[baseline_index], entries[candidate_index], seeds, uncertainty
        )
        for baseline_index in range(len(entries))
        for candidate_index in range(baseline_index + 1, len(entries))
    ]
    cohort = {
        "schema_version": COHORT_SCHEMA,
        "config_id": cohort_id or config["config_id"],
        "config_revision": cohort_revision or config["revision"],
        "development_config_sha256": sha256_json(config),
        "environment_revision": ENVIRONMENT_REVISION,
        "runner_revision": RUNNER_REVISION,
        "policy_adapter_revision": POLICY_ADAPTER_REVISION,
        "seed_namespace": "development",
        "seeds": seeds,
        "entries": entries,
        "paired_comparisons": comparisons,
        "metadata": metadata or {},
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
    }
    projection_without_hash = quality_projection({**cohort, "quality_hash": "pending"})
    projection_without_hash.pop("quality_hash")
    cohort["quality_hash"] = sha256_json(projection_without_hash)
    return cohort


def run_teacher_calibration(
    development_config: dict[str, Any],
    teacher_config: dict[str, Any],
    *,
    clock_ns: Clock = time.perf_counter_ns,
) -> dict[str, Any]:
    validate_teacher_calibration_config(teacher_config, development_config)
    policies = [*development_config["baselines"], teacher_config["teacher"]]
    return run_cohort(
        development_config,
        policy_configs=policies,
        cohort_id=teacher_config["config_id"],
        cohort_revision=teacher_config["revision"],
        budgets=teacher_config["budgets"],
        metadata={
            "teacher_calibration_config_sha256": sha256_json(teacher_config),
            "scope": teacher_config["scope"],
        },
        clock_ns=clock_ns,
    )


def validate_split_disjoint(
    train_examples: Sequence[dict[str, Any]], eval_examples: Sequence[dict[str, Any]]
) -> None:
    def identities(
        examples: Sequence[dict[str, Any]], split: str
    ) -> tuple[set[int], set[str]]:
        seeds: set[int] = set()
        boards: set[str] = set()
        for index, example in enumerate(examples):
            if not isinstance(example, dict) or not isinstance(
                example.get("seed"), int
            ):
                raise ValueError(f"{split}[{index}] must carry an integer seed")
            board = example.get("board")
            if not isinstance(board, list):
                raise ValueError(f"{split}[{index}] must carry a normalized board")
            seeds.add(example["seed"])
            boards.add(board_hash(board))
        return seeds, boards

    train_seeds, train_boards = identities(train_examples, "train")
    eval_seeds, eval_boards = identities(eval_examples, "evaluation")
    seed_overlap = sorted(train_seeds & eval_seeds)
    board_overlap = sorted(train_boards & eval_boards)
    if seed_overlap or board_overlap:
        raise ValueError(
            f"train/evaluation leakage: seeds={seed_overlap}, board_hashes={board_overlap}"
        )


def validate_transition_fixtures(fixtures: dict[str, Any]) -> None:
    if fixtures.get("schema_version") != "game-2048/board-transition-fixtures/v1":
        raise ValueError("unsupported board fixture schema")
    if fixtures.get("environment_revision") != ENVIRONMENT_REVISION:
        raise ValueError("board fixture environment revision mismatch")
    cases = fixtures.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("board transition fixtures must contain at least one case")
    for case in cases:
        actual_board, actual_score = move_without_spawn(case["board"], case["action"])
        if (
            list(actual_board) != case["expected_board_before_spawn"]
            or actual_score != case["expected_score_delta"]
        ):
            raise ValueError(f"board fixture failed: {case.get('id')}")


def qualify_tiny_cohort(
    cohort: dict[str, Any], expected: dict[str, Any] | None = None
) -> None:
    entries = {entry["policy"]["policy_id"]: entry for entry in cohort["entries"]}
    if set(entries) != {"random-legal", "greedy-one-ply"}:
        raise ValueError(
            "tiny qualification requires exactly random and greedy baselines"
        )
    for policy_id, entry in entries.items():
        if entry["aggregate"]["invalid_decisions"] != 0:
            raise ValueError(f"{policy_id} produced an invalid decision")
        if entry["aggregate"]["terminal_completion_rate"] != 1.0:
            raise ValueError(f"{policy_id} did not complete every tiny fixture episode")
        for episode in entry["episodes"]:
            validate_episode(episode)
    if (
        entries["greedy-one-ply"]["aggregate"]["score"]["mean"]
        <= entries["random-legal"]["aggregate"]["score"]["mean"]
    ):
        raise ValueError(
            "greedy-one-ply did not beat random-legal on the tiny development fixture"
        )
    if expected is not None and canonical_bytes(
        tracked_fixture_projection(cohort)
    ) != canonical_bytes(expected):
        raise ValueError(
            "tiny cohort quality/trace output does not match the tracked fixture"
        )


def teacher_fixture_projection(cohort: dict[str, Any]) -> dict[str, Any]:
    projection = tracked_fixture_projection(cohort)
    projection["schema_version"] = "game-2048/teacher-calibration-fixture/v1"
    return projection


def qualify_teacher_calibration(
    cohort: dict[str, Any], expected_report: dict[str, Any] | None = None
) -> None:
    entries = {entry["policy"]["policy_id"]: entry for entry in cohort["entries"]}
    required = {"random-legal", "greedy-one-ply", "expectimax-bounded"}
    if set(entries) != required:
        raise ValueError(f"teacher calibration requires exactly {sorted(required)}")
    for policy_id, entry in entries.items():
        if entry["aggregate"]["invalid_decisions"] != 0:
            raise ValueError(f"{policy_id} produced an invalid decision")
        if entry["aggregate"]["terminal_completion_rate"] != 1.0:
            raise ValueError(f"{policy_id} did not complete every calibration episode")
        for episode in entry["episodes"]:
            validate_episode(episode)
    if expected_report is not None:
        if (
            expected_report.get("schema_version")
            != "game-2048/teacher-calibration-report/v1"
        ):
            raise ValueError("unsupported tracked teacher calibration report")
        if canonical_bytes(teacher_fixture_projection(cohort)) != canonical_bytes(
            expected_report.get("quality")
        ):
            raise ValueError(
                "teacher calibration quality/trace output does not match the tracked report"
            )


def build_teacher_calibration_report(
    cohort: dict[str, Any],
    teacher_config: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    entries = {entry["policy"]["policy_id"]: entry for entry in cohort["entries"]}
    teacher = entries["expectimax-bounded"]["aggregate"]
    comparisons = {
        (item["baseline"]["policy_id"], item["candidate"]["policy_id"]): item
        for item in cohort["paired_comparisons"]
    }
    tradeoffs = []
    for baseline_id in ("random-legal", "greedy-one-ply"):
        baseline = entries[baseline_id]["aggregate"]
        comparison = comparisons[(baseline_id, "expectimax-bounded")]
        teacher_throughput = teacher["performance"]["decisions_per_second"]
        baseline_throughput = baseline["performance"]["decisions_per_second"]
        tradeoffs.append(
            {
                "baseline_policy_id": baseline_id,
                "paired_mean_score_delta": comparison["paired_mean_score_delta"],
                "paired_win_rate": comparison["paired_win_rate"],
                "score_ratio": teacher["score"]["mean"] / baseline["score"]["mean"],
                "throughput_ratio": teacher_throughput / baseline_throughput,
            }
        )
    return {
        "schema_version": "game-2048/teacher-calibration-report/v1",
        "observed_at": observed_at,
        "config_ref": {
            "config_id": teacher_config["config_id"],
            "revision": teacher_config["revision"],
            "sha256": sha256_json(teacher_config),
        },
        "quality": teacher_fixture_projection(cohort),
        "measured_performance": {
            "runtime": cohort["runtime"],
            "policies": [
                {
                    "policy": entry["policy"],
                    "mean_score": entry["aggregate"]["score"]["mean"],
                    **entry["aggregate"]["performance"],
                }
                for entry in cohort["entries"]
            ],
        },
        "tradeoffs": tradeoffs,
        "limitations": [
            "Four tracked development seeds only; this is not frozen-evaluation evidence.",
            "Chance nodes use the configured deterministic cell limit, so the teacher is bounded rather than exact full-width expectimax.",
            "Performance is one local CPU observation and is not a sustained thermal benchmark.",
            "No trajectories, model, or training artifacts were produced.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "qualify"):
        command = subparsers.add_parser(name)
        command.add_argument("--environment-config", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "qualify":
            command.add_argument("--expected", type=Path)
            command.add_argument("--transition-fixtures", type=Path, required=True)
    calibrate = subparsers.add_parser("calibrate-teacher")
    calibrate.add_argument("--environment-config", type=Path, required=True)
    calibrate.add_argument("--config", type=Path, required=True)
    calibrate.add_argument("--teacher-config", type=Path, required=True)
    calibrate.add_argument("--expected-report", type=Path)
    calibrate.add_argument("--output", type=Path, required=True)
    calibrate.add_argument("--report-output", type=Path)
    calibrate.add_argument("--observed-at")
    replay = subparsers.add_parser("replay")
    replay.add_argument("episode", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "replay":
            episode = load_json(args.episode)
            validate_episode(episode)
            print(episode["trace_hash"])
            return 0
        environment_config = load_json(args.environment_config)
        evaluation_config = load_json(args.config)
        validate_environment_config(environment_config)
        validate_evaluation_config(evaluation_config)
        if args.command == "calibrate-teacher":
            teacher_config = load_json(args.teacher_config)
            validate_teacher_calibration_config(teacher_config, evaluation_config)
            cohort = run_teacher_calibration(evaluation_config, teacher_config)
            expected_report = (
                load_json(args.expected_report) if args.expected_report else None
            )
            qualify_teacher_calibration(cohort, expected_report)
            write_json_exclusive(args.output, cohort)
            if args.report_output:
                if not args.observed_at:
                    raise ValueError("--observed-at is required with --report-output")
                write_json_exclusive(
                    args.report_output,
                    build_teacher_calibration_report(
                        cohort, teacher_config, args.observed_at
                    ),
                )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "quality_hash": cohort["quality_hash"],
                        "scores": {
                            entry["policy"]["policy_id"]: entry["aggregate"]["score"][
                                "mean"
                            ]
                            for entry in cohort["entries"]
                        },
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "qualify":
            validate_transition_fixtures(load_json(args.transition_fixtures))
        cohort = run_cohort(evaluation_config)
        if args.command == "qualify":
            expected = load_json(args.expected) if args.expected else None
            qualify_tiny_cohort(cohort, expected)
        write_json_exclusive(args.output, cohort)
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "quality_hash": cohort["quality_hash"],
                    "scores": {
                        entry["policy"]["policy_id"]: entry["aggregate"]["score"][
                            "mean"
                        ]
                        for entry in cohort["entries"]
                    },
                },
                sort_keys=True,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"game-2048: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
