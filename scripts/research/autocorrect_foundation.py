#!/usr/bin/env python3
"""No-model foundation for the Mac-local autocorrect specialist.

This stdlib-only module owns the frozen evaluator, deterministic keyboard
corruption simulator, source-first split/leakage checks, manifest verification,
and natural-vs-synthetic distribution report. It does not load a model, access
the network, install anything, compile, train, or benchmark.

Commands:

    python3 scripts/research/autocorrect_foundation.py validate
    python3 scripts/research/autocorrect_foundation.py evaluate --predictions FILE
    python3 scripts/research/autocorrect_foundation.py inspect
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "evals" / "autocorrect"
ERROR_FAMILIES = (
    "substitution",
    "insertion",
    "omission",
    "transposition",
    "repetition",
    "space",
    "shift_case",
)
REQUIRED_SOURCE_FIELDS = (
    "id",
    "title",
    "source_type",
    "license_spdx",
    "license_path",
    "revision",
    "revision_kind",
    "retrieval_method",
    "allowed_uses",
    "exclusions",
)


class ValidationError(ValueError):
    """Raised for a strict fixture, prediction, or manifest failure."""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValidationError(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def canonical_jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_overlap_key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(text.split())


def lexical_tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", text, re.UNICODE)
    }


def deterministic_int(seed: int, *parts: object) -> int:
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def deterministic_choice(values: list[Any], seed: int, *parts: object) -> Any:
    if not values:
        raise ValidationError(f"no deterministic choice available for {parts!r}")
    return values[deterministic_int(seed, *parts) % len(values)]


def load_layout(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or FIXTURE_DIR / "keyboard-mac-us-ansi-v1.json")


def _layout_maps(
    layout: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_character: dict[str, dict[str, Any]] = {}
    neighbors: dict[str, list[dict[str, Any]]] = {}
    keys = layout["keys"]
    for key in keys:
        by_character[key["unshifted"]] = key
        by_character[key["shifted"]] = key
    for key in keys:
        adjacent = []
        for candidate in keys:
            if candidate["id"] == key["id"]:
                continue
            dx = float(candidate["x"]) - float(key["x"])
            dy = float(candidate["y"]) - float(key["y"])
            if abs(dy) <= 1.0 and math.sqrt(dx * dx + dy * dy) <= 1.25:
                adjacent.append(candidate)
        neighbors[key["id"]] = sorted(adjacent, key=lambda item: item["id"])
    return by_character, neighbors


def _replacement_for_key(key: dict[str, Any], original: str) -> str:
    if original == key["shifted"] or (original.isalpha() and original.isupper()):
        return key["shifted"]
    return key["unshifted"]


def choose_weighted_family(
    weights: dict[str, int | float], seed: int, *parts: object
) -> str:
    scaled: list[tuple[str, int]] = []
    total = 0
    for family in ERROR_FAMILIES:
        weight = weights.get(family, 0)
        if not isinstance(weight, (int, float)) or weight < 0:
            raise ValidationError(f"invalid weight for {family}: {weight!r}")
        units = int(round(float(weight) * 1000))
        if units:
            total += units
            scaled.append((family, total))
    if total == 0:
        return "clean"
    ticket = deterministic_int(seed, *parts, "family") % total
    for family, ceiling in scaled:
        if ticket < ceiling:
            return family
    raise AssertionError("weighted selection fell through")


def simulate_corruption(
    clean: str,
    *,
    row_id: str,
    seed: int,
    family: str | None = None,
    layout: dict[str, Any] | None = None,
    weights: dict[str, int | float] | None = None,
) -> dict[str, Any]:
    """Apply exactly one deterministic corruption, or a clean control."""

    layout = layout or load_layout()
    by_character, neighbors = _layout_maps(layout)
    if family is None:
        if weights is None:
            raise ValidationError("family or weights is required")
        family = choose_weighted_family(weights, seed, row_id)
    if family == "clean":
        return {"clean": clean, "noisy": clean, "family": "clean", "trace": []}
    if family not in ERROR_FAMILIES:
        raise ValidationError(f"unsupported corruption family: {family}")

    start: int
    end: int
    replacement: str
    mode = family

    if family == "substitution":
        positions = [
            index
            for index, char in enumerate(clean)
            if char in by_character and neighbors[by_character[char]["id"]]
        ]
        start = deterministic_choice(positions, seed, row_id, family, "position")
        end = start + 1
        original_key = by_character[clean[start]]
        replacement_key = deterministic_choice(
            neighbors[original_key["id"]], seed, row_id, family, "neighbor"
        )
        replacement = _replacement_for_key(replacement_key, clean[start])
    elif family == "insertion":
        positions = [index for index, char in enumerate(clean) if char in by_character]
        anchor = deterministic_choice(positions, seed, row_id, family, "position")
        original_key = by_character[clean[anchor]]
        replacement_key = deterministic_choice(
            neighbors[original_key["id"]], seed, row_id, family, "neighbor"
        )
        start = anchor + (deterministic_int(seed, row_id, family, "side") % 2)
        end = start
        replacement = _replacement_for_key(replacement_key, clean[anchor])
    elif family == "omission":
        positions = [index for index, char in enumerate(clean) if char in by_character]
        start = deterministic_choice(positions, seed, row_id, family, "position")
        end = start + 1
        replacement = ""
    elif family == "transposition":
        positions = [
            index
            for index in range(len(clean) - 1)
            if not clean[index].isspace()
            and not clean[index + 1].isspace()
            and clean[index] != clean[index + 1]
        ]
        start = deterministic_choice(positions, seed, row_id, family, "position")
        end = start + 2
        replacement = clean[start + 1] + clean[start]
    elif family == "repetition":
        positions = [
            index
            for index, char in enumerate(clean)
            if char in by_character and not char.isspace()
        ]
        start = deterministic_choice(positions, seed, row_id, family, "position")
        end = start + 1
        replacement = clean[start] * 2
    elif family == "space":
        removable = [index for index, char in enumerate(clean) if char == " "]
        insertable = [
            index
            for index in range(1, len(clean))
            if not clean[index - 1].isspace() and not clean[index].isspace()
        ]
        use_removal = bool(removable) and (
            not insertable or deterministic_int(seed, row_id, family, "mode") % 2 == 0
        )
        if use_removal:
            start = deterministic_choice(removable, seed, row_id, family, "remove")
            end = start + 1
            replacement = ""
            mode = "space_omission"
        else:
            start = deterministic_choice(insertable, seed, row_id, family, "insert")
            end = start
            replacement = " "
            mode = "space_insertion"
    else:  # shift_case
        positions = [
            index
            for index, char in enumerate(clean)
            if char in by_character
            and by_character[char]["unshifted"] != by_character[char]["shifted"]
        ]
        start = deterministic_choice(positions, seed, row_id, family, "position")
        end = start + 1
        key = by_character[clean[start]]
        replacement = (
            key["unshifted"] if clean[start] == key["shifted"] else key["shifted"]
        )

    source_text = clean[start:end]
    noisy = clean[:start] + replacement + clean[end:]
    trace = {
        "family": family,
        "mode": mode,
        "source_start": start,
        "source_end": end,
        "source_text": source_text,
        "replacement_text": replacement,
        "noisy_start": start,
        "noisy_end": start + len(replacement),
    }
    return {"clean": clean, "noisy": noisy, "family": family, "trace": [trace]}


def apply_trace(clean: str, trace: list[dict[str, Any]]) -> str:
    value = clean
    for edit in sorted(trace, key=lambda item: item["source_start"], reverse=True):
        start = edit["source_start"]
        end = edit["source_end"]
        if value[start:end] != edit["source_text"]:
            raise ValidationError("trace source text does not match clean text")
        value = value[:start] + edit["replacement_text"] + value[end:]
    return value


def levenshtein_distance(source: str, target: str) -> int:
    if len(source) < len(target):
        source, target = target, source
    previous = list(range(len(target) + 1))
    for source_index, source_char in enumerate(source, 1):
        current = [source_index]
        for target_index, target_char in enumerate(target, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[target_index] + 1,
                    previous[target_index - 1] + (source_char != target_char),
                )
            )
        previous = current
    return previous[-1]


def edit_operations(source: str, target: str) -> list[tuple[str, int, int, str]]:
    """Return one deterministic minimum Levenshtein edit script."""

    rows = len(source) + 1
    columns = len(target) + 1
    matrix = [[0] * columns for _ in range(rows)]
    for index in range(rows):
        matrix[index][0] = index
    for index in range(columns):
        matrix[0][index] = index
    for i in range(1, rows):
        for j in range(1, columns):
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + (source[i - 1] != target[j - 1]),
            )

    operations: list[tuple[str, int, int, str]] = []
    i, j = len(source), len(target)
    while i or j:
        if (
            i
            and j
            and source[i - 1] == target[j - 1]
            and matrix[i][j] == matrix[i - 1][j - 1]
        ):
            i -= 1
            j -= 1
            continue
        if i and j and matrix[i][j] == matrix[i - 1][j - 1] + 1:
            operations.append(("substitution", i - 1, i, target[j - 1]))
            i -= 1
            j -= 1
        elif i and matrix[i][j] == matrix[i - 1][j] + 1:
            operations.append(("deletion", i - 1, i, ""))
            i -= 1
        elif j and matrix[i][j] == matrix[i][j - 1] + 1:
            operations.append(("insertion", i, i, target[j - 1]))
            j -= 1
        else:
            raise AssertionError("edit-script backtrack failed")
    return list(reversed(operations))


def automatic_protected_spans(text: str) -> list[dict[str, str]]:
    spans: list[dict[str, str]] = []
    patterns = (
        ("url", r"https?://[^\s]+"),
        ("code", r"`[^`\n]+`"),
        ("number", r"(?<!\w)\d[\d,:.-]*(?!\w)"),
    )
    for span_type, pattern in patterns:
        for match in re.finditer(pattern, text):
            spans.append({"type": span_type, "text": match.group(0)})
    return spans


def protected_spans(row: dict[str, Any]) -> list[dict[str, str]]:
    spans = automatic_protected_spans(row["clean"])
    spans.extend(row.get("protected_spans", []))
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for span in spans:
        unique[(span["type"], span["text"])] = span
    return list(unique.values())


def _aggregate_metrics(paired: list[tuple[dict[str, Any], str]]) -> dict[str, Any]:
    baseline_distance = 0
    candidate_distance = 0
    clean_characters = 0
    exact = 0
    clean_rows = 0
    clean_preserved = 0
    candidate_edits = 0
    unnecessary_edits = 0
    protected_total = 0
    protected_preserved = 0

    for row, prediction in paired:
        noisy = row["noisy"]
        clean = row["clean"]
        baseline = levenshtein_distance(noisy, clean)
        candidate = levenshtein_distance(prediction, clean)
        if baseline:
            baseline_distance += baseline
            candidate_distance += candidate
        clean_characters += max(len(clean), 1)
        exact += int(prediction == clean)
        if row["kind"] == "clean":
            clean_rows += 1
            clean_preserved += int(prediction.encode("utf-8") == clean.encode("utf-8"))

        reference_ops = set(edit_operations(noisy, clean))
        prediction_ops = edit_operations(noisy, prediction)
        candidate_edits += len(prediction_ops)
        unnecessary_edits += sum(
            operation not in reference_ops for operation in prediction_ops
        )

        for span in protected_spans(row):
            protected_total += 1
            expected_count = clean.count(span["text"])
            protected_preserved += int(prediction.count(span["text"]) == expected_count)

    rows = len(paired)
    return {
        "rows": rows,
        "error_rows": sum(row["kind"] != "clean" for row, _ in paired),
        "baseline_edit_distance": baseline_distance,
        "candidate_edit_distance": candidate_distance,
        "error_reduction_rate": (
            1.0 - candidate_distance / baseline_distance if baseline_distance else None
        ),
        "exact_match_rate": exact / rows if rows else None,
        "residual_character_error_rate": (
            sum(
                levenshtein_distance(prediction, row["clean"])
                for row, prediction in paired
            )
            / clean_characters
            if rows
            else None
        ),
        "clean_byte_exact_preservation_rate": (
            clean_preserved / clean_rows if clean_rows else None
        ),
        "unnecessary_edit_rate": (
            unnecessary_edits / candidate_edits if candidate_edits else 0.0
        ),
        "protected_span_preservation_rate": (
            protected_preserved / protected_total if protected_total else None
        ),
        "counts": {
            "clean_rows": clean_rows,
            "clean_rows_preserved": clean_preserved,
            "candidate_edits": candidate_edits,
            "unnecessary_edits": unnecessary_edits,
            "protected_spans": protected_total,
            "protected_spans_preserved": protected_preserved,
        },
    }


def evaluate(
    fixture_rows: list[dict[str, Any]], prediction_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    fixture_by_id = {row["id"]: row for row in fixture_rows}
    if len(fixture_by_id) != len(fixture_rows):
        raise ValidationError("fixture ids must be unique")

    predictions: dict[str, str] = {}
    for row in prediction_rows:
        if set(row) != {"id", "prediction"}:
            raise ValidationError(
                f"prediction {row.get('id', '<unknown>')}: only id and prediction are allowed"
            )
        if row["id"] in predictions:
            raise ValidationError(f"duplicate prediction id: {row['id']}")
        if not isinstance(row["prediction"], str):
            raise ValidationError(
                f"prediction {row['id']}: prediction must be a string"
            )
        predictions[row["id"]] = row["prediction"]

    missing = sorted(set(fixture_by_id) - set(predictions))
    extra = sorted(set(predictions) - set(fixture_by_id))
    if missing or extra:
        raise ValidationError(
            f"prediction id mismatch: missing={missing}, extra={extra}"
        )

    paired = [(row, predictions[row["id"]]) for row in fixture_rows]
    slices: dict[str, list[tuple[dict[str, Any], str]]] = defaultdict(list)
    for row, prediction in paired:
        for name in row["slices"]:
            slices[name].append((row, prediction))

    per_row = []
    for row, prediction in paired:
        baseline = levenshtein_distance(row["noisy"], row["clean"])
        candidate = levenshtein_distance(prediction, row["clean"])
        per_row.append(
            {
                "id": row["id"],
                "baseline_edit_distance": baseline,
                "candidate_edit_distance": candidate,
                "error_reduction_rate": 1.0 - candidate / baseline
                if baseline
                else None,
                "exact_match": prediction == row["clean"],
                "protected_spans_preserved": all(
                    prediction.count(span["text"]) == row["clean"].count(span["text"])
                    for span in protected_spans(row)
                ),
            }
        )

    return {
        "schema_version": 1,
        "protocol_id": "mac-local-autocorrect-v1",
        "fixture_sha256": sha256_file(FIXTURE_DIR / "eval-v1.jsonl"),
        "overall": _aggregate_metrics(paired),
        "slices": {
            name: _aggregate_metrics(slice_rows)
            for name, slice_rows in sorted(slices.items())
        },
        "rows": per_row,
    }


def materialize_manifest(
    manifest: dict[str, Any], source_rows: list[dict[str, Any]], layout: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_id = {row["id"]: row for row in source_rows}
    generated: list[dict[str, Any]] = []
    schedule = manifest["family_schedule"]
    seed = manifest["seed"]
    for source_position, source_id in enumerate(manifest["source_document_ids"]):
        if source_id not in source_by_id:
            raise ValidationError(
                f"{manifest['manifest_id']}: unknown source {source_id}"
            )
        source = source_by_id[source_id]
        if source["split"] not in manifest["allowed_splits"]:
            raise ValidationError(
                f"{manifest['manifest_id']}: source {source_id} has forbidden "
                f"split {source['split']}"
            )
        for example_index in range(manifest["examples_per_source"]):
            family = schedule[
                (source_position * manifest["examples_per_source"] + example_index)
                % len(schedule)
            ]
            row_id = f"{manifest['manifest_id']}:{source_id}:{example_index:02d}"
            result = simulate_corruption(
                source["text"],
                row_id=row_id,
                seed=seed,
                family=family,
                layout=layout,
            )
            generated.append(
                {
                    "id": row_id,
                    "source_document_id": source_id,
                    "source_id": source["source_id"],
                    "split": source["split"],
                    "clean": result["clean"],
                    "noisy": result["noisy"],
                    "error_family": result["family"],
                    "trace": result["trace"],
                }
            )
    split_counts = Counter(row["split"] for row in generated)
    family_counts = Counter(row["error_family"] for row in generated)
    summary = {
        "rows": len(generated),
        "utf8_bytes": len(canonical_jsonl_bytes(generated)),
        "split_rows": dict(sorted(split_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "family_rates": {
            family: count / len(generated)
            for family, count in sorted(family_counts.items())
        },
        "dataset_sha256": sha256_bytes(canonical_jsonl_bytes(generated)),
    }
    return generated, summary


def build_distribution_report(
    eval_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    config: dict[str, Any],
    layout: dict[str, Any],
) -> dict[str, Any]:
    natural = Counter()
    for row in eval_rows:
        if row["kind"] == "natural":
            natural.update(row["error_types"])
    natural_total = sum(natural.values())

    training_sources = [row for row in source_rows if row["split"] == "train"]
    synthetic = Counter()
    sample_rows = 256
    for index in range(sample_rows):
        source = training_sources[index % len(training_sources)]
        row_id = f"distribution:{source['id']}:{index:03d}"
        result = simulate_corruption(
            source["text"],
            row_id=row_id,
            seed=config["seed"],
            layout=layout,
            weights=config["family_weights"],
        )
        synthetic[result["family"]] += 1
    synthetic_total = sum(synthetic.values())

    natural_rates = {
        family: natural[family] / natural_total for family in ERROR_FAMILIES
    }
    synthetic_rates = {
        family: synthetic[family] / synthetic_total for family in ERROR_FAMILIES
    }
    absolute_delta = {
        family: abs(natural_rates[family] - synthetic_rates[family])
        for family in ERROR_FAMILIES
    }
    return {
        "schema_version": 1,
        "report_id": "autocorrect-natural-vs-synthetic-v1",
        "natural_fixture": {
            "path": "evals/autocorrect/eval-v1.jsonl",
            "sha256": sha256_file(FIXTURE_DIR / "eval-v1.jsonl"),
            "rows": sum(row["kind"] == "natural" for row in eval_rows),
            "error_events": natural_total,
            "counts": {family: natural[family] for family in ERROR_FAMILIES},
            "rates": natural_rates,
            "limitation": "Tiny manually reviewed original fixture; useful for smoke calibration, not population prevalence.",
        },
        "synthetic_sample": {
            "config_path": "evals/autocorrect/corruption-config-v1.json",
            "config_sha256": sha256_file(FIXTURE_DIR / "corruption-config-v1.json"),
            "rows": sample_rows,
            "counts": {family: synthetic[family] for family in ERROR_FAMILIES},
            "rates": synthetic_rates,
        },
        "comparison": {
            "absolute_rate_delta": absolute_delta,
            "total_variation_distance": 0.5 * sum(absolute_delta.values()),
        },
        "tuning": {
            "changed_surface": "training-side family_weights only",
            "frozen_surface": "evals/autocorrect/eval-v1.jsonl",
            "action": "Use the committed weights as the pilot prior; retune in a new config version when a larger licensed natural sample exists.",
        },
    }


def _validate_source_and_eval(
    errors: list[str],
    sources: dict[str, Any],
    source_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    protocol: dict[str, Any],
    taxonomy: dict[str, Any],
    thresholds: dict[str, Any],
) -> None:
    source_entries = sources.get("sources", [])
    source_by_id = {source.get("id"): source for source in source_entries}
    if len(source_by_id) != len(source_entries):
        errors.append("source ids must be unique")
    for source in source_entries:
        missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in source]
        if missing:
            errors.append(
                f"source {source.get('id')}: missing provenance fields {missing}"
            )
        license_path = source.get("license_path")
        if license_path and not (ROOT / license_path).is_file():
            errors.append(
                f"source {source.get('id')}: missing license path {license_path}"
            )

    source_path = FIXTURE_DIR / "source-documents-v1.jsonl"
    if source_entries:
        expected_revision = sha256_file(source_path)
        primary = source_entries[0]
        if primary.get("revision_kind") != "sha256":
            errors.append("primary source revision_kind must be sha256")
        if primary.get("revision") != expected_revision:
            errors.append(
                f"primary source revision drift: expected {expected_revision}, "
                f"got {primary.get('revision')}"
            )

    source_doc_by_id: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        required = {"id", "source_id", "split", "text"}
        if set(row) != required:
            errors.append(
                f"source document {row.get('id')}: fields must be {sorted(required)}"
            )
            continue
        if row["id"] in source_doc_by_id:
            errors.append(f"duplicate source document id: {row['id']}")
        source_doc_by_id[row["id"]] = row
        if row["source_id"] not in source_by_id:
            errors.append(
                f"source document {row['id']}: unknown source {row['source_id']}"
            )
        if row["split"] not in {"train", "development", "test"}:
            errors.append(f"source document {row['id']}: invalid split {row['split']}")

    allowed_families = set(taxonomy["supported_error_families"])
    eval_ids: set[str] = set()
    for row in eval_rows:
        required = {
            "id",
            "source_document_id",
            "source_id",
            "split",
            "kind",
            "noisy",
            "clean",
            "error_types",
            "slices",
            "protected_spans",
            "review",
        }
        if set(row) != required:
            errors.append(
                f"eval row {row.get('id')}: fields must be {sorted(required)}"
            )
            continue
        if row["id"] in eval_ids:
            errors.append(f"duplicate eval id: {row['id']}")
        eval_ids.add(row["id"])
        source_doc = source_doc_by_id.get(row["source_document_id"])
        if source_doc is None:
            errors.append(f"eval row {row['id']}: unknown source document")
            continue
        if (
            row["source_id"] != source_doc["source_id"]
            or row["split"] != source_doc["split"]
        ):
            errors.append(
                f"eval row {row['id']}: source-first split/provenance mismatch"
            )
        if row["split"] != "test":
            errors.append(f"eval row {row['id']}: frozen eval rows must be test split")
        if row["clean"] != source_doc["text"]:
            errors.append(
                f"eval row {row['id']}: clean text differs from source document"
            )
        if row["kind"] not in {"natural", "clean"}:
            errors.append(f"eval row {row['id']}: invalid kind")
        if row["kind"] == "clean" and (
            row["noisy"] != row["clean"] or row["error_types"]
        ):
            errors.append(f"eval row {row['id']}: invalid clean control")
        if row["kind"] == "natural" and (
            row["noisy"] == row["clean"] or not row["error_types"]
        ):
            errors.append(f"eval row {row['id']}: natural row needs an error")
        unknown = set(row["error_types"]) - allowed_families
        if unknown:
            errors.append(
                f"eval row {row['id']}: unknown error families {sorted(unknown)}"
            )
        if not row["review"].get("unambiguous") or not row["review"].get("reviewed"):
            errors.append(f"eval row {row['id']}: row is not reviewed and unambiguous")
        if (
            len(row["noisy"].encode("utf-8"))
            > protocol["task"]["maximum_input_utf8_bytes"]
        ):
            errors.append(f"eval row {row['id']}: exceeds protocol maximum input bytes")
        for span in protected_spans(row):
            if span["text"] not in row["clean"]:
                errors.append(
                    f"eval row {row['id']}: protected span absent from clean text: {span}"
                )

    train_dev_tokens: set[str] = set()
    test_tokens: set[str] = set()
    for row in source_rows:
        target = test_tokens if row["split"] == "test" else train_dev_tokens
        target.update(lexical_tokens(row["text"]))
    for token in thresholds["lexical_holdout_tokens"]:
        if token not in test_tokens:
            errors.append(f"lexical holdout token absent from test: {token}")
        if token in train_dev_tokens:
            errors.append(
                f"lexical holdout token leaked into train/development: {token}"
            )


def _validate_overlap(
    errors: list[str],
    source_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
) -> None:
    values: list[tuple[str, str, str, str]] = []
    for row in source_rows:
        values.append((row["split"], row["id"], "source-clean", row["text"]))
    for row in eval_rows:
        values.append((row["split"], row["id"], "eval-noisy", row["noisy"]))
    for row in generated_rows:
        values.append((row["split"], row["id"], "generated-noisy", row["noisy"]))

    exact: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    normalized: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for split, row_id, kind, text in values:
        exact[sha256_bytes(text.encode("utf-8"))].append((split, row_id, kind))
        normalized[normalized_overlap_key(text)].append((split, row_id, kind))
    for label, groups in (("exact", exact), ("normalized", normalized)):
        for key, occurrences in groups.items():
            splits = {item[0] for item in occurrences}
            if len(splits) > 1:
                errors.append(
                    f"{label} cross-split overlap {key!r}: {sorted(occurrences)}"
                )


def validate_repository() -> list[str]:
    errors: list[str] = []
    protocol = load_json(FIXTURE_DIR / "protocol-v1.json")
    taxonomy = load_json(FIXTURE_DIR / "taxonomy-v1.json")
    thresholds = load_json(FIXTURE_DIR / "thresholds-v1.json")
    sources = load_json(FIXTURE_DIR / "sources-v1.json")
    source_rows = load_jsonl(FIXTURE_DIR / "source-documents-v1.jsonl")
    eval_rows = load_jsonl(FIXTURE_DIR / "eval-v1.jsonl")
    layout = load_layout()
    config = load_json(FIXTURE_DIR / "corruption-config-v1.json")
    apple = load_json(FIXTURE_DIR / "apple-autocorrect-assessment-v1.json")

    _validate_source_and_eval(
        errors, sources, source_rows, eval_rows, protocol, taxonomy, thresholds
    )
    if apple.get("full_span_protocol_equivalent") is not False:
        errors.append("Apple assessment must not claim full-span protocol equivalence")
    if apple.get("classification") != "observational-non-equivalent":
        errors.append("Apple assessment must remain observational-non-equivalent")
    if not apple.get("evidence") or any(
        not item.get("path") or len(item.get("sha256", "")) != 64
        for item in apple.get("evidence", [])
    ):
        errors.append("Apple assessment evidence paths/hashes are incomplete")

    all_generated: list[dict[str, Any]] = []
    for filename in ("tiny-overfit-manifest-v1.json", "pilot-manifest-v1.json"):
        manifest = load_json(FIXTURE_DIR / filename)
        try:
            input_paths = {
                "sources_sha256": FIXTURE_DIR / "sources-v1.json",
                "source_documents_sha256": FIXTURE_DIR / "source-documents-v1.jsonl",
                "layout_sha256": FIXTURE_DIR / "keyboard-mac-us-ansi-v1.json",
                "corruption_config_sha256": FIXTURE_DIR / "corruption-config-v1.json",
            }
            for field, path in input_paths.items():
                if manifest.get("input_hashes", {}).get(field) != sha256_file(path):
                    errors.append(f"{filename}: {field} drift")
            drop_reasons = manifest.get("drop_reasons")
            if not isinstance(drop_reasons, dict) or any(
                not isinstance(reason, str) or not isinstance(count, int) or count < 0
                for reason, count in (
                    drop_reasons.items() if isinstance(drop_reasons, dict) else []
                )
            ):
                errors.append(
                    f"{filename}: drop_reasons must map strings to non-negative counts"
                )
            generated, summary = materialize_manifest(manifest, source_rows, layout)
            all_generated.extend(generated)
            if manifest.get("expected") != summary:
                errors.append(
                    f"{filename}: expected summary drift; "
                    f"expected={manifest.get('expected')}, actual={summary}"
                )
            for row in generated:
                if apply_trace(row["clean"], row["trace"]) != row["noisy"]:
                    errors.append(f"{filename}: trace replay failed for {row['id']}")
        except (KeyError, TypeError, ValidationError) as exc:
            errors.append(f"{filename}: {exc}")

    _validate_overlap(errors, source_rows, eval_rows, all_generated)

    cases = load_json(FIXTURE_DIR / "simulator-cases-v1.json")
    seen_families: set[str] = set()
    for case in cases["cases"]:
        actual = simulate_corruption(
            case["clean"],
            row_id=case["id"],
            seed=case["seed"],
            family=case["family"],
            layout=layout,
        )
        seen_families.add(case["family"])
        if actual != case["expected"]:
            errors.append(
                f"simulator case {case['id']}: drift; expected={case['expected']}, actual={actual}"
            )
        if apply_trace(actual["clean"], actual["trace"]) != actual["noisy"]:
            errors.append(f"simulator case {case['id']}: trace replay failed")
    missing_families = (set(ERROR_FAMILIES) | {"clean"}) - seen_families
    if missing_families:
        errors.append(f"simulator cases missing families: {sorted(missing_families)}")

    for case in cases["disabled_family_cases"]:
        counts = Counter(
            choose_weighted_family(
                case["family_weights"], case["seed"], case["id"], index
            )
            for index in range(case["samples"])
        )
        if dict(sorted(counts.items())) != case["expected_counts"]:
            errors.append(
                f"disabled-family case {case['id']}: expected "
                f"{case['expected_counts']}, actual={dict(sorted(counts.items()))}"
            )

    expected_report = build_distribution_report(eval_rows, source_rows, config, layout)
    committed_report = load_json(FIXTURE_DIR / "distribution-report-v1.json")
    if committed_report != expected_report:
        errors.append("distribution-report-v1.json drifted from frozen inputs")

    oracle = load_jsonl(FIXTURE_DIR / "oracle-predictions-v1.jsonl")
    try:
        oracle_report = evaluate(eval_rows, oracle)
        if oracle_report["slices"]["natural"]["error_reduction_rate"] != 1.0:
            errors.append("oracle natural error reduction is not 1.0")
        if (
            oracle_report["slices"]["clean"]["clean_byte_exact_preservation_rate"]
            != 1.0
        ):
            errors.append("oracle clean preservation is not 1.0")
    except ValidationError as exc:
        errors.append(f"oracle predictions: {exc}")

    frontier_path = FIXTURE_DIR / "frontier-predictions-codex-v1.jsonl"
    calibration_path = FIXTURE_DIR / "frontier-calibration-v1.json"
    calibration = load_json(calibration_path)
    try:
        frontier_report = evaluate(eval_rows, load_jsonl(frontier_path))
        expected_result = {
            "rows": frontier_report["overall"]["rows"],
            "error_rows": frontier_report["overall"]["error_rows"],
            "exact_match_rate": frontier_report["overall"]["exact_match_rate"],
            "error_reduction_rate": frontier_report["overall"]["error_reduction_rate"],
            "clean_byte_exact_preservation_rate": frontier_report["overall"][
                "clean_byte_exact_preservation_rate"
            ],
            "protected_span_preservation_rate": frontier_report["overall"][
                "protected_span_preservation_rate"
            ],
            "unnecessary_edit_rate": frontier_report["overall"][
                "unnecessary_edit_rate"
            ],
            "rows_fixed_or_dropped": 0,
        }
        if calibration.get("fixture_sha256") != sha256_file(
            FIXTURE_DIR / "eval-v1.jsonl"
        ):
            errors.append("frontier calibration fixture hash drift")
        if calibration.get("predictions_sha256") != sha256_file(frontier_path):
            errors.append("frontier calibration prediction hash drift")
        if calibration.get("result") != expected_result:
            errors.append("frontier calibration result drift")
        if calibration.get("run", {}).get("approved_text_scope") != (
            "evals/autocorrect/eval-v1.jsonl only"
        ):
            errors.append("frontier calibration approved text scope drift")
    except ValidationError as exc:
        errors.append(f"frontier predictions: {exc}")
    return errors


def inspect_payload() -> dict[str, Any]:
    source_rows = load_jsonl(FIXTURE_DIR / "source-documents-v1.jsonl")
    eval_rows = load_jsonl(FIXTURE_DIR / "eval-v1.jsonl")
    layout = load_layout()
    config = load_json(FIXTURE_DIR / "corruption-config-v1.json")
    return {
        "source_documents_sha256": sha256_file(
            FIXTURE_DIR / "source-documents-v1.jsonl"
        ),
        "manifests": {
            filename: materialize_manifest(
                load_json(FIXTURE_DIR / filename), source_rows, layout
            )[1]
            for filename in (
                "tiny-overfit-manifest-v1.json",
                "pilot-manifest-v1.json",
            )
        },
        "simulator_cases": [
            {
                "id": case["id"],
                "expected": simulate_corruption(
                    case["clean"],
                    row_id=case["id"],
                    seed=case["seed"],
                    family=case["family"],
                    layout=layout,
                ),
            }
            for case in load_json(FIXTURE_DIR / "simulator-cases-v1.json")["cases"]
        ],
        "distribution_report": build_distribution_report(
            eval_rows, source_rows, config, layout
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "validate", help="validate every committed foundation artifact"
    )
    evaluate_parser = subparsers.add_parser(
        "evaluate", help="strictly score predictions against the frozen fixture"
    )
    evaluate_parser.add_argument("--predictions", type=Path, required=True)
    subparsers.add_parser(
        "inspect", help="print deterministic hashes/expected artifacts for review"
    )
    args = parser.parse_args(argv)

    if args.command == "validate":
        errors = validate_repository()
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("autocorrect foundation: valid")
        return 0
    if args.command == "evaluate":
        report = evaluate(
            load_jsonl(FIXTURE_DIR / "eval-v1.jsonl"),
            load_jsonl(args.predictions),
        )
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    print(json.dumps(inspect_payload(), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
