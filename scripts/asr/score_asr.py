#!/usr/bin/env python3
"""Dependency-free, deterministic ASR scorer for frozen transcript fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


SCHEMA = "posttrainllm.asr-score.v1"


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def normalize(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9' ]+", " ", ascii_text).split()


def edit_counts(reference: list[str], hypothesis: list[str]) -> dict[str, int]:
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    costs = [[0] * columns for _ in range(rows)]
    ops = [[""] * columns for _ in range(rows)]
    for row in range(1, rows):
        costs[row][0] = row
        ops[row][0] = "deletion"
    for column in range(1, columns):
        costs[0][column] = column
        ops[0][column] = "insertion"
    priority = {"equal": 0, "substitution": 1, "deletion": 2, "insertion": 3}
    for row in range(1, rows):
        for column in range(1, columns):
            diagonal_op = (
                "equal"
                if reference[row - 1] == hypothesis[column - 1]
                else "substitution"
            )
            candidates = [
                (costs[row - 1][column - 1] + (diagonal_op != "equal"), diagonal_op),
                (costs[row - 1][column] + 1, "deletion"),
                (costs[row][column - 1] + 1, "insertion"),
            ]
            costs[row][column], ops[row][column] = min(
                candidates, key=lambda item: (item[0], priority[item[1]])
            )
    counts = {"substitutions": 0, "deletions": 0, "insertions": 0}
    row, column = len(reference), len(hypothesis)
    while row or column:
        operation = ops[row][column]
        if operation in {"equal", "substitution"}:
            if operation == "substitution":
                counts["substitutions"] += 1
            row -= 1
            column -= 1
        elif operation == "deletion":
            counts["deletions"] += 1
            row -= 1
        elif operation == "insertion":
            counts["insertions"] += 1
            column -= 1
        else:
            raise ValueError("invalid edit traceback")
    return counts


def repetition_events(words: list[str], maximum_ngram: int = 8) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    index = 0
    while index < len(words) - 1:
        longest = 0
        upper = min(maximum_ngram, (len(words) - index) // 2)
        for width in range(1, upper + 1):
            if words[index : index + width] == words[index + width : index + 2 * width]:
                longest = width
        if longest:
            events.append(
                {
                    "start": index,
                    "width": longest,
                    "phrase": " ".join(words[index : index + longest]),
                }
            )
            index += longest * 2
        else:
            index += 1
    return events


def contains_phrase(words: list[str], phrase: list[str]) -> bool:
    return any(
        words[index : index + len(phrase)] == phrase for index in range(len(words))
    )


def score(fixture: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    references = {item["id"]: item for item in fixture["items"]}
    hypotheses = {item["id"]: item for item in prediction["transcripts"]}
    if references.keys() != hypotheses.keys():
        missing = sorted(references.keys() - hypotheses.keys())
        extra = sorted(hypotheses.keys() - references.keys())
        raise ValueError(
            f"transcript ids do not match fixture; missing={missing}, extra={extra}"
        )

    totals = {"substitutions": 0, "deletions": 0, "insertions": 0}
    reference_words = 0
    proper_noun_hits = 0
    proper_noun_targets = 0
    reference_repetitions = 0
    hypothesis_repetitions = 0
    total_audio_seconds = 0.0
    total_decode_ms = 0.0
    realtime_factors = []
    per_item = []
    for item_id, reference in references.items():
        hypothesis = hypotheses[item_id]
        ref_words = normalize(reference["reference"])
        hyp_words = normalize(hypothesis["text"])
        counts = edit_counts(ref_words, hyp_words)
        errors = sum(counts.values())
        reference_words += len(ref_words)
        for key in totals:
            totals[key] += counts[key]
        ref_repetitions = repetition_events(ref_words)
        hyp_repetitions = repetition_events(hyp_words)
        reference_repetitions += len(ref_repetitions)
        hypothesis_repetitions += len(hyp_repetitions)
        noun_results = []
        for noun in reference.get("proper_nouns", []):
            target = normalize(noun)
            matched = contains_phrase(hyp_words, target)
            proper_noun_targets += 1
            proper_noun_hits += int(matched)
            noun_results.append({"target": noun, "matched": matched})
        audio_seconds = float(hypothesis["audio_seconds"])
        decode_ms = float(hypothesis["decode_ms"])
        if audio_seconds <= 0 or decode_ms <= 0:
            raise ValueError(f"{item_id}: audio_seconds and decode_ms must be positive")
        total_audio_seconds += audio_seconds
        total_decode_ms += decode_ms
        realtime_factors.append(audio_seconds / (decode_ms / 1000))
        per_item.append(
            {
                "id": item_id,
                "reference_words": len(ref_words),
                **counts,
                "word_errors": errors,
                "wer": errors / len(ref_words) if ref_words else None,
                "proper_nouns": noun_results,
                "reference_repetition_events": ref_repetitions,
                "hypothesis_repetition_events": hyp_repetitions,
                "audio_seconds": audio_seconds,
                "decode_ms": decode_ms,
            }
        )
    word_errors = sum(totals.values())
    return {
        "schema_version": SCHEMA,
        "fixture_id": fixture["fixture_id"],
        "model_id": prediction["model_id"],
        "model_revision": prediction["model_revision"],
        "normalization": fixture["normalization"],
        "summary": {
            "items": len(per_item),
            "reference_words": reference_words,
            **totals,
            "word_errors": word_errors,
            "wer": word_errors / reference_words if reference_words else None,
            "proper_noun_hits": proper_noun_hits,
            "proper_noun_targets": proper_noun_targets,
            "proper_noun_accuracy": (
                proper_noun_hits / proper_noun_targets if proper_noun_targets else None
            ),
            "reference_repetition_events": reference_repetitions,
            "hypothesis_repetition_events": hypothesis_repetitions,
            "repetition_regression": hypothesis_repetitions - reference_repetitions,
            "audio_seconds": total_audio_seconds,
            "decode_ms": total_decode_ms,
            "realtime_factor": total_audio_seconds / (total_decode_ms / 1000),
            "median_realtime_factor": median(realtime_factors),
        },
        "per_item": per_item,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
        result = score(fixture, prediction)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"score-asr: {exc}", file=sys.stderr)
        return 1
    rendered = f"{json.dumps(result, indent=2)}\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
