#!/usr/bin/env python3
"""Build or check the committed synthetic OffHours method preview."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import offhours_analysis as analysis
import offhours_core as core
import offhours_fixture as fixture
import offhours_report
import offhours_store as store

DEFAULT_ROOT = core.ROOT / "evals" / "offhours"


def build_report() -> dict:
    bundle = core.load_bundle()
    core.validate_bundle(bundle)
    conditions = [item["id"] for item in bundle["config"]["conditions"]]
    with tempfile.TemporaryDirectory() as temporary:
        database = store.connect(Path(temporary) / "preview.sqlite")
        try:
            store.prepare_run(
                database,
                bundle,
                store.RunSpec(
                    run_id="offhours-method-preview",
                    days=5,
                    tasks_per_day=40,
                    seed=42,
                    conditions=conditions,
                    provenance=fixture.build_fixture_provenance(bundle),
                ),
            )
            store.execute_run(
                database,
                bundle,
                "offhours-method-preview",
                fixture.PerfectFixtureClient(),
            )
            return analysis.analyze(database, bundle, "offhours-method-preview")
        finally:
            database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    outputs = {
        "markdown": DEFAULT_ROOT / "report-preview.md",
        "html": DEFAULT_ROOT / "report-preview.html",
    }
    rendered = {
        "markdown": analysis.render_markdown(report),
        "html": offhours_report.render_html(report),
    }
    offhours_report.validate_html(rendered["html"])
    if args.check:
        for kind, path in outputs.items():
            if not path.exists() or path.read_text(encoding="utf-8") != rendered[kind]:
                raise ValueError(f"OffHours preview drift: {path}")
    else:
        for kind, path in outputs.items():
            path.write_text(rendered[kind], encoding="utf-8")
    print("OffHours fixture report: clean; synthetic data only; no model invoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
