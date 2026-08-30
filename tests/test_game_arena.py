#!/usr/bin/env python3
"""Focused no-model checks for the extensible game arena."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# scripts/ is grouped into topic subdirs; each is a flat import surface.
for _d in [
    ROOT / "scripts",
    *sorted(p for p in (ROOT / "scripts").iterdir() if p.is_dir()),
]:
    sys.path.insert(0, str(_d))

import game_arena as arena  # noqa: E402


def rating_config(samples: int = 128) -> dict:
    return {
        "base": 1500,
        "scale": 400,
        "prior_standard_deviation": 400,
        "bootstrap_samples": samples,
        "bootstrap_seed": 17,
    }


def head_gate(minimum: int = 1) -> dict:
    return {
        "minimum_total_matches": minimum,
        "minimum_matches_per_policy": minimum,
        "maximum_forfeit_rate": 0.1,
        "require_connected_pool": True,
        "require_color_balance": True,
    }


def matches() -> list[dict]:
    return [
        {
            "white_policy_id": "a",
            "black_policy_id": "b",
            "white_score": 1.0,
            "forfeit": False,
        },
        {
            "white_policy_id": "b",
            "black_policy_id": "a",
            "white_score": 0.0,
            "forfeit": False,
        },
        {
            "white_policy_id": "a",
            "black_policy_id": "b",
            "white_score": 0.5,
            "forfeit": False,
        },
        {
            "white_policy_id": "b",
            "black_policy_id": "a",
            "white_score": 0.5,
            "forfeit": False,
        },
    ]


def test_elo_orders_ahead_and_centers_pool():
    result = arena.fit_arena_elo(["a", "b"], matches(), rating_config(), head_gate())
    ratings = {row["policy_id"]: row for row in result["ratings"]}
    assert ratings["a"]["rating"] > ratings["b"]["rating"]
    assert abs((ratings["a"]["rating"] + ratings["b"]["rating"]) / 2 - 1500) < 0.1
    assert result["qualification"]["qualified"] is True
    assert result["human_elo_equivalence"] == "unknown-and-not-claimed"


def test_qualification_is_independent_from_estimate():
    result = arena.fit_arena_elo(["a", "b"], matches(), rating_config(), head_gate(30))
    assert all(isinstance(row["rating"], float) for row in result["ratings"])
    assert all(row["status"] == "unrated" for row in result["ratings"])
    assert "minimum_total_matches" in result["qualification"]["unmet"]


def test_forfeit_is_counted_and_blocks_quality_gate():
    rows = matches()
    rows[0] = {**rows[0], "forfeit": True}
    result = arena.fit_arena_elo(["a", "b"], rows, rating_config(), head_gate())
    assert result["forfeits"] == 1
    assert result["qualification"]["checks"]["maximum_forfeit_rate"] is False


def test_disconnected_pool_is_visible():
    rows = matches() + [
        {
            "white_policy_id": "c",
            "black_policy_id": "d",
            "white_score": 1.0,
            "forfeit": False,
        },
        {
            "white_policy_id": "d",
            "black_policy_id": "c",
            "white_score": 0.0,
            "forfeit": False,
        },
    ]
    result = arena.fit_arena_elo(
        ["a", "b", "c", "d"], rows, rating_config(), head_gate()
    )
    assert result["connected_pool"] is False
    assert result["qualification"]["checks"]["connected_pool"] is False


def test_paired_score_never_emits_elo():
    trials = [
        {
            "policy_id": "model",
            "baseline_policy_id": "random",
            "policy_score": 20,
            "baseline_score": 10,
        },
        {
            "policy_id": "model",
            "baseline_policy_id": "random",
            "policy_score": 8,
            "baseline_score": 10,
        },
    ]
    result = arena.score_paired_trials(
        trials,
        {"model": {"complete": True, "status": "test", "provider_failures": 0}},
        rating_config(),
        {"minimum_complete_pairs_per_policy": 2, "require_complete_source": True},
    )
    assert result["elo"] is None
    assert result["entries"][0]["paired_mean_delta"] == 4
    assert result["entries"][0]["qualification"]["qualified"] is True


def test_candidate_report_is_deterministic_and_honest():
    config = ROOT / "configs/game-arena/candidate-v1.json"
    first = arena.build_report(config, ROOT)
    second = arena.build_report(config, ROOT)
    assert first == second
    assert [game["competition_family"] for game in first["games"]] == [
        "head-to-head",
        "paired-score",
    ]
    chess = first["games"][0]["result"]
    assert chess["matches"] == 4
    assert chess["forfeits"] == 2
    assert chess["qualification"]["qualified"] is False
    assert all(row["status"] == "unrated" for row in chess["ratings"])
    score = first["games"][1]["result"]
    assert score["elo"] is None
    assert first["claims"]["model_calls_performed"] == 0


def test_current_chess_diagnostic_does_not_masquerade_as_fide():
    report = arena.build_report(ROOT / "configs/game-arena/candidate-v1.json", ROOT)
    chess = report["games"][0]["result"]
    assert chess["rating_name"] == "Arena Elo"
    assert chess["human_elo_equivalence"] == "unknown-and-not-claimed"
    assert set(chess["qualification"]["unmet"]) >= {
        "minimum_total_matches",
        "minimum_matches_per_policy",
        "maximum_forfeit_rate",
    }


def test_duplicate_chess_pair_is_rejected():
    source_path = ROOT / "evals/chess/qwen4b-v-qwen9b-paired-games-v1.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["games"].append(deepcopy(source["games"][0]))
    try:
        arena.adapt_chess(Path(source_path.name), source)
    except ValueError as error:
        assert "duplicate match id" in str(error)
    else:
        raise AssertionError("duplicate chess evidence must fail closed")


def test_invalid_match_result_is_rejected():
    invalid = matches()
    invalid[0] = {**invalid[0], "white_score": 0.25}
    try:
        arena.fit_arena_elo(["a", "b"], invalid, rating_config(), head_gate())
    except ValueError as error:
        assert "win, draw, or loss" in str(error)
    else:
        raise AssertionError("malformed match result must fail closed")


def test_adapter_family_mismatch_is_rejected():
    config = json.loads(
        (ROOT / "configs/game-arena/candidate-v1.json").read_text(encoding="utf-8")
    )
    config["games"][0]["competition_family"] = "paired-score"
    try:
        arena.validate_config(config)
    except ValueError as error:
        assert "incompatible" in str(error)
    else:
        raise AssertionError("semantically incompatible adapter must fail closed")


if __name__ == "__main__":
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"game arena tests: {len(tests)} passed")
