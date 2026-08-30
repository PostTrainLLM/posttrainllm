#!/usr/bin/env python3
"""Blend public text-to-SQL rows with local execution-grounded SQL rows.

The public-only adapter beat the small public T5 baseline but regressed the
synthetic execution fixture. This builder makes that tradeoff explicit and
reproducible by weighting both sources in one SFT corpus.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
        + "\n"
    )


def weighted_rows(rows: list[dict], repeat: int, source: str) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        for idx in range(repeat):
            r = dict(row)
            r["id"] = f"{row.get('id', source)}-{source}-w{idx}"
            r["blend_source"] = source
            out.append(r)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--public-train", default="evals/sql-public-bmc2-train-v4-joinweighted/train.jsonl")
    p.add_argument("--synthetic-train", default="evals/sql-poc-expanded/train.jsonl")
    p.add_argument("--out", default="evals/sql-blend-public-synthetic-v1")
    p.add_argument("--public-repeat", type=int, default=1)
    p.add_argument("--synthetic-repeat", type=int, default=30)
    args = p.parse_args()

    public_rows = read_jsonl(Path(args.public_train))
    synthetic_rows = read_jsonl(Path(args.synthetic_train))

    rows = (
        weighted_rows(public_rows, args.public_repeat, "public")
        + weighted_rows(synthetic_rows, args.synthetic_repeat, "synthetic")
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dump_jsonl(out / "train.jsonl", rows)

    counts = collections.Counter(row["blend_source"] for row in rows)
    curriculum = collections.Counter(
        row.get("curriculum") or row.get("domain") or "unknown" for row in rows
    )
    manifest = {
        "public_train": args.public_train,
        "synthetic_train": args.synthetic_train,
        "public_repeat": args.public_repeat,
        "synthetic_repeat": args.synthetic_repeat,
        "rows": len(rows),
        "source_counts": dict(sorted(counts.items())),
        "curriculum_or_domain_counts": dict(sorted(curriculum.items())),
        "gate": {
            "public_exact_min": 0.484,
            "synthetic_execution_target": 0.860,
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(rows)} blend rows to {out / 'train.jsonl'}")
    print(dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
