#!/usr/bin/env python3
"""B26 deferred-tool parity report.

Consumes two EvalCompare.Row JSONL files from `tinygpt eval-bfcl`:

  python3 scripts/b26_deferred_parity_report.py \
    --full /tmp/bfcl-full.jsonl \
    --deferred /tmp/bfcl-deferred.jsonl \
    --out /tmp/b26-parity.json

The B26 ship rule is:
  1. deferred BFCL average is no more than 2pp below full mode, and
  2. average get_tool_info round-trips per sample is <= 2.

For the real B26 acceptance gate, pass `--require-hop-stats`. Current
`tinygpt eval-bfcl --tool-mode deferred` emits a
`bfcl/deferred_tools/get_tool_info_hops` metric row, and this report also
understands legacy per-row hop fields named `get_tool_info_hops`,
`tool_info_hops`, `meta_tool_hops`, or `deferred_tool_hops`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


HOP_KEYS = (
    "get_tool_info_hops",
    "tool_info_hops",
    "meta_tool_hops",
    "deferred_tool_hops",
)


def is_hop_metric(row: dict[str, Any]) -> bool:
    metric = str(row.get("metric") or "")
    subtask = str(row.get("subtask") or "")
    return metric in HOP_KEYS or subtask == "deferred_tools"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    if not rows:
        raise SystemExit(f"{path}: no rows")
    return rows


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("task") or ""),
        str(row.get("subtask") or ""),
        str(row.get("metric") or ""),
    )


def weighted_average(rows: list[dict[str, Any]]) -> float:
    num = 0.0
    den = 0
    for row in rows:
        if is_hop_metric(row):
            continue
        score = float(row.get("score", 0.0))
        n = int(row.get("n_examples") or 1)
        if not math.isfinite(score) or n <= 0:
            continue
        num += score * n
        den += n
    return num / den if den else 0.0


def matching_rows(full: list[dict[str, Any]],
                  deferred: list[dict[str, Any]]) -> list[dict[str, Any]]:
    full_by_key = {row_key(row): row for row in full if not is_hop_metric(row)}
    deferred_by_key = {row_key(row): row for row in deferred if not is_hop_metric(row)}
    keys = sorted(set(full_by_key) | set(deferred_by_key))
    rows = []
    for key in keys:
        f = full_by_key.get(key)
        d = deferred_by_key.get(key)
        rows.append({
            "task": key[0],
            "subtask": key[1] or None,
            "metric": key[2],
            "full_score": f.get("score") if f else None,
            "deferred_score": d.get("score") if d else None,
            "delta_pp": ((float(d["score"]) - float(f["score"])) * 100.0
                         if f and d else None),
            "n_examples": int((d or f or {}).get("n_examples") or 0),
            "present_in_full": f is not None,
            "present_in_deferred": d is not None,
        })
    return rows


def hop_values(rows: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for row in rows:
        if is_hop_metric(row):
            values.append(float(row.get("score", 0.0)))
            continue
        for key in HOP_KEYS:
            if key in row and row[key] is not None:
                values.append(float(row[key]))
                break
    return values


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", type=Path, required=True,
                   help="EvalCompare JSONL from full-schema mode")
    p.add_argument("--deferred", type=Path, required=True,
                   help="EvalCompare JSONL from deferred-tool mode")
    p.add_argument("--threshold-pp", type=float, default=2.0,
                   help="Allowed deferred regression in percentage points")
    p.add_argument("--max-hops", type=float, default=2.0,
                   help="Allowed average get_tool_info hops per sample")
    p.add_argument("--require-hop-stats", action="store_true",
                   help="Exit non-zero if hop stats are absent")
    p.add_argument("--out", type=Path, default=None,
                   help="Optional JSON report path")
    args = p.parse_args()

    full = read_jsonl(args.full)
    deferred = read_jsonl(args.deferred)
    full_avg = weighted_average(full)
    deferred_avg = weighted_average(deferred)
    delta_pp = (deferred_avg - full_avg) * 100.0
    rows = matching_rows(full, deferred)
    missing = [r for r in rows if not (r["present_in_full"] and r["present_in_deferred"])]

    hops = hop_values(deferred)
    avg_hops = sum(hops) / len(hops) if hops else None
    score_pass = delta_pp >= -args.threshold_pp and not missing
    hop_pass = (avg_hops is not None and avg_hops <= args.max_hops)
    hop_status = "pass" if hop_pass else ("missing" if avg_hops is None else "fail")

    report = {
        "full_average": full_avg,
        "deferred_average": deferred_avg,
        "delta_pp": delta_pp,
        "threshold_pp": args.threshold_pp,
        "score_gate": "pass" if score_pass else "fail",
        "avg_get_tool_info_hops": avg_hops,
        "max_hops": args.max_hops,
        "hop_gate": hop_status,
        "matched_rows": rows,
    }

    print("B26 deferred-tools parity")
    print(f"  full avg:     {full_avg:.3f}")
    print(f"  deferred avg: {deferred_avg:.3f}")
    print(f"  delta:        {delta_pp:+.1f}pp "
          f"(allowed regression: -{args.threshold_pp:.1f}pp)")
    print(f"  score gate:   {report['score_gate']}")
    if avg_hops is None:
        print("  hop gate:     missing (no hop-count fields in deferred rows)")
    else:
        print(f"  hop gate:     {hop_status} ({avg_hops:.2f} <= {args.max_hops:.2f})")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(f"  wrote {args.out}")

    if not score_pass:
        sys.exit(1)
    if args.require_hop_stats and not hop_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
