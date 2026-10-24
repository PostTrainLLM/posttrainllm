"""Local specialist data identity, finite JSON, bounded work and provenance.

Contract: docs/factory/specialist-labs.md. No model calls or downloads at import.
"""

from __future__ import annotations

import hashlib
import json
import math
import resource
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def file_hash(path) -> str:
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwriting evidence or checkpoints by default.
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def read_rows(path):
    rows = [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]
    ids = [row["id"] for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("dataset must be nonempty with unique ids")
    return rows


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def softmax(logits, temperature=1.0):
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("need at least two finite option logits")
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    values = values / temperature
    values -= values.max()
    values = np.exp(values)
    return values / values.sum()


def frontier_answers(schema, out, prompt):
    """One subscription-CLI ceiling request; refuse any tool-using trajectory."""
    import subprocess
    import sys

    sys.path.insert(0, str(ROOT))
    from scripts.factory.frontier_cli import codex_command

    result = subprocess.run(
        codex_command(schema, out / "answers.json", prompt, json_events=True),
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError(
            "frontier infrastructure failure; local capability accuracy is prohibited"
        )
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    kinds = [event["item"].get("type") for event in events if "item" in event]
    if any(kind not in ("agent_message", "reasoning") for kind in kinds):
        raise ValueError("frontier used tools; this ceiling is invalid")
    return read_json(out / "answers.json")["answers"], sorted(set(kinds))


class Budget:
    """Cooperative deadline plus thread cap; not an OS sandbox or hard RAM limit."""

    def __init__(self, seconds=60.0, threads=2):
        if not 0 < seconds <= 3600 or not 1 <= threads <= 2:
            raise ValueError("seconds must be in (0,3600], threads in [1,2]")
        self.seconds = seconds
        self.threads = threads
        self.started = time.monotonic()

    def check(self):
        if time.monotonic() - self.started >= self.seconds:
            raise TimeoutError("specialist work budget exhausted")

    def torch(self):
        import torch

        torch.set_num_threads(self.threads)
        return torch

    def measurements(self):
        import sys

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "elapsed_seconds": time.monotonic() - self.started,
            "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
            "paid_usd": 0,
            "pytorch_thread_cap": self.threads,
            "gpu_memory_bytes": None,
            "budget_enforcement": "cooperative wall deadline; no hard RAM sandbox",
        }
