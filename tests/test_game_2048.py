#!/usr/bin/env python3
"""Focused stdlib correctness tests for deterministic 2048 and its baselines."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# scripts/ is grouped into topic subdirs; each is a flat import surface.
for _d in [ROOT / "scripts", *sorted(p for p in (ROOT / "scripts").iterdir() if p.is_dir())]:
    sys.path.insert(0, str(_d))

import game_2048 as game  # noqa: E402

ENV_CONFIG_PATH = ROOT / "configs/game-2048/environment-v1.json"
EVAL_CONFIG_PATH = ROOT / "configs/game-2048/development-eval-v1.json"
BOARD_FIXTURE_PATH = ROOT / "evals/game-2048/fixtures/board-transitions-v1.json"
COHORT_FIXTURE_PATH = ROOT / "evals/game-2048/fixtures/tiny-cohort-v1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class StepClock:
    def __init__(self, step: int = 10_000):
        self.value = 0
        self.step = step

    def __call__(self) -> int:
        value = self.value
        self.value += self.step
        return value


def rotate_clockwise(board):
    source = game.board_tuple(board)
    return tuple(source[(game.BOARD_SIZE - 1 - column) * game.BOARD_SIZE + row] for row in range(4) for column in range(4))


def test_configs_and_tracked_fixtures_validate():
    environment = load(ENV_CONFIG_PATH)
    evaluation = load(EVAL_CONFIG_PATH)
    game.validate_environment_config(environment)
    game.validate_evaluation_config(evaluation)
    game.validate_transition_fixtures(load(BOARD_FIXTURE_PATH))
    assert evaluation["seed_namespaces"]["frozen_evaluation"]["fixture_seeds"] == []
    assert evaluation["seed_namespaces"]["frozen_evaluation"]["seed_material"] == "maintainer-local-not-tracked"


def test_proof_thresholds_and_transition_fixtures_fail_closed():
    evaluation = load(EVAL_CONFIG_PATH)
    for field, invalid in (
        ("frontier_strict_invalid_decisions_maximum", 1),
        ("frontier_constrained_paired_mean_score_delta_over_random_minimum", 0),
        ("frontier_constrained_paired_bootstrap_lower_bound_minimum", 0),
        ("frontier_constrained_paired_win_rate_minimum", 0.5),
        ("frontier_constrained_mean_score_ratio_over_random_minimum", 1.09),
    ):
        damaged = copy.deepcopy(evaluation)
        damaged["benchmark_admission"][field] = invalid
        try:
            game.validate_evaluation_config(damaged)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid benchmark admission threshold was accepted: {field}")
    for field, invalid in (
        ("candidate_parameter_count_maximum", 50_000_001),
        ("larger_llm_paired_mean_score_delta_minimum", 0),
        ("larger_llm_paired_win_rate_minimum", 0.5),
        ("larger_llm_paired_bootstrap_lower_bound_minimum", 0),
        ("invalid_decisions_maximum", 0.5),
    ):
        damaged = copy.deepcopy(evaluation)
        damaged["proof_thresholds"][field] = invalid
        try:
            game.validate_evaluation_config(damaged)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid proof threshold was accepted: {field}")
    empty_fixtures = load(BOARD_FIXTURE_PATH)
    empty_fixtures["cases"] = []
    try:
        game.validate_transition_fixtures(empty_fixtures)
    except ValueError as exc:
        assert "at least one case" in str(exc)
    else:
        raise AssertionError("empty transition fixtures were accepted")


def test_golden_merges_and_no_double_merge():
    cases = load(BOARD_FIXTURE_PATH)["cases"]
    for case in cases:
        board, score = game.move_without_spawn(case["board"], case["action"])
        assert list(board) == case["expected_board_before_spawn"], case["id"]
        assert score == case["expected_score_delta"], case["id"]
    assert game.merge_line([2, 2, 4, 0]) == ((4, 4, 0, 0), 4)
    assert game.merge_line([4, 4, 4, 4]) == ((8, 8, 0, 0), 16)


def test_character_observation_is_compact_text_not_visual_input():
    observation = {
        "board": [0, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 0, 0, 0, 0],
        "score": 4096,
        "move_count": 17,
        "legal_actions": ["up", "left"],
    }
    encoded = game.serialize_character_observation(observation)
    assert encoded == "B=0123456789ab0000;S=4096;M=17;L=UL"
    assert len(encoded.split(";", 1)[0].removeprefix("B=")) == game.CELL_COUNT
    assert game.parse_character_action(" L\n") == "left"
    for invalid in ("", "LEFT", "L.", "UL"):
        try:
            game.parse_character_action(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid character action was accepted: {invalid!r}")


def test_directional_rotation_equivalence():
    board = game.board_tuple([2, 0, 2, 4, 4, 4, 8, 8, 0, 2, 2, 4, 16, 0, 16, 16])
    action_rotation = {"up": "right", "right": "down", "down": "left", "left": "up"}
    rotated = rotate_clockwise(board)
    for action, rotated_action in action_rotation.items():
        result, score = game.move_without_spawn(board, action)
        rotated_result, rotated_score = game.move_without_spawn(rotated, rotated_action)
        assert rotate_clockwise(result) == rotated_result
        assert score == rotated_score


def test_legal_move_spawns_exactly_once():
    env = game.Game2048(11)
    env.board = game.board_tuple([2, 2, 0, 0] + [0] * 12)
    env.score = 0
    env.move_count = 0
    moved, expected_score = game.move_without_spawn(env.board, "left")
    record = env.step("left")
    assert record["valid"] is True
    assert record["score_delta"] == expected_score == 4
    assert record["spawn"]["value"] in (2, 4)
    spawned_index = record["spawn"]["index"]
    assert moved[spawned_index] == 0
    expected = list(moved)
    expected[spawned_index] = record["spawn"]["value"]
    assert list(env.board) == expected
    assert env.move_count == 1


def test_invalid_and_noop_actions_do_not_mutate_or_advance_rng():
    env = game.Game2048(22)
    env.board = game.board_tuple([2, 0, 0, 0] + [0] * 12)
    before = env.observation()
    state = env.rng_state
    for action, failure in (("left", "no-state-change"), ("diagonal", "unknown-action"), (None, "unknown-action")):
        record = env.step(action)
        assert record["valid"] is False
        assert record["failure"] == failure
        assert env.observation() == before
        assert env.rng_state == state
        assert record["environment_rng_state_before"] == record["environment_rng_state_after"] == state


def test_legal_actions_and_terminal_state_are_exact():
    live = [2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2, 4, 8, 16, 32, 32]
    dead = [2, 4, 2, 4, 4, 2, 4, 2, 2, 4, 2, 4, 4, 2, 4, 2]
    assert game.legal_actions_for(live)
    assert game.legal_actions_for(dead) == ()
    env = game.Game2048(1)
    env.board = game.board_tuple(live)
    assert env.terminal is False
    env.board = game.board_tuple(dead)
    assert env.terminal is True


def test_fixed_seed_reset_and_replay_are_byte_identical():
    first = game.run_episode(
        game.RandomLegalPolicy(2048000000),
        2048000000,
        max_moves=2500,
        per_move_milliseconds=25,
        clock_ns=StepClock(),
    )
    second = game.run_episode(
        game.RandomLegalPolicy(2048000000),
        2048000000,
        max_moves=2500,
        per_move_milliseconds=25,
        clock_ns=StepClock(),
    )
    assert game.canonical_bytes(first) == game.canonical_bytes(second)
    replayed = game.replay_episode(first)
    assert game.canonical_bytes(game.episode_trace_payload(first)) == game.canonical_bytes(game.episode_trace_payload(replayed))
    assert first["trace_hash"] == replayed["trace_hash"]


def test_policy_randomness_cannot_perturb_environment_randomness():
    left = game.Game2048(77)
    right = game.Game2048(77)
    policy_rng = game.SplitMix64(game.derive_stream_seed(77, "policy/test/v1"))
    for _ in range(20):
        assert left.observation() == right.observation()
        legal = left.legal_actions
        if not legal:
            break
        action = legal[0]
        policy_rng.next_u64()
        policy_rng.next_u64()
        assert left.step(action) == right.step(action)


def test_reward_sum_trace_tamper_and_overwrite_refusal():
    episode = game.run_episode(
        game.RandomLegalPolicy(9),
        9,
        max_moves=2500,
        per_move_milliseconds=25,
        clock_ns=StepClock(),
    )
    game.validate_episode(episode)
    damaged = copy.deepcopy(episode)
    damaged["records"][0]["score_delta"] += 1
    try:
        game.validate_episode(damaged)
    except ValueError as exc:
        assert "reward sum" in str(exc)
    else:
        raise AssertionError("tampered reward was accepted")
    damaged = copy.deepcopy(episode)
    damaged["terminal_reason"] = "move-budget-exhausted"
    damaged["trace_hash"] = game.sha256_json(game.episode_trace_payload(damaged))
    try:
        game.validate_episode(damaged)
    except ValueError as exc:
        assert "replay" in str(exc)
    else:
        raise AssertionError("tampered terminal reason was accepted")
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "episode.json"
        game.write_json_exclusive(output, episode)
        try:
            game.write_json_exclusive(output, episode)
        except ValueError as exc:
            assert "refusing to overwrite" in str(exc)
        else:
            raise AssertionError("episode overwrite was accepted")


def test_split_validation_fails_closed_on_seed_or_board_overlap():
    board_a = [2, 0, 0, 0] + [0] * 12
    board_b = [0, 2, 0, 0] + [0] * 12
    game.validate_split_disjoint([{"seed": 1, "board": board_a}], [{"seed": 2, "board": board_b}])
    for evaluation in (
        [{"seed": 1, "board": board_b}],
        [{"seed": 2, "board": board_a}],
    ):
        try:
            game.validate_split_disjoint([{"seed": 1, "board": board_a}], evaluation)
        except ValueError as exc:
            assert "leakage" in str(exc)
        else:
            raise AssertionError("leaking split was accepted")


def test_policy_boundary_records_unknown_malformed_and_timeout():
    class BadPolicy:
        policy_id = "bad"
        revision = "1"

        def __init__(self, action):
            self.action = action

        def choose(self, observation, legal_actions):
            del observation, legal_actions
            return self.action

    unknown = game.run_episode(BadPolicy("diagonal"), 3, max_moves=10, per_move_milliseconds=25, clock_ns=StepClock())
    malformed = game.run_episode(BadPolicy(["left"]), 3, max_moves=10, per_move_milliseconds=25, clock_ns=StepClock())
    timeout = game.run_episode(BadPolicy("left"), 3, max_moves=10, per_move_milliseconds=0.001, clock_ns=StepClock())
    assert unknown["terminal_reason"] == "invalid-decision:unknown-action"
    assert malformed["terminal_reason"] == "invalid-decision:malformed-action"
    assert timeout["terminal_reason"] == "invalid-decision:time-budget-exceeded"
    for episode in (unknown, malformed, timeout):
        assert episode["metrics"]["legal_move_rate"] == 0.0
        assert episode["initial_observation"] == episode["final_observation"]
        game.validate_episode(episode)


def test_paired_runner_is_deterministic_with_injected_clock():
    config = load(EVAL_CONFIG_PATH)
    first = game.run_cohort(config, clock_ns=StepClock())
    second = game.run_cohort(config, clock_ns=StepClock())
    assert game.canonical_bytes(first) == game.canonical_bytes(second)
    comparison = first["paired_comparisons"][0]
    assert [row["seed"] for row in comparison["score_deltas_by_seed"]] == config["seed_namespaces"]["development"]["fixture_seeds"]
    assert comparison["paired_mean_score_delta"] > 0
    game.qualify_tiny_cohort(first, load(COHORT_FIXTURE_PATH))


def test_cli_qualifies_and_refuses_to_overwrite():
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "cohort.json"
        command = [
            sys.executable,
            str(ROOT / "scripts/games/game_2048.py"),
            "qualify",
            "--environment-config",
            str(ENV_CONFIG_PATH),
            "--config",
            str(EVAL_CONFIG_PATH),
            "--transition-fixtures",
            str(BOARD_FIXTURE_PATH),
            "--expected",
            str(COHORT_FIXTURE_PATH),
            "--output",
            str(output),
        ]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        result = load(output)
        assert result["schema_version"] == game.COHORT_SCHEMA
        assert result["runtime"]["implementation"]
        for entry in result["entries"]:
            performance = entry["aggregate"]["performance"]
            assert performance["warm_decision_latency_ms"]["p50"] is not None
            assert performance["warm_decision_latency_ms"]["p95"] is not None
            assert performance["decisions_per_second"] is not None
            assert performance["evaluation_wall_time_ms"] > 0
            assert performance["model_load_time_ms"] == 0
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        assert second.returncode == 1
        assert "refusing to overwrite" in second.stderr


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"game-2048 tests: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
