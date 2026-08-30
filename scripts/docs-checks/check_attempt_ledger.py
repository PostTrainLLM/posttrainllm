#!/usr/bin/env python3
"""Check that docs/attempt-ledger.md covers structured attempt metadata."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED_STATUSES = {
    "worked",
    "worked-with-caveat",
    "failed",
    "regressed",
    "inconclusive",
    "not-tried",
}
REQUIRES_REASON = {"failed", "regressed", "worked-with-caveat", "inconclusive"}
REASON_FIELDS = ("failure_reason", "lesson", "next_action")
ALLOWED_CONFIDENCE = {
    "exact",
    "inferred",
    "missing-evidence",
    "not-applicable",
}


def main() -> int:
    attempts_path = ROOT / "docs/attempts.json"
    ledger_path = ROOT / "docs/attempt-ledger.md"
    history_path = ROOT / "docs/audits/history-coverage-audit.md"
    completion_path = ROOT / "docs/audits/exactness-completion-audit.md"
    payload = json.loads(attempts_path.read_text(encoding="utf-8"))
    attempts = payload.get("attempts") or []
    ledger = ledger_path.read_text(encoding="utf-8")
    history = history_path.read_text(encoding="utf-8")
    completion = completion_path.read_text(encoding="utf-8")
    errors: list[str] = []

    if payload.get("schema_version") != 2:
        errors.append("docs/attempts.json schema_version must be 2")
    for confidence in ALLOWED_CONFIDENCE:
        if confidence not in (payload.get("confidence_vocabulary") or {}):
            errors.append(
                f"docs/attempts.json confidence_vocabulary missing {confidence!r}"
            )

    seen: set[str] = set()
    for idx, attempt in enumerate(attempts):
        attempt_id = attempt.get("id")
        name = attempt.get("name")
        status = attempt.get("status")
        evidence = attempt.get("evidence")
        source = attempt.get("source")
        family = attempt.get("family")
        confidence = attempt.get("failure_reason_confidence")
        evidence_sources = attempt.get("evidence_sources")
        if not attempt_id or attempt_id in seen:
            errors.append(f"attempt[{idx}] has missing or duplicate id")
        seen.add(attempt_id)
        if status not in ALLOWED_STATUSES:
            errors.append(f"{attempt_id}: invalid status {status!r}")
        if confidence not in ALLOWED_CONFIDENCE:
            errors.append(
                f"{attempt_id}: invalid failure_reason_confidence {confidence!r}"
            )
        if status in REQUIRES_REASON and confidence == "not-applicable":
            errors.append(
                f"{attempt_id}: {status} requires real confidence, not not-applicable"
            )
        if (
            status in {"worked", "not-tried"}
            and confidence != "not-applicable"
            and not attempt.get("failure_reason")
        ):
            errors.append(
                f"{attempt_id}: {status} without failure_reason should use not-applicable confidence"
            )
        for field, value in (
            ("name", name),
            ("family", family),
            ("evidence", evidence),
            ("source", source),
        ):
            if not value:
                errors.append(f"{attempt_id}: missing {field}")
        if not isinstance(evidence_sources, list) or not evidence_sources:
            errors.append(f"{attempt_id}: missing evidence_sources")
        else:
            for evidence_source in evidence_sources:
                if not isinstance(evidence_source, str) or not evidence_source:
                    errors.append(f"{attempt_id}: invalid evidence_sources entry")
                    continue
                local_source = evidence_source.split("#", 1)[0]
                if local_source.startswith(("http://", "https://")):
                    continue
                if not (ROOT / local_source).exists():
                    errors.append(
                        f"{attempt_id}: evidence source does not exist: {evidence_source}"
                    )
        if status in REQUIRES_REASON:
            for field in REASON_FIELDS:
                value = attempt.get(field)
                if not value:
                    errors.append(f"{attempt_id}: missing {field}")
                elif value not in ledger:
                    errors.append(
                        f"{attempt_id}: ledger missing {field} text {value!r}"
                    )
        if name and name not in ledger:
            errors.append(f"{attempt_id}: ledger missing name {name!r}")
        if status and f"`{status}`" not in ledger:
            errors.append(f"{attempt_id}: ledger missing status {status!r}")
        if evidence and evidence not in ledger:
            errors.append(f"{attempt_id}: ledger missing evidence {evidence!r}")

    # Shape fields are what make the index queryable. They are optional per
    # attempt -- old entries may not have derivable shape without inventing
    # history -- but anything present must be valid and resolvable.
    kind_vocab = payload.get("kind_vocabulary") or {}
    method_vocab = payload.get("method_vocabulary") or {}
    objective_vocab = payload.get("objective_vocabulary") or {}
    for vocab_name, vocab in (
        ("kind_vocabulary", kind_vocab),
        ("method_vocabulary", method_vocab),
        ("objective_vocabulary", objective_vocab),
    ):
        if not vocab:
            errors.append(f"docs/attempts.json missing {vocab_name}")

    ids = {attempt.get("id") for attempt in attempts}
    for attempt in attempts:
        attempt_id = attempt.get("id")
        kind = attempt.get("kind")
        if kind not in kind_vocab:
            errors.append(f"{attempt_id}: invalid or missing kind {kind!r}")
        for method in attempt.get("methods") or []:
            if method not in method_vocab:
                errors.append(
                    f"{attempt_id}: method {method!r} is not in method_vocabulary"
                )
        objective = attempt.get("objective")
        if objective and objective not in objective_vocab:
            errors.append(
                f"{attempt_id}: objective {objective!r} is not in objective_vocabulary"
            )
        parent = attempt.get("varied_from")
        if parent:
            if parent not in ids:
                errors.append(f"{attempt_id}: varied_from {parent!r} does not resolve")
            if not attempt.get("varied"):
                errors.append(
                    f"{attempt_id}: varied_from without a 'varied' description"
                )
        if kind == "infrastructure":
            stray = [
                field
                for field in (
                    "methods",
                    "bases",
                    "objective",
                    "data_rows",
                    "varied_from",
                )
                if attempt.get(field)
            ]
            if stray:
                errors.append(
                    f"{attempt_id}: infrastructure attempt carries shape {stray}"
                )

    # A varied_from cycle would make lineage walks non-terminating.
    for attempt in attempts:
        seen_chain, cursor = set(), attempt.get("id")
        by_id = {a.get("id"): a for a in attempts}
        while cursor and cursor not in seen_chain:
            seen_chain.add(cursor)
            cursor = (by_id.get(cursor) or {}).get("varied_from")
        if cursor:
            errors.append(f"{attempt.get('id')}: varied_from chain contains a cycle")

    # The structured index is the queryable source, so the prose ledger must not
    # run ahead of it. Checking only json -> markdown let four attempts live in
    # the ledger with no structured entry, which is invisible to every query.
    import re

    ledger_titles = {title.strip() for title in re.findall(r"^### (.+)$", ledger, re.M)}
    structured_titles = {attempt.get("name", "").strip() for attempt in attempts}
    for orphan in sorted(ledger_titles - structured_titles):
        errors.append(
            f"attempt-ledger.md has section {orphan!r} with no docs/attempts.json entry; "
            "the structured index is what queries read"
        )

    family_labels = {
        "apple-fm": "Apple FM",
        "architecture": "Architecture",
        "archive-model": "Archive model",
        "autocorrect": "Autocorrect",
        "browser-product": "Browser product",
        "chess": "Chess",
        "factory-docs": "Factory/docs",
        "file-ops": "File-ops",
        "pace-planner": "Pace planner",
        "runtime-perf": "Runtime/perf",
        "sql": "SQL",
        "tool-calling": "Tool-calling harness",
    }
    family_counts = Counter(attempt.get("family") for attempt in attempts)
    confidence_counts = Counter(
        attempt.get("failure_reason_confidence") for attempt in attempts
    )
    if f"| Total structured attempts | {len(attempts)} |" not in history:
        errors.append("history coverage audit has stale total structured attempt count")
    if f"| Total attempts | {len(attempts)} |" not in completion:
        errors.append("exactness completion audit has stale total attempt count")
    for family, count in sorted(family_counts.items(), key=lambda kv: kv[0] or ""):
        label = family_labels.get(family)
        if not label:
            errors.append(f"missing history coverage label for family {family!r}")
            continue
        if f"| {label} | {count} |" not in history:
            errors.append(f"history coverage audit has stale count for {family!r}")
    for confidence, count in sorted(
        confidence_counts.items(), key=lambda kv: kv[0] or ""
    ):
        row = f"| `{confidence}` | {count} |"
        if row not in ledger:
            errors.append(
                f"attempt ledger has stale confidence count for {confidence!r}"
            )
        if row not in history:
            errors.append(
                f"history coverage audit has stale confidence count for {confidence!r}"
            )
        completion_label = {
            "exact": "Exact confidence",
            "inferred": "Inferred confidence",
            "not-applicable": "Not-applicable confidence",
            "missing-evidence": "Missing-evidence confidence",
        }.get(confidence)
        if completion_label and f"| {completion_label} | {count} |" not in completion:
            errors.append(
                f"exactness completion audit has stale confidence count for {confidence!r}"
            )

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("attempt ledger check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
