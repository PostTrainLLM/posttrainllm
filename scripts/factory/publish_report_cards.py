"""Publish the Fine-Tune Report Card cohort into the public site.

    python3 scripts/factory/publish_report_cards.py            # regenerate committed cards
    python3 scripts/factory/publish_report_cards.py --check    # fail if committed cards drifted

Each cohort member is compiled from evidence that already exists in this
repository, so the published cards can always be regenerated without a GPU, a
model, or a network call:

- `qwen06-sql-routed-v1` is rendered from the committed SQL fixtures by
  `scripts/sql/render_sql_factory_run.py` into a throwaway run folder, then
  compiled through the factory-run adapter.
- the two registered specialist packages are compiled through the
  specialist-package adapter, which marks their legacy scores `historical`.

Published output lands in `browser/public/report-cards/<slug>.{json,html}`,
served by Cloudflare Pages as `/report-cards/<slug>`. `--check` recompiles into a
temp directory and compares, so a stale committed card cannot ship silently
(the same guard idea as `browser/scripts/check_gallery_drift.mjs`).

Outcome classes with no compilable evidence in a clean checkout are recorded in
`docs/factory/report-card.md` as documented absences rather than being faked.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_fine_tune_report_card as builder
import fine_tune_report_card as rc

ROOT = Path(__file__).resolve().parents[2]
PUBLISH_DIR = ROOT / "browser/public/report-cards"

#: (published slug, source kind, source locator, allow_report_only)
COHORT = (
    (
        "qwen3-4b-file-ops-distilled",
        "specialist",
        "specialists/qwen3-4b-file-ops-distilled",
        False,
    ),
    ("qwen3-4b-rest-fused", "specialist", "specialists/qwen3-4b-rest-fused", False),
    ("qwen06-sql-routed-v1", "sql-run", "scripts/sql/render_sql_factory_run.py", True),
)


def compile_member(kind: str, locator: str, workdir: Path) -> dict:
    if kind == "specialist":
        return builder.compile_from_specialist(ROOT / locator)
    if kind == "sql-run":
        run_dir = workdir / "sql-run"
        subprocess.run(
            [sys.executable, str(ROOT / locator), "--out", str(run_dir)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return builder.compile_from_run(run_dir)
    raise SystemExit(f"unknown cohort source kind: {kind}")


def build_all(workdir: Path) -> dict[str, tuple[str, str]]:
    """Compile every cohort member. Returns {slug: (json_text, html_text)}."""
    out: dict[str, tuple[str, str]] = {}
    for slug, kind, locator, allow_report_only in COHORT:
        card = compile_member(kind, locator, workdir)
        errors = rc.validate(card, allow_report_only=allow_report_only)
        if errors:
            print(f"FAIL: {slug} did not validate:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            raise SystemExit(1)
        canonical_url = f"https://posttrainllm.com/report-cards/{slug}"
        out[slug] = (rc.dumps(card), rc.render_html(card, canonical_url=canonical_url))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="compare committed cards against a fresh compile and exit non-zero on drift",
    )
    p.add_argument("--out", default=str(PUBLISH_DIR), help="publish directory")
    args = p.parse_args(argv)

    out_dir = Path(args.out)
    with tempfile.TemporaryDirectory(prefix="report-cards-") as tmp:
        cards = build_all(Path(tmp))

    if args.check:
        drifted: list[str] = []
        for slug, (payload, page) in sorted(cards.items()):
            for suffix, fresh in ((".json", payload), (".html", page)):
                path = out_dir / f"{slug}{suffix}"
                if not path.is_file():
                    drifted.append(f"{path.name}: not published")
                elif path.read_text(encoding="utf-8") != fresh:
                    drifted.append(f"{path.name}: differs from a fresh compile")
        extra = {
            path.name
            for path in out_dir.glob("*")
            if path.is_file()
            and path.stem not in cards
            and path.suffix in (".json", ".html")
        }
        for name in sorted(extra):
            drifted.append(f"{name}: published but not in the cohort")
        if drifted:
            print("FAIL: published report cards have drifted:", file=sys.stderr)
            for item in drifted:
                print(f"  - {item}", file=sys.stderr)
            print(
                "\nRegenerate with: python3 scripts/factory/publish_report_cards.py",
                file=sys.stderr,
            )
            return 1
        print(f"report cards up to date: {len(cards)} card(s) in {out_dir}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, (payload, page) in sorted(cards.items()):
        (out_dir / f"{slug}.json").write_text(payload, encoding="utf-8")
        (out_dir / f"{slug}.html").write_text(page, encoding="utf-8")
        print(f"published: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
