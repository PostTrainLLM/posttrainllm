#!/usr/bin/env python3
"""Assemble a canonical factory run folder from real train/eval fragments.

This is the general report-artifact bridge. Where `render_sql_factory_run.py`
hard-codes one SQL run, this script assembles *any* run from the JSON fragments
that the real commands already produce, then derives the parts that should never
be hand-authored:

- `provenance.json`  — git state, dataset SHA-256/rows, exact command strings.
- `report.md`        — the `docs/factory/reports.md` template, filled from the
                       fragments with the eval delta computed, not typed.
- `train.log`        — a placeholder only if the training step left none.

It is metadata-only: it never starts a server, trains an adapter, or reruns a
GPU eval. It only reads fragments and writes the derived files back into the run
directory, so the output passes both `FactoryRunFolder.validate` (the typed
Swift schema) and `check_factory_run_publish.py` (the publish gate).

Usage:

    # real commands drop these into runs/<id>/ first:
    #   config.json dataset.json eval-baseline.json eval-candidate.json
    #   decision.json  (+ optional artifact.json slice-metrics.json
    #                    trace_review.md train.log)
    python3 scripts/assemble_factory_run.py runs/<id>
    python3 scripts/assemble_factory_run.py runs/<id> --publish-check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

# Fragments the real train/eval/decision commands are expected to emit.
REQUIRED_FRAGMENTS = [
    "config.json",
    "dataset.json",
    "eval-baseline.json",
    "eval-candidate.json",
    "decision.json",
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid or missing JSON: {exc}")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_value(args: list[str], default: str | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return default


def resolve_dataset_path(raw: str) -> Path | None:
    """Find a dataset source file relative to the repo root or as an absolute path."""
    candidate = Path(raw)
    for base in (ROOT / raw, candidate):
        if base.is_file():
            return base
    return None


def num(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) else "n/a"


def build_provenance(run_dir: Path, payloads: dict[str, Any]) -> dict[str, Any]:
    config = payloads["config"]
    baseline = payloads["eval-baseline"]
    candidate = payloads["eval-candidate"]

    datasets: list[dict[str, Any]] = []
    for source in payloads["dataset"].get("sources", []):
        raw = source.get("path", "")
        if source.get("sha256"):
            # Trust a precomputed hash (e.g. a non-repo cache path).
            datasets.append(
                {"path": raw, "rows": source.get("rows", 0), "sha256": source["sha256"]}
            )
            continue
        resolved = resolve_dataset_path(raw)
        if resolved is None:
            raise SystemExit(
                f"dataset source path not found and no precomputed sha256: {raw!r}\n"
                "Provide a real path or a 'sha256' field in dataset.json sources."
            )
        datasets.append(
            {"path": raw, "rows": line_count(resolved), "sha256": sha256_file(resolved)}
        )

    status = git_value(["status", "--short"], default="")
    return {
        "schema_version": 1,
        "renderer": "scripts/assemble_factory_run.py",
        "renderer_command": f"python3 scripts/assemble_factory_run.py {run_dir}",
        "git": {
            "commit": git_value(["rev-parse", "HEAD"], default=None),
            "branch": git_value(["rev-parse", "--abbrev-ref", "HEAD"], default=None),
            "dirty": bool(status),
        },
        "commands": {
            "baseline": baseline.get("command"),
            "candidate": candidate.get("command"),
            "training": config.get("candidate", {}).get("training_command"),
            "publish_check": f"posttrainllm factory-run publish-check --allow-report-only {run_dir}",
        },
        "datasets": datasets,
    }


def render_slice_table(slice_metrics: dict[str, Any] | None) -> str:
    if not slice_metrics:
        return (
            "| Slice | Baseline | Candidate | Delta | Pass |\n"
            "|---|---:|---:|---:|---|\n"
            "| Overall | n/a | n/a | n/a | see `slice-metrics.json` |\n"
        )
    rows = ["| Slice | Baseline | Candidate | Delta | Rows |", "|---|---:|---:|---:|---:|"]
    for name, slc in (slice_metrics.get("slices") or {}).items():
        # Two shapes are supported: the explicit baseline/candidate/delta shape,
        # and the candidate-only score_sql_slices.py shape (execution_accuracy /
        # exact_match / rows).
        base = slc.get("baseline")
        cand = slc.get("candidate")
        if cand is None:
            cand = slc.get("execution_accuracy", slc.get("exact_match"))
        delta = slc.get("delta")
        n_rows = slc.get("rows")
        rows.append(
            f"| {name} | {num(base)} | {num(cand)} | {num(delta)} | {n_rows if n_rows is not None else 'n/a'} |"
        )
    return "\n".join(rows) + "\n"


def render_report(payloads: dict[str, Any], slice_metrics: dict[str, Any] | None) -> str:
    config = payloads["config"]
    dataset = payloads["dataset"]
    baseline = payloads["eval-baseline"]
    candidate = payloads["eval-candidate"]
    decision = payloads["decision"]
    artifact = payloads.get("artifact")

    delta = None
    if isinstance(candidate.get("score"), (int, float)) and isinstance(
        baseline.get("score"), (int, float)
    ):
        delta = candidate["score"] - baseline["score"]

    method = config.get("candidate", {}).get("method", "unknown-method")
    date = candidate.get("date", "n/a")
    target = config.get("target", "unknown-target")
    counts = dataset.get("counts", {})
    processing = dataset.get("processing", {})
    passed_primary = "yes" if candidate.get("passed") else "no"
    artifact_path = artifact.get("path") if artifact else "report-only (no shipped artifact)"

    evidence = "\n".join(
        f"  - `{src}`" for src in (decision.get("evidence_sources") or ["eval-candidate.json"])
    )

    perf_rows = [
        ("Train time", candidate.get("train_time", "n/a")),
        ("Eval time", candidate.get("eval_time", "n/a")),
        ("Latency", f'{candidate["latency_ms"]} ms' if candidate.get("latency_ms") is not None else "n/a"),
        ("tok/s", candidate.get("tokens_per_second") if candidate.get("tokens_per_second") is not None else "n/a"),
        ("RAM / peak RSS", f'{candidate["peak_rss_mb"]} MB' if candidate.get("peak_rss_mb") is not None else "n/a"),
    ]
    perf_table = "\n".join(f"| {name} | {value} |" for name, value in perf_rows)

    return f"""# {target} — {method} — {date}

## Decision

Decision: {decision.get("decision")}

Reason: {decision.get("reason")}

## Evidence / Exactness

- Failure reason: {decision.get("failure_reason") if decision.get("failure_reason") else "n/a (ship)"}
- Failure reason confidence: {decision.get("failure_reason_confidence")}
- Lesson: {decision.get("lesson") if decision.get("lesson") else "n/a"}
- Evidence sources:
{evidence}

## Target

- Target: {target}
- Base model: {config.get("base_model", {}).get("id")}
- Candidate: {candidate.get("model_id")}
- Training method: {method}
- Artifact: {artifact_path}

## Data

- Dataset: {dataset.get("dataset_id")}
- Rows: {counts.get("train_rows", "n/a")} train
- Heldout: {counts.get("heldout_rows", "n/a")} heldout, {counts.get("dropped_rows", 0)} dropped
- Filters: dedupe={processing.get("dedupe")}, quality_filter={processing.get("quality_filter")}, heldout_split={processing.get("heldout_split")}
- Known gaps: {dataset.get("known_gaps", "none recorded")}

## Eval

| Metric | Baseline | Candidate | Delta | Pass |
|---|---:|---:|---:|---|
| {config.get("eval", {}).get("primary", "primary")} | {num(baseline.get("score"))} | {num(candidate.get("score"))} | {num(delta)} | {passed_primary} |

## Slice Metrics

{render_slice_table(slice_metrics)}
## Performance

| Metric | Value |
|---|---:|
{perf_table}

## Failures

| Attempt | Method | Result | Decision | Failure reason | Confidence | Lesson |
|---|---|---|---|---|---|---|
| A0 | {method} | primary {num(candidate.get("score"))} ({passed_primary}) | {decision.get("decision")} | {decision.get("failure_reason") or "n/a"} | {decision.get("failure_reason_confidence")} | {decision.get("lesson") or "n/a"} |

## Trace Review

- File: `trace_review.md`

## Next Action

{decision.get("next_action")}
"""


def assemble(run_dir: Path, force: bool) -> dict[str, Any]:
    if not run_dir.is_dir():
        raise SystemExit(f"{run_dir}: not a directory")

    missing = [f for f in REQUIRED_FRAGMENTS if not (run_dir / f).is_file()]
    if missing:
        raise SystemExit(
            f"{run_dir}: missing required fragments: {', '.join(missing)}\n"
            "These are emitted by the train/eval/decision commands before assembly."
        )

    payloads: dict[str, Any] = {
        "config": load_json(run_dir / "config.json"),
        "dataset": load_json(run_dir / "dataset.json"),
        "eval-baseline": load_json(run_dir / "eval-baseline.json"),
        "eval-candidate": load_json(run_dir / "eval-candidate.json"),
        "decision": load_json(run_dir / "decision.json"),
    }
    if (run_dir / "artifact.json").is_file():
        payloads["artifact"] = load_json(run_dir / "artifact.json")

    slice_metrics = (
        load_json(run_dir / "slice-metrics.json")
        if (run_dir / "slice-metrics.json").is_file()
        else None
    )

    # Derive provenance from git + real dataset hashes.
    provenance_path = run_dir / "provenance.json"
    if provenance_path.is_file() and not force:
        raise SystemExit(f"{provenance_path} already exists; pass --force to overwrite")
    write_json(provenance_path, build_provenance(run_dir, payloads))

    # Derive the report from the fragments (delta computed, not typed).
    report_path = run_dir / "report.md"
    if report_path.is_file() and not force:
        raise SystemExit(f"{report_path} already exists; pass --force to overwrite")
    report_path.write_text(render_report(payloads, slice_metrics), encoding="utf-8")

    # Only fill train.log if the training step left none.
    train_log = run_dir / "train.log"
    if not train_log.is_file():
        train_log.write_text(
            "No train log recorded by the training command; assembled metadata-only.\n",
            encoding="utf-8",
        )

    warnings: list[str] = []
    if slice_metrics is None:
        warnings.append("slice-metrics.json absent (required by publish-check; run score_sql_slices.py)")
    if not (run_dir / "trace_review.md").is_file():
        warnings.append("trace_review.md absent (required by publish-check; run review_sql_trace.py)")
    return {"warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="Run directory holding the emitted fragments.")
    ap.add_argument("--force", action="store_true", help="Overwrite derived provenance.json/report.md.")
    ap.add_argument(
        "--publish-check",
        action="store_true",
        help="Run check_factory_run_publish.py --allow-report-only after assembling.",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    result = assemble(run_dir, args.force)
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"assembled factory run: {run_dir}")

    if args.publish_check:
        checker = ROOT / "scripts/check_factory_run_publish.py"
        rc = subprocess.call(
            [sys.executable, str(checker), str(run_dir), "--allow-report-only"]
        )
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
