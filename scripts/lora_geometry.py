#!/usr/bin/env python3
"""Inspect TinyGPT TGLA LoRA/DoRA adapter geometry.

The script reports per-module effective update statistics without loading the
base model. It parses the TGLA header plus A/B matrices and summarizes the
Frobenius norm, stable rank, and rank after forming B @ A.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np


def read_tgla(path: Path) -> tuple[dict, list[tuple[np.ndarray, np.ndarray, np.ndarray | None]]]:
    data = path.read_bytes()
    if data[:4] != b"TGLA":
        raise SystemExit(f"{path}: not a TGLA adapter")
    version = struct.unpack_from("<I", data, 4)[0]
    if version not in (1, 2):
        raise SystemExit(f"{path}: unsupported TGLA version {version}")
    header_len = struct.unpack_from("<I", data, 8)[0]
    header = json.loads(data[12:12 + header_len].decode("utf-8"))
    cursor = 12 + header_len
    mats = []
    for entry in header["entries"]:
        a_count = int(np.prod(entry["loraAShape"]))
        b_count = int(np.prod(entry["loraBShape"]))
        a = np.frombuffer(data, dtype="<f4", count=a_count, offset=cursor).copy()
        cursor += a_count * 4
        b = np.frombuffer(data, dtype="<f4", count=b_count, offset=cursor).copy()
        cursor += b_count * 4
        a = a.reshape(entry["loraAShape"])
        b = b.reshape(entry["loraBShape"])
        m = None
        if entry.get("loraMShape"):
            m_count = int(np.prod(entry["loraMShape"]))
            m = np.frombuffer(data, dtype="<f4", count=m_count, offset=cursor).copy()
            cursor += m_count * 4
        mats.append((a, b, m))
    return header, mats


def low_rank_stats(a: np.ndarray, b: np.ndarray) -> tuple[int, float, float, float]:
    """Return rank, stable rank, Frobenius norm, spectral norm for B.T @ A.T.

    TGLA stores A=[in,r], B=[r,out]. The effective update is huge, but its
    non-zero spectrum is rank <= r. Compute all stats from r x r Gram products
    instead of materializing out x in matrices or running a large SVD.
    """
    u = b.T  # [out, r]
    v = a    # [in, r]
    gram_u = u.T @ u
    gram_v = v.T @ v
    fro_sq = float(np.trace(gram_u @ gram_v))
    if fro_sq <= 0.0:
        return 0, 0.0, 0.0, 0.0
    eigvals = np.linalg.eigvals(gram_u @ gram_v)
    eigvals = np.real(eigvals)
    eigvals = np.maximum(eigvals, 0.0)
    spectral_sq = float(np.max(eigvals)) if eigvals.size else 0.0
    spectral = spectral_sq ** 0.5
    rank = int(np.count_nonzero(eigvals > max(spectral_sq, 1.0) * 1e-6))
    stable = fro_sq / spectral_sq if spectral_sq else 0.0
    return rank, stable, fro_sq ** 0.5, spectral


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("adapters", nargs="+")
    p.add_argument("--out", default="", help="optional JSON summary path")
    p.add_argument("--top", type=int, default=12)
    args = p.parse_args()

    summaries = []
    for raw in args.adapters:
        path = Path(raw)
        header, mats = read_tgla(path)
        rows = []
        for entry, (a, b, m) in zip(header["entries"], mats):
            rank, srank, fro_norm, spectral_norm = low_rank_stats(a, b)
            rows.append({
                "name": entry["name"],
                "rank_config": header["rank"],
                "matrix_rank": rank,
                "stable_rank": round(srank, 4),
                "fro_norm": round(fro_norm, 6),
                "spectral_norm": round(spectral_norm, 6),
                "has_dora_magnitude": m is not None,
            })
        rows_sorted = sorted(rows, key=lambda r: r["fro_norm"], reverse=True)
        summaries.append({
            "path": str(path),
            "rank": header["rank"],
            "alpha": header["alpha"],
            "entries": len(rows),
            "target_suffixes": header.get("targetSuffixes", []),
            "has_dora": any(r["has_dora_magnitude"] for r in rows),
            "mean_stable_rank": round(float(np.mean([r["stable_rank"] for r in rows])) if rows else 0.0, 4),
            "top_by_fro_norm": rows_sorted[: args.top],
        })

    text = json.dumps({"adapters": summaries}, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
