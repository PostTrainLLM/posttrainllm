#!/usr/bin/env python3
"""Performance harness for the routed SQL specialist generate path.

Mirrors the conventions of scripts/run_sql_routed_generate.py (argparse,
dataclasses, stdlib only). Measures, per row of an eval fixture:

- wall-clock generation latency (p50 / p95 / mean, in ms)
- child-process peak RSS (via os.wait4 rusage; macOS reports bytes,
  Linux reports KB -- both converted to MB)
- tokens/sec, approximated as whitespace-token count of the child's
  stdout over that row's generation wall time. This is a coarse
  approximation (whitespace split, not the model tokenizer) and is
  documented in --help.

The harness invokes a command once per row. The command is a template
string with optional placeholders:

- {row_file}  -> path to a temp .jsonl containing only this row
- {prompt}    -> the row's `prompt` field (shell-safe substituted into
                 a single argv token)

In mock mode (--mock), --mock-cmd is used instead of --cmd, so no model
is required. Output JSON is shaped for direct paste into a factory run
report (docs/factory/run-schema.md): latency_ms, peak_rss_mb,
tokens_per_s, command, mock.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RowResult:
    index: int
    latency_ms: float
    peak_rss_mb: float
    tokens: int
    tokens_per_s: float
    returncode: int


@dataclass
class Report:
    rows: int
    latency_ms: dict
    peak_rss_mb: float
    tokens_per_s: float
    command: str
    mock: bool
    failures: int = 0
    per_row: list = field(default_factory=list)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _rss_to_mb(ru_maxrss: int) -> float:
    # macOS ru_maxrss is in bytes; Linux (and POSIX spec) is in kilobytes.
    if _is_macos():
        return ru_maxrss / (1024 * 1024)
    return ru_maxrss / 1024


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    # Linear interpolation between closest ranks.
    k = (len(sorted_vals) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _render_cmd(template: str, row: dict, row_file: Path) -> list[str]:
    """Split a command template on shell rules and substitute placeholders.

    Substitution happens per-token after shlex.split, so {prompt} is injected
    as a single argv element (no shell re-parsing). Unknown placeholders are
    left intact.
    """
    tokens = shlex.split(template)
    rendered: list[str] = []
    for tok in tokens:
        if "{row_file}" in tok:
            tok = tok.replace("{row_file}", str(row_file))
        if "{prompt}" in tok:
            tok = tok.replace("{prompt}", str(row.get("prompt") or ""))
        rendered.append(tok)
    return rendered


def run_one(
    cmd_argv: list[str],
    row: dict,
    row_file: Path,
) -> RowResult:
    """Run the command for one row and measure latency, RSS, tokens."""
    start = time.perf_counter()
    # stdout is captured for token counting; stderr is dropped to avoid
    # pipe-buffer deadlock on chatty children. Output for SQL generation
    # and for the mock stand-in is small, so a blocking read until EOF
    # is safe.
    proc = subprocess.Popen(
        cmd_argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    out_text = ""
    try:
        assert proc.stdout is not None
        out_text = proc.stdout.read()
    finally:
        # os.wait4 reaps the child and returns its rusage. We do NOT call
        # proc.wait() afterwards (the child is already reaped).
        pid, status, rusage = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
    elapsed = time.perf_counter() - start
    latency_ms = elapsed * 1000.0
    peak_rss_mb = _rss_to_mb(rusage.ru_maxrss)
    tokens = len(out_text.split())
    tokens_per_s = (tokens / elapsed) if elapsed > 0 else 0.0
    return RowResult(
        index=int(row.get("_row_index", -1)),
        latency_ms=latency_ms,
        peak_rss_mb=peak_rss_mb,
        tokens=tokens,
        tokens_per_s=tokens_per_s,
        returncode=proc.returncode,
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Measure per-row latency, child peak RSS, and tokens/sec for the "
            "routed SQL generate path. tokens/sec is approximated as "
            "whitespace-token count of child stdout over per-row wall time "
            "(NOT the model tokenizer)."
        ),
    )
    p.add_argument("--data", required=True, help="input .jsonl fixture rows")
    p.add_argument("--limit", type=int, default=0, help="use only the first N rows (0 = all)")
    p.add_argument(
        "--cmd",
        default="",
        help=(
            "command template for real generation. Placeholders: "
            "{row_file} (temp .jsonl with this row), {prompt} (row prompt)."
        ),
    )
    p.add_argument(
        "--mock-cmd",
        default="",
        help="offline stand-in command template (same placeholders as --cmd)",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="use --mock-cmd instead of --cmd (no model required)",
    )
    p.add_argument("--out", required=True, help="path to write the JSON report")
    args = p.parse_args()

    if args.mock:
        if not args.mock_cmd:
            p.error("--mock requires --mock-cmd")
        cmd_template = args.mock_cmd
    else:
        if not args.cmd:
            p.error("--cmd is required (or pass --mock with --mock-cmd)")
        cmd_template = args.cmd

    rows = read_jsonl(Path(args.data))
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    results: list[RowResult] = []
    failures = 0
    with tempfile.TemporaryDirectory(prefix="tinygpt-sql-perf-") as td:
        tmp = Path(td)
        for idx, row in enumerate(rows):
            row = dict(row)
            row["_row_index"] = idx
            row_file = tmp / f"row-{idx}.jsonl"
            row_file.write_text(
                json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            cmd_argv = _render_cmd(cmd_template, row, row_file)
            try:
                res = run_one(cmd_argv, row, row_file)
            except Exception as e:  # noqa: BLE001 - report and continue
                print(f"perf: row {idx} failed: {e}", file=sys.stderr)
                failures += 1
                continue
            if res.returncode != 0:
                failures += 1
            results.append(res)

    if not results:
        report = Report(
            rows=0,
            latency_ms={"p50": 0.0, "p95": 0.0, "mean": 0.0},
            peak_rss_mb=0.0,
            tokens_per_s=0.0,
            command=cmd_template,
            mock=args.mock,
            failures=failures,
        )
    else:
        latencies = sorted(r.latency_ms for r in results)
        peak_rss = max(r.peak_rss_mb for r in results)
        total_tokens = sum(r.tokens for r in results)
        total_wall = sum(r.latency_ms for r in results) / 1000.0
        tps = (total_tokens / total_wall) if total_wall > 0 else 0.0
        report = Report(
            rows=len(results),
            latency_ms={
                "p50": round(_percentile(latencies, 0.50), 3),
                "p95": round(_percentile(latencies, 0.95), 3),
                "mean": round(statistics.fmean(latencies), 3),
            },
            peak_rss_mb=round(peak_rss, 3),
            tokens_per_s=round(tps, 3),
            command=cmd_template,
            mock=args.mock,
            failures=failures,
            per_row=[
                {
                    "index": r.index,
                    "latency_ms": round(r.latency_ms, 3),
                    "peak_rss_mb": round(r.peak_rss_mb, 3),
                    "tokens": r.tokens,
                    "tokens_per_s": round(r.tokens_per_s, 3),
                    "returncode": r.returncode,
                }
                for r in results
            ],
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.__dict__, ensure_ascii=False, indent=2) + "\n")
    print(
        f"perf: {report.rows} rows mock={report.mock} "
        f"latency p50={report.latency_ms['p50']}ms p95={report.latency_ms['p95']}ms "
        f"peak_rss={report.peak_rss_mb}MB tps={report.tokens_per_s} "
        f"failures={report.failures} -> {out_path}"
    )


if __name__ == "__main__":
    main()
