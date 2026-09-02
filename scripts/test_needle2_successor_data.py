from pathlib import Path

from needle2_successor_data import OUT, artifacts


def rows(path: Path) -> list[dict[str, object]]:
    import json

    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_generated_files_match_the_freezer() -> None:
    for path, expected in artifacts().items():
        assert path.read_text() == expected


def test_factorial_arms_are_balanced_and_isolate_the_treatments() -> None:
    plain_standard = rows(OUT / "train-plain-standard.jsonl")
    plain_safety = rows(OUT / "train-plain-safety.jsonl")
    distractor_standard = rows(OUT / "train-distractor-standard.jsonl")
    distractor_safety = rows(OUT / "train-distractor-safety.jsonl")

    assert {len(arm) for arm in (plain_standard, plain_safety, distractor_standard, distractor_safety)} == {216}
    assert [row["query"] for row in plain_standard[:156]] == [
        row["query"] for row in plain_safety[:156]
    ]
    assert [row["query"] for row in plain_standard] == [
        row["query"] for row in distractor_standard
    ]
    assert [row["query"] for row in plain_safety] == [
        row["query"] for row in distractor_safety
    ]
    assert {len(row["tools"]) for row in plain_standard} == {1}
    assert {len(row["tools"]) for row in distractor_standard} == {8}
    assert {len(row["tools"]) for row in distractor_safety} == {8}
    assert all(row["slice"] == "supported" for row in plain_standard)
    assert any(row["slice"] != "supported" for row in plain_safety)


def test_eval_sets_are_disjoint_and_tiny_fixtures_fit_the_gate() -> None:
    train_queries = {
        row["query"]
        for path in OUT.glob("train-*.jsonl")
        for row in rows(path)
    }
    dev = rows(OUT / "public-dev-v2.jsonl")
    sealed = rows(OUT / "sealed-v2.jsonl")
    assert len(dev) == 94
    assert len(sealed) == 36
    assert train_queries.isdisjoint(row["query"] for row in dev)
    assert train_queries.isdisjoint(row["query"] for row in sealed)
    assert {row["query"] for row in dev}.isdisjoint(row["query"] for row in sealed)
    for path in OUT.glob("tiny-*.jsonl"):
        assert 1024 <= path.stat().st_size <= 10 * 1024
