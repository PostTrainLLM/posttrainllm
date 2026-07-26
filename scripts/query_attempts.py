#!/usr/bin/env python3
"""Query prior attempts by shape, so a new recipe can be checked against history.

The attempt ledger is written one attempt at a time but read one *question* at
a time, and the question is almost always "has anything shaped like this been
tried?" That needs matching on method, base, and objective -- not chronology.

Usage:
    python3 scripts/query_attempts.py --method dpo --objective output-format
    python3 scripts/query_attempts.py --base flan-t5-small --failures-only
    python3 scripts/query_attempts.py --lineage sql-hygiene-dpo-higher-pressure
    python3 scripts/query_attempts.py --coverage
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS_PATH = ROOT / "docs" / "attempts.json"

# Statuses that mean "this did not achieve what it set out to".
NEGATIVE_STATUSES = {"failed", "regressed", "inconclusive"}


def load_attempts(path: Path | None = None) -> list[dict[str, Any]]:
    payload = json.loads((path or ATTEMPTS_PATH).read_text(encoding="utf-8"))
    return payload["attempts"]


def load_payload(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or ATTEMPTS_PATH).read_text(encoding="utf-8"))


def match(
    attempts: list[dict[str, Any]],
    *,
    methods: list[str] | None = None,
    bases: list[str] | None = None,
    objective: str | None = None,
    kinds: list[str] | None = None,
    failures_only: bool = False,
) -> list[dict[str, Any]]:
    """Attempts sharing any requested method/base plus the objective if given.

    Method and base are OR-matched within themselves and AND-matched against
    each other, which is the useful default: "DPO or SimPO, on this base".
    """
    hits = []
    for attempt in attempts:
        if kinds and attempt.get("kind") not in kinds:
            continue
        if failures_only and attempt["status"] not in NEGATIVE_STATUSES:
            continue
        if methods and not (set(methods) & set(attempt.get("methods") or [])):
            continue
        if bases and not (set(bases) & set(attempt.get("bases") or [])):
            continue
        if objective and attempt.get("objective") != objective:
            continue
        if not (methods or bases or objective or kinds or failures_only):
            continue
        hits.append(attempt)
    return hits


def lineage(attempts: list[dict[str, Any]], attempt_id: str) -> list[dict[str, Any]]:
    """Walk `varied_from` back to the root, oldest first.

    This is the chain a new attempt is about to extend. Reading it in order is
    how you notice that three prior attempts already varied the same axis.
    """
    by_id = {attempt["id"]: attempt for attempt in attempts}
    if attempt_id not in by_id:
        raise SystemExit(f"unknown attempt id: {attempt_id}")
    chain, seen = [], set()
    current: str | None = attempt_id
    while current and current not in seen:
        seen.add(current)
        node = by_id.get(current)
        if node is None:
            break
        chain.append(node)
        current = node.get("varied_from")
    return list(reversed(chain))


def descendants(attempts: list[dict[str, Any]], attempt_id: str) -> list[dict[str, Any]]:
    return [a for a in attempts if a.get("varied_from") == attempt_id]


def format_attempt(attempt: dict[str, Any], *, verbose: bool = True) -> str:
    shape = []
    if attempt.get("methods"):
        shape.append("+".join(attempt["methods"]))
    if attempt.get("bases"):
        shape.append("/".join(attempt["bases"]))
    if attempt.get("objective"):
        shape.append(f"-> {attempt['objective']}")
    if attempt.get("data_rows"):
        shape.append(f"{attempt['data_rows']} rows")
    lines = [f"[{attempt['status']}] {attempt['name']}", f"    {'  |  '.join(shape)}"]
    if attempt.get("varied"):
        lines.append(f"    varied: {attempt['varied']}")
    if verbose:
        lines.append(f"    evidence: {attempt['evidence']}")
        if attempt.get("lesson"):
            lines.append(f"    LESSON:   {attempt['lesson']}")
    return "\n".join(lines)


def related_to_recipe(
    attempts: list[dict[str, Any]],
    *,
    methods: list[str],
    bases: list[str],
    objective: str | None,
) -> list[dict[str, Any]]:
    """Prior attempts a proposed recipe should be read against, most relevant first.

    Ranked by how much shape they share; a shared objective outweighs a shared
    method, because "someone already tried to fix THIS" matters more than
    "someone else also used LoRA". Failures break ties -- a prior failure on the
    same axis is the point of the lookup -- but relevance dominates, otherwise a
    barely-related failure outranks the direct precedent.
    """
    scored = []
    for attempt in attempts:
        if attempt.get("kind") == "infrastructure":
            continue
        score = 0
        if set(methods) & set(attempt.get("methods") or []):
            score += 2
        if set(bases) & set(attempt.get("bases") or []):
            score += 2
        if objective and attempt.get("objective") == objective:
            score += 5
        if score:
            scored.append((score, attempt["status"] in NEGATIVE_STATUSES, attempt))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [attempt for _, _, attempt in scored]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", action="append", default=[])
    parser.add_argument("--base", action="append", default=[])
    parser.add_argument("--objective")
    parser.add_argument("--kind", action="append", default=[])
    parser.add_argument("--failures-only", action="store_true")
    parser.add_argument("--lineage", metavar="ATTEMPT_ID")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args(argv)

    payload = load_payload()
    attempts = payload["attempts"]

    if args.coverage:
        shaped = [a for a in attempts if a.get("kind") != "infrastructure"]
        print(f"attempts: {len(attempts)}  shaped: {len(shaped)}  "
              f"infrastructure: {len(attempts) - len(shaped)}")
        for field in ("methods", "bases", "objective", "data_rows", "varied_from"):
            have = sum(1 for a in shaped if a.get(field))
            print(f"  {field:12} {have:>3}/{len(shaped)}")
        print("\nvocabulary in use:")
        for key in ("methods", "bases", "objective"):
            values: set[str] = set()
            for attempt in shaped:
                value = attempt.get(key)
                values.update(value if isinstance(value, list) else [value] if value else [])
            print(f"  {key:12} {', '.join(sorted(values))}")
        return 0

    if args.lineage:
        chain = lineage(attempts, args.lineage)
        if args.json:
            print(json.dumps(chain, indent=2, ensure_ascii=False))
            return 0
        print(f"lineage of {args.lineage} ({len(chain)} attempt(s), oldest first):\n")
        for index, attempt in enumerate(chain):
            print(f"{index + 1}. {format_attempt(attempt)}\n")
        kids = descendants(attempts, args.lineage)
        if kids:
            print(f"superseded by: {', '.join(k['id'] for k in kids)}")
        return 0

    hits = match(
        attempts,
        methods=args.method or None,
        bases=args.base or None,
        objective=args.objective,
        kinds=args.kind or None,
        failures_only=args.failures_only,
    )
    if args.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return 0
    if not hits:
        print("no prior attempt matches that shape")
        return 0
    print(f"{len(hits)} matching attempt(s):\n")
    for attempt in hits:
        print(format_attempt(attempt) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
