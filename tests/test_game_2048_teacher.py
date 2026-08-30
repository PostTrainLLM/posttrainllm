#!/usr/bin/env python3
"""Focused stdlib tests for the bounded 2048 expectimax teacher."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# scripts/ is grouped into topic subdirs; each is a flat import surface.
for _d in [ROOT / "scripts", *sorted(p for p in (ROOT / "scripts").iterdir() if p.is_dir())]:
    sys.path.insert(0, str(_d))

import game_2048 as game  # noqa: E402

DEVELOPMENT_CONFIG_PATH = ROOT / "configs/game-2048/development-eval-v1.json"
TEACHER_CONFIG_PATH = ROOT / "configs/game-2048/teacher-calibration-v1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def teacher_policy_config() -> dict:
    return load(TEACHER_CONFIG_PATH)["teacher"]


def test_teacher_config_is_versioned_bounded_and_development_only():
    development = load(DEVELOPMENT_CONFIG_PATH)
    calibration = load(TEACHER_CONFIG_PATH)
    game.validate_teacher_calibration_config(calibration, development)
    assert calibration["benchmark_role"] == "algorithmic-diagnostic-only"
    assert calibration["teacher"]["search_depth"] == 2
    assert calibration["teacher"]["max_nodes_per_decision"] == 768
    assert calibration["scope"]["seed_namespace"] == "development"
    assert all(
        calibration["scope"][field] is False
        for field in (
            "frozen_evaluation_allowed",
            "trajectory_generation_allowed",
            "model_loading_allowed",
            "training_allowed",
        )
    )


def test_chance_node_matches_weighted_spawn_expectation_for_one_empty_cell():
    policy = game.ExpectimaxBoundedPolicy(teacher_policy_config())
    board = game.board_tuple([2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2, 4, 8, 16, 32, 0])
    with_two = list(board)
    with_two[-1] = 2
    with_four = list(board)
    with_four[-1] = 4
    expected = 0.9 * policy._leaf_value(tuple(with_two)) + 0.1 * policy._leaf_value(tuple(with_four))
    actual = policy._chance_value(board, 0, game.SearchBudget(16))
    assert abs(actual - expected) < 1e-9


def test_teacher_choice_is_deterministic_and_does_not_mutate_observation():
    env = game.Game2048(2048000000)
    observation = env.observation()
    before = copy.deepcopy(observation)
    first = game.ExpectimaxBoundedPolicy(teacher_policy_config())
    second = game.ExpectimaxBoundedPolicy(teacher_policy_config())
    assert first.choose(observation, observation["legal_actions"]) == second.choose(observation, observation["legal_actions"])
    assert observation == before
    assert first.last_search_stats == second.last_search_stats
    assert first.last_search_stats["node_expansions"] <= first.max_nodes_per_decision


def test_teacher_hard_node_budget_is_enforced():
    config = teacher_policy_config()
    config["max_nodes_per_decision"] = 4
    policy = game.ExpectimaxBoundedPolicy(config)
    env = game.Game2048(9)
    action = policy.choose(env.observation(), env.legal_actions)
    assert action in env.legal_actions
    assert policy.last_search_stats["node_expansions"] <= 4
    assert policy.last_search_stats["budget_exhausted"] is True


def test_teacher_policy_identity_carries_configuration_hash():
    config = teacher_policy_config()
    policy = game.ExpectimaxBoundedPolicy(config)
    episode = game.run_episode(
        policy,
        31,
        max_moves=8,
        per_move_milliseconds=1000,
    )
    assert episode["policy"]["configuration_sha256"] == game.sha256_json(config)
    assert episode["terminal_reason"] == "move-budget-exhausted"
    game.validate_episode(episode)


def test_teacher_config_mutations_fail_closed():
    development = load(DEVELOPMENT_CONFIG_PATH)
    original = load(TEACHER_CONFIG_PATH)
    mutations = []
    wrong_hash = copy.deepcopy(original)
    wrong_hash["development_config_ref"]["sha256"] = "0" * 64
    mutations.append(wrong_hash)
    frozen_scope = copy.deepcopy(original)
    frozen_scope["scope"]["frozen_evaluation_allowed"] = True
    mutations.append(frozen_scope)
    unbounded = copy.deepcopy(original)
    unbounded["teacher"]["max_nodes_per_decision"] = 1_000_000
    mutations.append(unbounded)
    bad_spawn = copy.deepcopy(original)
    bad_spawn["teacher"]["spawn_distribution"] = {"2": 1.0, "4": 0.1}
    mutations.append(bad_spawn)
    capability_anchor = copy.deepcopy(original)
    capability_anchor["benchmark_role"] = "capability-anchor"
    mutations.append(capability_anchor)
    for mutation in mutations:
        try:
            game.validate_teacher_calibration_config(mutation, development)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid teacher calibration mutation was accepted")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"game-2048 teacher tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
