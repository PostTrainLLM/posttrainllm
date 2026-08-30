"""Resolve BFCL across its standalone and Gorilla-monorepo checkout layouts."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_bfcl_root() -> Path:
    configured = os.environ.get("BFCL_ROOT")
    cache_root = (
        Path.home()
        / ".cache/posttrainllm/datasets/_external/gorilla-bfcl"
        / "berkeley-function-call-leaderboard"
    )
    candidates = [
        Path(configured).expanduser() if configured else None,
        cache_root,
        cache_root / "berkeley-function-call-leaderboard",
    ]

    for candidate in candidates:
        if candidate and (candidate / "bfcl_eval").is_dir():
            return candidate.resolve()

    checked = ", ".join(str(path) for path in candidates if path)
    raise FileNotFoundError(
        "BFCL checkout not found. Set BFCL_ROOT to the directory containing "
        f"bfcl_eval. Checked: {checked}"
    )


def resolve_bfcl_data() -> Path:
    return resolve_bfcl_root() / "bfcl_eval/data"
