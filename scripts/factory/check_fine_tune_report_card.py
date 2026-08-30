#!/usr/bin/env python3
"""Validate a Fine-Tune Report Card before it enters the public artifact registry.

    python3 scripts/factory/check_fine_tune_report_card.py <report-card.json> [...]
    python3 scripts/factory/check_fine_tune_report_card.py --allow-report-only <path>

Checks schema version, per-field measurement states and provenance, decision
consistency, frontier-ceiling and frozen-eval disclosure, leakage policy,
routed-use disclosure, and public safety (no private payload field names). When
a sibling `report-card.html` exists it is also checked for the accessibility
and contract invariants the static renderer promises.

Invalid publication exits non-zero while printing every failure locally, so a
weak artifact cannot reach the registry by accident. This mirrors
`scripts/factory/check_factory_run_publish.py` for the derived report-card layer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fine_tune_report_card as rc  # noqa: E402


def check_html(page: str, card: dict[str, Any]) -> list[str]:
    """Structural + accessibility checks on the rendered public report.

    These are the promises the static renderer makes: the page is readable
    without repository access, it never renders a weak value as a plain
    measurement, and its structure is navigable by assistive technology.
    """
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(f"html: {message}")

    require("<html lang=" in page, "root element must declare a language")
    require(page.count("<h1") == 1, "page must have exactly one h1")
    require('class="skip-link"' in page, "page must offer a skip link")

    # Heading order must not skip a level (h1 -> h3 is a hard failure).
    levels = [int(m) for m in re.findall(r"<h([1-6])", page)]
    for previous, current in zip(levels, levels[1:]):
        if current > previous + 1:
            errors.append(f"html: heading order skips from h{previous} to h{current}")
            break

    # Every table needs a caption and column headers with an explicit scope.
    tables = re.findall(r"<table>(.*?)</table>", page, flags=re.S)
    require(bool(tables), "page must render at least one evidence table")
    for idx, table in enumerate(tables):
        if "<caption>" not in table:
            errors.append(f"html: table[{idx}] is missing a caption")
        for th in re.findall(r"<th\b[^>]*>", table):
            if "scope=" not in th:
                errors.append(f"html: table[{idx}] has a th without a scope attribute")
                break

    # Every aria-labelledby target must exist on the page.
    for target in re.findall(r'aria-labelledby="([^"]+)"', page):
        if f'id="{target}"' not in page:
            errors.append(f"html: aria-labelledby target `{target}` has no matching id")

    # No empty link text (a link that reads as nothing to a screen reader).
    for text in re.findall(r"<a\b[^>]*>(.*?)</a>", page, flags=re.S):
        if not re.sub(r"<[^>]+>", "", text).strip():
            errors.append("html: found a link with no accessible text")
            break

    # Contract invariants: the decision, its label, and every weak state must
    # be present as text so the page cannot read better than the payload.
    decision = card.get("decision", {})
    require(
        rc.DECISION_HEADLINE.get(decision.get("decision"), "\0") in page,
        "rendered page must state the canonical decision",
    )
    require(
        rc.OUTCOME_HEADLINE.get(decision.get("outcome_label"), "\0") in page,
        "rendered page must state the outcome label",
    )
    if not decision.get("verified"):
        require(
            'data-verified="false"' in page,
            "an unverified card must say so on the page",
        )
        for blocker in decision.get("verification_blockers") or []:
            if blocker not in page and _escape(blocker) not in page:
                errors.append("html: a verification blocker is missing from the page")
                break
    for state in rc.WEAK_STATES:
        if _state_used(card, state):
            require(
                f'data-state="{state}"' in page,
                f"payload uses state `{state}` but the page never labels it",
            )
    return errors


def _escape(text: str) -> str:
    import html as _html

    return _html.escape(text, quote=True)


def _state_used(node: Any, state: str) -> bool:
    if isinstance(node, dict):
        if node.get("state") == state and "sources" in node:
            return True
        return any(_state_used(v, state) for v in node.values())
    if isinstance(node, list):
        return any(_state_used(v, state) for v in node)
    return False


def check_path(path: Path, allow_report_only: bool) -> list[str]:
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{path}: not found"]
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]

    errors = rc.validate(card, allow_report_only=allow_report_only)

    # Prefer the same-stem sibling (published cards are `<slug>.json` next to
    # `<slug>.html`) and only then the compiler's default `report-card.html`.
    # Checking the default first would validate a slug's payload against an
    # unrelated page that happened to share the directory.
    html_path = path.with_suffix(".html")
    if not html_path.is_file():
        html_path = path.with_name("report-card.html")
    if html_path.is_file() and not errors:
        errors.extend(check_html(html_path.read_text(encoding="utf-8"), card))
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="+", help="report-card.json file(s) to validate")
    p.add_argument(
        "--allow-report-only",
        action="store_true",
        help="permit non-ship cards with open blockers. Ship claims stay strict.",
    )
    args = p.parse_args(argv)

    failed = False
    for raw in args.paths:
        path = Path(raw)
        errors = check_path(path, args.allow_report_only)
        if errors:
            failed = True
            print(f"FAIL: {path}", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(f"report card check ok: {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
