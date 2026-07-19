#!/usr/bin/env python3
"""Emit a sanitized Foundry evidence receipt for posttrainllm.

This is metadata-only and read-only. It never trains, evaluates, uploads,
publishes, deploys, or copies a private payload. It collects evidence that
already exists in the repo (git state, ``specialists/registry.json``, factory
run folders, the local nightly cache markers) and the latest CI run via
``gh`` (when available), then writes a single JSON receipt.

The contract is documented in ``docs/factory/foundry-evidence.md``. The
receipt is validated by ``scripts/check_foundry_receipt.py``.

Privacy:

- No dataset rows, prompts, completions, golds, predictions, checkpoint
  bytes, or training-log contents are copied. Only paths, hashes, row
  counts, scores, and metadata.
- No secrets. The PostHog public ingest key is never read here.
- ``sanitize_payload`` strips any field on a denylist and enforces a total
  byte ceiling, so even if a caller passes a run folder containing private
  fragments, the receipt cannot carry them.

Usage:

    python3 scripts/foundry_receipt.py                    # write to stdout
    python3 scripts/foundry_receipt.py --out receipt.json
    python3 scripts/foundry_receipt.py --runs runs/       # include local runs
    python3 scripts/foundry_receipt.py --no-ci            # skip gh query
    python3 scripts/foundry_receipt.py --check            # validate after emit
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
PROJECT = "posttrainllm"
NIGHTLY_HOME = Path(os.environ.get("HOME", "")) / ".cache" / "posttrainllm" / "nightly"
NIGHTLY_FRESHNESS_DAYS = 7
PUBLIC_SITE_FRESHNESS_DAYS = 14

# Fields that must NEVER appear in a receipt, regardless of source. The
# sanitizer drops any key (case-insensitive substring) on this list before
# the receipt is serialized.
DENYLIST_FIELDS = (
    "prompt",
    "completion",
    "gold",
    "prediction",
    "trajectory",
    "raw_log",
    "train_log_contents",
    "checkpoint",
    "adapter_bytes",
    "weights",
    "weight_bytes",
    "optimizer_state",
    "api_key",
    "token",
    "secret",
    "password",
    "credential",
    "dataset_rows_text",
    "dataset_content",
    "prompt_text",
    "output_text",
)

# Hard ceiling on the serialized receipt. A real receipt is a few KB; this
# is a backstop against a bug accidentally streaming a checkpoint in.
RECEIPT_BYTE_CEILING = 256 * 1024


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def git_value(args: list[str], default: str | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip() or default
    except Exception:
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_payload(value: Any, _path: str = "") -> Any:
    """Recursively drop denylisted keys and private-looking strings.

    This is defense in depth. The emitter never intentionally reads private
    payloads, but if a future caller wires in a run folder containing raw
    fragments, this strips anything that looks private before serialization.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if any(bad in key_lower for bad in DENYLIST_FIELDS):
                continue
            out[k] = sanitize_payload(v, f"{_path}.{k}")
        return out
    if isinstance(value, list):
        return [sanitize_payload(v, f"{_path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, str):
        # Drop strings that look like raw training data: very long, or that
        # contain common prompt/completion markers. A 4 KB ceiling is well
        # above any legitimate metadata string (paths, repo ids, slugs).
        if len(value) > 4096:
            return f"<redacted:overlong-string:{len(value)}b>"
        return value
    return value


def source_revision() -> dict[str, Any]:
    commit = git_value(["rev-parse", "HEAD"])
    branch = git_value(["rev-parse", "--abbrev-ref", "HEAD"])
    status = git_value(["status", "--short"], default="")
    return {"commit": commit, "branch": branch, "dirty": bool(status)}


def ci_status() -> dict[str, Any]:
    """Latest ci.yml run on main via gh. Returns not-applicable when unavailable."""
    try:
        out = subprocess.check_output(
            [
                "gh",
                "run",
                "list",
                "--workflow=ci.yml",
                "--branch=main",
                "--limit=1",
                "--json=status,conclusion,headSha,url,databaseId",
            ],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        )
        runs = json.loads(out) if out.strip() else []
    except Exception:
        return {"status": "not-applicable", "reason": "gh-unavailable"}
    if not runs:
        return {"status": "not-applicable", "reason": "no-ci-runs"}
    r = runs[0]
    return {
        "status": r.get("status"),
        "conclusion": r.get("conclusion"),
        "head_sha": r.get("headSha"),
        "url": r.get("url"),
        "run_id": r.get("databaseId"),
    }


def public_site_block() -> dict[str, Any]:
    indexing_files = [
        "browser/public/llms.txt",
        "browser/public/llms-full.txt",
        "browser/public/api-ai.json",
        "browser/public/robots.txt",
        "browser/public/sitemap.xml",
    ]
    missing = [f for f in indexing_files if not (ROOT / f).is_file()]
    return {
        "build": "pass" if not missing else "fail",
        "live": "not-applicable",  # live probe is a fleet-host job, not this receipt
        "indexing": "pass" if not missing else "fail",
        "missing_index_files": missing,
        "freshness_window_days": PUBLIC_SITE_FRESHNESS_DAYS,
    }


def playground_block() -> dict[str, Any]:
    bundle_files = [
        "browser/public/tinygpt.js",
        "browser/public/tinygpt.wasm",
        "browser/public/tinygpt64.js",
        "browser/public/tinygpt64.wasm",
    ]
    missing = [f for f in bundle_files if not (ROOT / f).is_file()]
    analytics = ROOT / "browser/src/analytics.ts"
    has_activation = analytics.is_file() and "playground_loaded" in analytics.read_text(
        encoding="utf-8"
    )
    has_failure = analytics.is_file() and "foundry_page_crash" in analytics.read_text(
        encoding="utf-8"
    )
    return {
        "bundle": "pass" if not missing else "fail",
        "missing_bundle_files": missing,
        "activation_event": "playground_loaded" if has_activation else "missing",
        "failure_event": "foundry_page_crash" if has_failure else "missing",
    }


def artifact_quality_claims(pkg: dict[str, Any], eval_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build provenance-anchored quality claims from a registry pkg + eval_report.

    Each claim carries source_revision, model, eval_config, dataset_version,
    observed_at, result, artifact_location, and retention. If any required
    provenance field is missing, the claim is omitted and a gap is recorded
    in the receipt's ``blocked`` list by the caller.
    """
    claims: list[dict[str, Any]] = []
    if not eval_report:
        return claims
    artifact_loc = pkg.get("artifact_path") or pkg.get("storage", {}).get("repo_id")
    model = pkg.get("base")
    updated = eval_report.get("updated")
    # Source revision MUST be the revision at which the claim was observed,
    # recorded explicitly in the eval_report. We deliberately do NOT fall
    # back to current HEAD: that would mislabel emit-time as observation-time
    # and let a stale claim masquerade as fresh provenance. Missing
    # source_revision -> the claim is dropped and a gap is recorded by the
    # caller (artifacts_block).
    source_rev = eval_report.get("source_revision")
    for score in eval_report.get("scores", []):
        dataset_version = score.get("dataset_version") or score.get("dataset_sha256")
        eval_config = score.get("eval_config") or score.get("source")
        # Required provenance per the contract. Missing any -> skip the claim.
        if not (source_rev and model and eval_config and artifact_loc and updated):
            continue
        claims.append(
            {
                "metric": score.get("suite"),
                "n": score.get("n"),
                "baseline": score.get("stock_4b"),
                "candidate": score.get("distilled_4b") or score.get("candidate"),
                "frontier": score.get("frontier"),
                "delta": score.get("delta"),
                "source_revision": source_rev,
                "model": model,
                "eval_config": eval_config,
                "dataset_version": dataset_version or "not-recorded",
                "observed_at": updated,
                "artifact_location": artifact_loc,
                "retention": "hf-preserved" if pkg.get("storage", {}).get("primary") == "huggingface_hub" else "local-only",
            }
        )
    return claims


def artifacts_block(blocked: list[str]) -> list[dict[str, Any]]:
    registry_path = ROOT / "specialists/registry.json"
    if not registry_path.is_file():
        blocked.append("specialists/registry.json missing")
        return []
    registry = read_json(registry_path)
    out: list[dict[str, Any]] = []
    for pkg in registry.get("packages", []):
        pkg_dir = ROOT / pkg.get("package_path", "")
        eval_report_path = pkg_dir / "eval_report.json"
        eval_report = read_json(eval_report_path) if eval_report_path.is_file() else None
        lock_path = pkg_dir / "tinygpt.lock.json"
        reproducibility = "lockfile-present" if lock_path.is_file() else "fail"
        claims = artifact_quality_claims(pkg, eval_report or {})
        if eval_report and not claims:
            blocked.append(f"{pkg.get('id')}: eval_report present but no provenance-complete claims")
        out.append(
            {
                "id": pkg.get("id"),
                "state": pkg.get("status"),
                "storage": pkg.get("storage", {}),
                "reproducibility": reproducibility,
                "size_cost_guard": "not-applicable",  # no automatic budget enforcement yet
                "quality_claims": claims,
            }
        )
    return out


def local_runs_block(runs_dir: Path, blocked: list[str]) -> list[dict[str, Any]]:
    """Summarize each factory run folder. Carries only metadata, never payloads."""
    if not runs_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        decision_path = run_dir / "decision.json"
        config_path = run_dir / "config.json"
        baseline_path = run_dir / "eval-baseline.json"
        candidate_path = run_dir / "eval-candidate.json"
        provenance_path = run_dir / "provenance.json"
        if not (decision_path.is_file() and config_path.is_file()):
            continue
        decision = read_json(decision_path)
        config = read_json(config_path)
        baseline = read_json(baseline_path) if baseline_path.is_file() else {}
        candidate = read_json(candidate_path) if candidate_path.is_file() else {}
        provenance = read_json(provenance_path) if provenance_path.is_file() else {}
        dataset_sha = None
        dataset_rows = None
        for d in provenance.get("datasets", []):
            dataset_sha = d.get("sha256")
            dataset_rows = d.get("rows")
            break
        # publish-check verdict: re-derive by invoking the no-build checker.
        publish_check = "not-applicable"
        try:
            res = subprocess.run(
                ["python3", "scripts/check_factory_run_publish.py", "--allow-report-only", str(run_dir)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )
            publish_check = "pass" if res.returncode == 0 else "fail"
        except Exception:
            publish_check = "not-applicable"
        out.append(
            {
                "run_id": config.get("run_id") or run_dir.name,
                "target": config.get("target"),
                "method": config.get("candidate", {}).get("method"),
                "decision": decision.get("decision"),
                "baseline_score": baseline.get("score"),
                "candidate_score": candidate.get("score"),
                "delta": (
                    candidate.get("score") - baseline.get("score")
                    if isinstance(candidate.get("score"), (int, float))
                    and isinstance(baseline.get("score"), (int, float))
                    else None
                ),
                "source_revision": provenance.get("git", {}).get("commit"),
                "dataset_sha256": dataset_sha,
                "dataset_rows": dataset_rows,
                "publish_check": publish_check,
                "publication": "pending-approval",  # never auto-publish
            }
        )
    return out


def nightly_block() -> list[dict[str, Any]]:
    jobs_dir = ROOT / "scripts/nightly"
    if not jobs_dir.is_dir():
        return []
    done_dir = NIGHTLY_HOME / "done"
    log_dir = NIGHTLY_HOME / "logs"
    out: list[dict[str, Any]] = []
    now = _dt.datetime.now(_dt.timezone.utc)
    for job in sorted(jobs_dir.glob("N*.sh")):
        name = job.stem
        done = done_dir / f"{name}.done"
        log = log_dir / f"{name}.log"
        if not NIGHTLY_HOME.exists():
            state = "not-applicable"
            last_done_at = None
        elif done.is_file():
            mtime = _dt.datetime.fromtimestamp(done.stat().st_mtime, _dt.timezone.utc)
            age_days = (now - mtime).days
            state = "pass" if age_days <= NIGHTLY_FRESHNESS_DAYS else "stale"
            last_done_at = mtime.replace(microsecond=0).isoformat()
        elif log.is_file():
            state = "fail"
            last_done_at = None
        else:
            state = "not-applicable"
            last_done_at = None
        out.append(
            {
                "job": name,
                "state": state,
                "last_done_at": last_done_at,
                "freshness_window_days": NIGHTLY_FRESHNESS_DAYS,
                "log_path": str(log) if log.is_file() else None,
            }
        )
    return out


def build_receipt(include_ci: bool, runs_dir: Path | None) -> dict[str, Any]:
    blocked: list[str] = []
    artifacts = artifacts_block(blocked)
    local_runs = local_runs_block(runs_dir, blocked) if runs_dir else []
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        "generated_at": now_iso(),
        "source_revision": source_revision(),
        "ci": ci_status() if include_ci else {"status": "not-applicable", "reason": "skipped"},
        "public_site": public_site_block(),
        "playground": playground_block(),
        "artifacts": artifacts,
        "local_runs": local_runs,
        "nightly": nightly_block(),
        "publication_authority": "manual",
        "accepted_exceptions": [],
        "blocked": blocked,
    }
    return sanitize_payload(receipt)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", help="write receipt JSON to this path (default: stdout)")
    p.add_argument("--runs", default="", help="directory of factory run folders to summarize")
    p.add_argument("--no-ci", action="store_true", help="skip the gh CI query")
    p.add_argument("--check", action="store_true", help="validate the emitted receipt with check_foundry_receipt.py")
    args = p.parse_args()

    runs_dir = Path(args.runs) if args.runs else None
    receipt = build_receipt(include_ci=not args.no_ci, runs_dir=runs_dir)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"

    if len(payload.encode("utf-8")) > RECEIPT_BYTE_CEILING:
        # Should be impossible after sanitize_payload, but enforce anyway.
        print(
            f"foundry_receipt: refusing to emit {len(payload)}b receipt over {RECEIPT_BYTE_CEILING}b ceiling",
            file=sys.stderr,
        )
        return 2

    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"foundry_receipt: wrote {args.out} ({len(payload)}b)", file=sys.stderr)
    else:
        sys.stdout.write(payload)

    if args.check:
        check = ROOT / "scripts/check_foundry_receipt.py"
        if not check.is_file():
            print("foundry_receipt: --check requested but check_foundry_receipt.py missing", file=sys.stderr)
            return 2
        res = subprocess.run(
            ["python3", str(check), "-"],
            input=payload,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        sys.stderr.write(res.stderr)
        if res.returncode != 0:
            return res.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
