#!/usr/bin/env python3
"""Focused stdlib tests for the no-model autocorrect foundation.

Run:
    python3 tests/test_autocorrect_foundation.py
"""

from __future__ import annotations

import copy
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


def load_module():
    path = _script_path("autocorrect_foundation.py")
    spec = importlib.util.spec_from_file_location("autocorrect_foundation", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ac = load_module()
FIXTURES = ROOT / "evals" / "autocorrect"


def test_repository_artifacts_validate():
    assert ac.validate_repository() == []


def test_oracle_scores_perfectly_without_unnecessary_edits():
    report = ac.evaluate(
        ac.load_jsonl(FIXTURES / "eval-v1.jsonl"),
        ac.load_jsonl(FIXTURES / "oracle-predictions-v1.jsonl"),
    )
    assert report["slices"]["natural"]["error_reduction_rate"] == 1.0
    assert report["overall"]["exact_match_rate"] == 1.0
    assert report["slices"]["clean"]["clean_byte_exact_preservation_rate"] == 1.0
    assert report["overall"]["unnecessary_edit_rate"] == 0.0
    assert report["overall"]["protected_span_preservation_rate"] == 1.0


def test_frontier_calibration_is_hash_linked_and_reproducible():
    calibration = ac.load_json(FIXTURES / "frontier-calibration-v1.json")
    predictions_path = FIXTURES / "frontier-predictions-codex-v1.jsonl"
    report = ac.evaluate(
        ac.load_jsonl(FIXTURES / "eval-v1.jsonl"),
        ac.load_jsonl(predictions_path),
    )
    assert calibration["fixture_sha256"] == ac.sha256_file(FIXTURES / "eval-v1.jsonl")
    assert calibration["predictions_sha256"] == ac.sha256_file(predictions_path)
    assert calibration["result"]["rows"] == report["overall"]["rows"] == 18
    assert calibration["result"]["exact_match_rate"] == 1.0
    assert calibration["result"]["clean_byte_exact_preservation_rate"] == 1.0
    assert calibration["result"]["rows_fixed_or_dropped"] == 0


def test_negative_error_reduction_is_not_clamped():
    fixture = [
        {
            "id": "negative",
            "kind": "natural",
            "noisy": "cat",
            "clean": "cut",
            "slices": ["natural"],
            "protected_spans": [],
        }
    ]
    report = ac.evaluate(fixture, [{"id": "negative", "prediction": "zzzz"}])
    assert report["overall"]["baseline_edit_distance"] == 1
    assert report["overall"]["candidate_edit_distance"] == 4
    assert report["overall"]["error_reduction_rate"] == -3.0


def test_zero_error_control_has_null_error_reduction_and_counts_damage():
    fixture = [
        {
            "id": "clean",
            "kind": "clean",
            "noisy": "Keep 42.",
            "clean": "Keep 42.",
            "slices": ["clean"],
            "protected_spans": [],
        }
    ]
    report = ac.evaluate(fixture, [{"id": "clean", "prediction": "Keep 43."}])
    assert report["overall"]["error_reduction_rate"] is None
    assert report["overall"]["clean_byte_exact_preservation_rate"] == 0.0
    assert report["overall"]["unnecessary_edit_rate"] == 1.0
    assert report["overall"]["protected_span_preservation_rate"] == 0.0


def test_prediction_schema_fails_closed():
    fixtures = [
        {
            "id": "one",
            "kind": "clean",
            "noisy": "x",
            "clean": "x",
            "slices": ["clean"],
            "protected_spans": [],
        }
    ]
    bad_cases = (
        [],
        [{"id": "one", "prediction": "x", "explanation": "extra"}],
        [{"id": "one", "prediction": "x"}, {"id": "one", "prediction": "x"}],
        [{"id": "other", "prediction": "x"}],
    )
    for predictions in bad_cases:
        try:
            ac.evaluate(fixtures, predictions)
        except ac.ValidationError:
            pass
        else:
            raise AssertionError(f"strict evaluator accepted {predictions!r}")


def test_each_simulator_family_is_seeded_and_replayable():
    layout = ac.load_layout()
    cases = ac.load_json(FIXTURES / "simulator-cases-v1.json")["cases"]
    assert {case["family"] for case in cases} == set(ac.ERROR_FAMILIES) | {"clean"}
    for case in cases:
        first = ac.simulate_corruption(
            case["clean"],
            row_id=case["id"],
            seed=case["seed"],
            family=case["family"],
            layout=layout,
        )
        second = ac.simulate_corruption(
            case["clean"],
            row_id=case["id"],
            seed=case["seed"],
            family=case["family"],
            layout=layout,
        )
        assert first == second == case["expected"]
        assert ac.apply_trace(first["clean"], first["trace"]) == first["noisy"]


def test_disabled_families_never_fire_and_all_disabled_is_clean():
    fixture = ac.load_json(FIXTURES / "simulator-cases-v1.json")
    for case in fixture["disabled_family_cases"]:
        counts: dict[str, int] = {}
        for index in range(case["samples"]):
            family = ac.choose_weighted_family(
                case["family_weights"], case["seed"], case["id"], index
            )
            counts[family] = counts.get(family, 0) + 1
        assert dict(sorted(counts.items())) == case["expected_counts"]


def test_manifests_are_deterministic_source_first_and_bounded():
    sources = ac.load_jsonl(FIXTURES / "source-documents-v1.jsonl")
    source_by_id = {row["id"]: row for row in sources}
    layout = ac.load_layout()
    for filename in ("tiny-overfit-manifest-v1.json", "pilot-manifest-v1.json"):
        manifest = ac.load_json(FIXTURES / filename)
        rows_a, summary_a = ac.materialize_manifest(manifest, sources, layout)
        rows_b, summary_b = ac.materialize_manifest(manifest, sources, layout)
        assert rows_a == rows_b
        assert summary_a == summary_b == manifest["expected"]
        assert summary_a["rows"] <= 256
        assert all(
            row["split"] == source_by_id[row["source_document_id"]]["split"]
            for row in rows_a
        )
        assert all(row["split"] != "test" for row in rows_a)
    tiny = ac.load_json(FIXTURES / "tiny-overfit-manifest-v1.json")["expected"]
    assert tiny["utf8_bytes"] <= 10 * 1024


def test_overlap_detection_catches_exact_and_normalized_leakage():
    errors: list[str] = []
    source_rows = [
        {"id": "train", "split": "train", "text": "Café   Notes"},
        {"id": "test", "split": "test", "text": "cafe\u0301 notes"},
    ]
    ac._validate_overlap(errors, source_rows, [], [])
    assert any("normalized cross-split overlap" in error for error in errors)

    errors = []
    source_rows[1]["text"] = source_rows[0]["text"]
    ac._validate_overlap(errors, source_rows, [], [])
    assert any("exact cross-split overlap" in error for error in errors)


def test_incomplete_provenance_and_manifest_hash_drift_are_detected():
    protocol = ac.load_json(FIXTURES / "protocol-v1.json")
    taxonomy = ac.load_json(FIXTURES / "taxonomy-v1.json")
    thresholds = ac.load_json(FIXTURES / "thresholds-v1.json")
    source_rows = ac.load_jsonl(FIXTURES / "source-documents-v1.jsonl")
    eval_rows = ac.load_jsonl(FIXTURES / "eval-v1.jsonl")
    sources = ac.load_json(FIXTURES / "sources-v1.json")
    del sources["sources"][0]["license_spdx"]
    errors: list[str] = []
    ac._validate_source_and_eval(
        errors,
        sources,
        source_rows,
        eval_rows,
        protocol,
        taxonomy,
        thresholds,
    )
    assert any("missing provenance fields" in error for error in errors)

    manifest = ac.load_json(FIXTURES / "pilot-manifest-v1.json")
    tampered = copy.deepcopy(manifest)
    tampered["expected"]["dataset_sha256"] = "0" * 64
    _, actual = ac.materialize_manifest(tampered, source_rows, ac.load_layout())
    assert actual != tampered["expected"]


def test_lexical_holdout_is_absent_from_train_and_present_in_test():
    thresholds = ac.load_json(FIXTURES / "thresholds-v1.json")
    source_rows = ac.load_jsonl(FIXTURES / "source-documents-v1.jsonl")
    train_tokens: set[str] = set()
    test_tokens: set[str] = set()
    for row in source_rows:
        target = test_tokens if row["split"] == "test" else train_tokens
        target.update(ac.lexical_tokens(row["text"]))
    for token in thresholds["lexical_holdout_tokens"]:
        assert token in test_tokens
        assert token not in train_tokens


def test_distribution_report_is_reproducible_and_test_fixture_is_frozen():
    eval_rows = ac.load_jsonl(FIXTURES / "eval-v1.jsonl")
    source_rows = ac.load_jsonl(FIXTURES / "source-documents-v1.jsonl")
    report = ac.build_distribution_report(
        eval_rows,
        source_rows,
        ac.load_json(FIXTURES / "corruption-config-v1.json"),
        ac.load_layout(),
    )
    assert report == ac.load_json(FIXTURES / "distribution-report-v1.json")
    assert report["tuning"]["frozen_surface"] == "evals/autocorrect/eval-v1.jsonl"
    assert report["natural_fixture"]["rows"] == 12
    assert report["synthetic_sample"]["rows"] == 256


def test_base_bakeoff_preserves_complete_measured_evidence():
    report = ac.load_json(FIXTURES / "base-bakeoff-v1.json")
    assert report["fixture"]["sha256"] == ac.sha256_file(FIXTURES / "eval-v1.jsonl")
    assert report["selection"]["model_key"] == "flan-t5-small"
    assert report["selection"]["decision"] == "advance-to-training-feasibility"
    assert len(report["candidates"]) == 3
    fixture_ids = [row["id"] for row in ac.load_jsonl(FIXTURES / "eval-v1.jsonl")]
    for candidate in report["candidates"]:
        assert [row["id"] for row in candidate["predictions"]] == fixture_ids
        assert [row["id"] for row in candidate["timing_rows"]] == fixture_ids
        assert [row["id"] for row in candidate["tokenizer_rows"]] == fixture_ids
        rerun = ac.evaluate(
            ac.load_jsonl(FIXTURES / "eval-v1.jsonl"),
            candidate["predictions"],
        )
        assert rerun["overall"] == candidate["evaluation"]["overall"]
        assert rerun["slices"] == candidate["evaluation"]["slices"]


def main() -> int:
    tests = [
        test_repository_artifacts_validate,
        test_oracle_scores_perfectly_without_unnecessary_edits,
        test_frontier_calibration_is_hash_linked_and_reproducible,
        test_negative_error_reduction_is_not_clamped,
        test_zero_error_control_has_null_error_reduction_and_counts_damage,
        test_prediction_schema_fails_closed,
        test_each_simulator_family_is_seeded_and_replayable,
        test_disabled_families_never_fire_and_all_disabled_is_clean,
        test_manifests_are_deterministic_source_first_and_bounded,
        test_overlap_detection_catches_exact_and_normalized_leakage,
        test_incomplete_provenance_and_manifest_hash_drift_are_detected,
        test_lexical_holdout_is_absent_from_train_and_present_in_test,
        test_distribution_report_is_reproducible_and_test_fixture_is_frozen,
        test_base_bakeoff_preserves_complete_measured_evidence,
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
