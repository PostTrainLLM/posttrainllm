#!/usr/bin/env python3
"""Tests for shape-based attempt lookup.

Run:
    python3 tests/test_query_attempts.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _script_path(filename):
    """scripts/ is grouped into topic subdirs; find a script in any of them."""
    direct = ROOT / "scripts" / filename
    if direct.exists():
        return direct
    for sub in sorted((ROOT / "scripts").iterdir()):
        if sub.is_dir() and (sub / filename).exists():
            return sub / filename
    raise FileNotFoundError(f"scripts/**/{filename}")


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, _script_path(f"{name}.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qa = load_module("query_attempts")
ATTEMPTS = qa.load_attempts()
PAYLOAD = qa.load_payload()


def test_every_attempt_has_a_kind_from_the_vocabulary():
    kinds = set(PAYLOAD["kind_vocabulary"])
    missing = [a["id"] for a in ATTEMPTS if a.get("kind") not in kinds]
    assert not missing, missing


def test_shape_values_stay_inside_the_declared_vocabulary():
    methods, objectives = set(PAYLOAD["method_vocabulary"]), set(PAYLOAD["objective_vocabulary"])
    for attempt in ATTEMPTS:
        for method in attempt.get("methods") or []:
            assert method in methods, f"{attempt['id']}: {method}"
        objective = attempt.get("objective")
        assert objective is None or objective in objectives, f"{attempt['id']}: {objective}"


def test_the_hygiene_repeat_is_findable_by_shape():
    """The lookup that would have flagged a fourth attempt on the same axis."""
    hits = qa.match(ATTEMPTS, methods=["dpo", "simpo"], objective="output-format")
    assert len(hits) == 3, [h["id"] for h in hits]
    assert all(h["status"] == "failed" for h in hits)


def test_lineage_walks_the_varied_from_chain_oldest_first():
    chain = qa.lineage(ATTEMPTS, "sql-hygiene-dpo-higher-pressure")
    assert [a["id"] for a in chain] == [
        "sql-hygiene-simpo-dpo",
        "sql-hygiene-dpo-refanchored",
        "sql-hygiene-dpo-higher-pressure",
    ]
    assert all(a.get("varied") for a in chain[1:]), "each step must say what changed"


def test_lineage_of_a_root_attempt_is_just_itself():
    assert [a["id"] for a in qa.lineage(ATTEMPTS, "sql-hygiene-simpo-dpo")] == [
        "sql-hygiene-simpo-dpo"
    ]


def test_lineage_terminates_on_a_cycle():
    cyclic = [
        {"id": "a", "varied_from": "b", "status": "failed", "name": "A"},
        {"id": "b", "varied_from": "a", "status": "failed", "name": "B"},
    ]
    assert len(qa.lineage(cyclic, "a")) == 2, "a cycle must not hang the walk"


def test_relevance_outranks_negativity():
    """A barely-related failure must not outrank the direct precedent."""
    ranked = qa.related_to_recipe(
        ATTEMPTS, methods=["sft", "lora"], bases=["flan-t5-small"], objective="typo-repair"
    )
    top_two = {a["id"] for a in ranked[:2]}
    assert top_two == {"autocorrect-tiny-overfit-gate", "autocorrect-ordinary-loss-pilot"}, top_two
    # Among equally-relevant attempts, the failure sorts first.
    same_shape = [a for a in ranked if a.get("objective") == "typo-repair"]
    assert same_shape[0]["status"] == "regressed"


def test_infrastructure_attempts_are_excluded_from_recipe_lookup():
    ranked = qa.related_to_recipe(
        ATTEMPTS, methods=["sft", "lora"], bases=["qwen3-0.6b"], objective="sql-execution"
    )
    assert all(a.get("kind") != "infrastructure" for a in ranked)


def test_an_unmatched_shape_returns_nothing_rather_than_everything():
    assert qa.match(ATTEMPTS, methods=["dpo"], objective="typo-repair") == []
    assert qa.match(ATTEMPTS, bases=["gpt-4"]) == []


def test_empty_query_returns_nothing():
    """A query with no filters must not read as 'everything matched'."""
    assert qa.match(ATTEMPTS) == []


def test_trailing_failures_fire_on_the_output_format_axis():
    """Three straight failures on one objective is the signal to change axis."""
    record = qa.negative_streaks(ATTEMPTS)["output-format"]
    assert record["streak"] == 3
    assert record["tip"] == "sql-hygiene-dpo-higher-pressure"
    warning = qa.streak_warning(ATTEMPTS, "output-format")
    assert "STOP AND RETHINK" in warning
    assert "Composed DPO cannot fix output-format hygiene" in warning


def test_a_solved_axis_does_not_warn():
    """sql-exact-match failed 3 times early, then routing worked. Not a dead axis."""
    record = qa.negative_streaks(ATTEMPTS)["sql-exact-match"]
    assert record["streak"] == 0, "a chain ending in success must not warn"
    assert record["chain_length"] == 7
    assert qa.streak_warning(ATTEMPTS, "sql-exact-match") is None


def test_a_single_failure_is_not_yet_a_pattern():
    assert qa.negative_streaks(ATTEMPTS)["typo-repair"]["streak"] == 1
    assert qa.streak_warning(ATTEMPTS, "typo-repair") is None


def test_two_trailing_failures_caution_three_stop():
    def streak_of(statuses):
        chain = [
            {"id": f"n{i}", "status": s, "objective": "x",
             "varied_from": f"n{i-1}" if i else None, "lesson": "l"}
            for i, s in enumerate(statuses)
        ]
        return qa.streak_warning(chain, "x")

    assert streak_of(["worked"]) is None
    assert streak_of(["worked", "failed"]) is None
    assert "CAUTION" in streak_of(["worked", "failed", "regressed"])
    assert "STOP AND RETHINK" in streak_of(["failed", "failed", "inconclusive"])
    # A success at the tip resets the streak even after many failures.
    assert streak_of(["failed", "failed", "failed", "worked"]) is None


def test_streak_warning_needs_an_objective():
    assert qa.streak_warning(ATTEMPTS, None) is None
    assert qa.streak_warning(ATTEMPTS, "not-a-real-objective") is None


def test_chains_cover_every_shaped_attempt():
    shaped = [a for a in ATTEMPTS if a.get("kind") != "infrastructure"]
    covered = {a["id"] for path in qa.chains(shaped) for a in path}
    assert covered == {a["id"] for a in shaped}


def test_varied_from_targets_all_resolve():
    ids = {a["id"] for a in ATTEMPTS}
    for attempt in ATTEMPTS:
        parent = attempt.get("varied_from")
        assert parent is None or parent in ids, f"{attempt['id']} -> {parent}"


def main() -> int:
    tests = [
        test_every_attempt_has_a_kind_from_the_vocabulary,
        test_shape_values_stay_inside_the_declared_vocabulary,
        test_the_hygiene_repeat_is_findable_by_shape,
        test_lineage_walks_the_varied_from_chain_oldest_first,
        test_lineage_of_a_root_attempt_is_just_itself,
        test_lineage_terminates_on_a_cycle,
        test_relevance_outranks_negativity,
        test_infrastructure_attempts_are_excluded_from_recipe_lookup,
        test_an_unmatched_shape_returns_nothing_rather_than_everything,
        test_empty_query_returns_nothing,
        test_trailing_failures_fire_on_the_output_format_axis,
        test_a_solved_axis_does_not_warn,
        test_a_single_failure_is_not_yet_a_pattern,
        test_two_trailing_failures_caution_three_stop,
        test_streak_warning_needs_an_objective,
        test_chains_cover_every_shaped_attempt,
        test_varied_from_targets_all_resolve,
    ]
    failures = 0
    for test in tests:
        print(f"-- {test.__name__}")
        try:
            test()
            print("  ok")
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}")
            failures += 1
    print()
    if failures:
        print(f"{failures}/{len(tests)} tests failed")
        return 1
    print(f"all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
