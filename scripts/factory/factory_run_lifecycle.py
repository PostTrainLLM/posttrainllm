#!/usr/bin/env python3
"""Schema-parity bridge for metadata-only factory-run assembly.

TinyGPTIO remains the authoritative implementation. This module mirrors only
the subset needed by ``assemble_factory_run.py`` and is exercised against the
typed Swift decoder by the lifecycle smoke.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
STATUS_FILE = "run-status.json"
CURRENT_POINTER_FILE = "current-run.json"
LATEST_POINTER_FILE = "latest-run.json"
LOCK_DIR = ".run-status.lock"

TERMINAL = {"decided", "failed"}
NORMAL = {
    "created": "data-ready",
    "data-ready": "training",
    "training": "trained",
    "trained": "evaluating",
    "evaluating": "evaluated",
    "evaluated": "packaging",
    "packaging": "packaged",
    "packaged": "reporting",
    "reporting": "decided",
}
ALTERNATE = {
    ("created", "evaluating"),
    ("data-ready", "evaluating"),
    ("created", "reporting"),
    ("data-ready", "reporting"),
    ("trained", "reporting"),
    ("evaluated", "reporting"),
}
PHASES = set(NORMAL) | set(NORMAL.values()) | {"failed"}
REASON_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
PRIVATE_SUMMARY_MARKERS = (
    "prompt",
    "completion",
    "gold",
    "prediction",
    "trajectory",
    "checkpoint",
    "weights",
    "optimizer",
    "api key",
    "secret",
    "password",
    "credential",
    "dataset content",
    "output text",
    "token",
)


class LifecycleError(RuntimeError):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def validate_status(status: dict[str, Any]) -> None:
    if status.get("schema_version") != SCHEMA_VERSION:
        raise LifecycleError("unsupported lifecycle schema_version")
    if not status.get("run_id"):
        raise LifecycleError("run_id is required")
    if not isinstance(status.get("revision"), int) or status["revision"] < 1:
        raise LifecycleError("revision must be >= 1")
    if status.get("phase") not in PHASES:
        raise LifecycleError(f"invalid phase: {status.get('phase')!r}")
    transition = status.get("last_transition")
    if (
        not isinstance(transition, dict)
        or not transition.get("source")
        or not transition.get("command")
    ):
        raise LifecycleError("last_transition source and command are required")
    failure = status.get("failure")
    if status["phase"] == "failed":
        if not isinstance(failure, dict):
            raise LifecycleError("failed phase requires failure")
        if not REASON_RE.fullmatch(str(failure.get("code", ""))):
            raise LifecycleError("failure code must be machine-readable")
        summary = str(failure.get("summary", ""))
        if (
            not summary
            or len(summary) > 240
            or "\n" in summary
            or "\r" in summary
            or any(marker in summary.lower() for marker in PRIVATE_SUMMARY_MARKERS)
        ):
            raise LifecycleError("failure summary must be one bounded line")
    elif failure is not None:
        raise LifecycleError("failure is allowed only for failed phase")


def read_status(run_dir: Path) -> dict[str, Any]:
    path = run_dir / STATUS_FILE
    if not path.is_file():
        raise LifecycleError(f"missing {STATUS_FILE}")
    status = read_json(path)
    validate_status(status)
    config = read_json(run_dir / "config.json")
    if status["run_id"] != config.get("run_id"):
        raise LifecycleError("run-status run_id does not match config.json")
    if status["phase"] == "decided" and not (run_dir / "decision.json").is_file():
        raise LifecycleError("decided phase requires decision.json")
    return status


@contextmanager
def lifecycle_lock(run_dir: Path) -> Iterator[None]:
    lock = run_dir / LOCK_DIR
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise LifecycleError(f"lifecycle lock conflict at {lock}") from exc
    try:
        atomic_write_json(
            lock / "owner.json",
            {"pid": os.getpid(), "acquired_at": now_iso()},
        )
        yield
    finally:
        for child in lock.iterdir() if lock.is_dir() else []:
            child.unlink(missing_ok=True)
        lock.rmdir()


def initialize(run_dir: Path, *, source: str = "python-assembler") -> dict[str, Any]:
    if (run_dir / STATUS_FILE).exists():
        return read_status(run_dir)
    with lifecycle_lock(run_dir):
        if (run_dir / STATUS_FILE).exists():
            return read_status(run_dir)
        return _initialize_unlocked(run_dir, source=source)


def _initialize_unlocked(
    run_dir: Path, *, source: str = "python-assembler"
) -> dict[str, Any]:
    config = read_json(run_dir / "config.json")
    run_id = config.get("run_id")
    if not run_id:
        raise LifecycleError("config.run_id is required")
    status = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "revision": 1,
        "phase": "created",
        "updated_at": now_iso(),
        "last_transition": {
            "source": source,
            "command": "python3 scripts/factory/assemble_factory_run.py",
            "reason": None,
        },
        "parent_run_id": None,
        "successor_run_id": None,
        "failure": None,
        "imported": False,
        "import_evidence": [],
    }
    validate_status(status)
    atomic_write_json(run_dir / STATUS_FILE, status)
    refresh_pointers(run_dir.parent)
    return status


def transition(
    run_dir: Path,
    target: str,
    expected_revision: int,
    *,
    reason: str | None = None,
    failure: dict[str, str] | None = None,
    source: str = "python-assembler",
) -> dict[str, Any]:
    with lifecycle_lock(run_dir):
        current = read_status(run_dir)
        if current["revision"] != expected_revision:
            raise LifecycleError(
                f"stale lifecycle revision {expected_revision}; current is {current['revision']}"
            )
        origin = current["phase"]
        if origin in TERMINAL:
            raise LifecycleError(f"{origin} is terminal; create a linked retry run")
        if target != "failed":
            if NORMAL.get(origin) == target:
                pass
            elif (origin, target) in ALTERNATE:
                if not reason or not REASON_RE.fullmatch(reason):
                    raise LifecycleError(
                        f"{origin} -> {target} requires machine-readable reason"
                    )
            else:
                raise LifecycleError(
                    f"illegal lifecycle transition {origin} -> {target}"
                )
        if target == "failed":
            if not isinstance(failure, dict):
                raise LifecycleError("failed transition requires sanitized failure")
        elif failure is not None:
            raise LifecycleError("failure is allowed only for failed phase")
        if target == "decided" and not (run_dir / "decision.json").is_file():
            raise LifecycleError("decided phase requires decision.json")

        status = {
            **current,
            "revision": current["revision"] + 1,
            "phase": target,
            "updated_at": now_iso(),
            "last_transition": {
                "source": source,
                "command": "python3 scripts/factory/assemble_factory_run.py",
                "reason": reason,
            },
            "failure": failure,
        }
        validate_status(status)
        atomic_write_json(run_dir / STATUS_FILE, status)
        refresh_pointers(run_dir.parent)
        return status


def fail_sanitized(run_dir: Path, status: dict[str, Any]) -> None:
    if status["phase"] in TERMINAL:
        return
    try:
        transition(
            run_dir,
            "failed",
            status["revision"],
            failure={
                "code": "assembly-failed",
                "summary": "Factory run metadata assembly could not complete.",
            },
        )
    except Exception:
        # Preserve the original assembly failure. Lifecycle repair remains
        # available through the native reconcile command.
        pass


def _records(root: Path) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    if not root.is_dir():
        return records
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            status = read_status(run_dir)
        except Exception:
            continue
        records.append((run_dir.relative_to(root).as_posix(), status))
    records.sort(key=lambda item: item[0])
    records.sort(key=lambda item: item[1]["updated_at"], reverse=True)
    return records


def _pointer(relative: str, status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "relative_run_path": relative,
        "run_id": status["run_id"],
        "lifecycle_revision": status["revision"],
        "phase": status["phase"],
        "updated_at": status["updated_at"],
    }


def refresh_pointers(root: Path) -> None:
    records = _records(root)
    active = next((item for item in records if item[1]["phase"] not in TERMINAL), None)
    terminal = next((item for item in records if item[1]["phase"] in TERMINAL), None)
    for name, selected in (
        (CURRENT_POINTER_FILE, active),
        (LATEST_POINTER_FILE, terminal),
    ):
        path = root / name
        if selected:
            atomic_write_json(path, _pointer(*selected))
        else:
            path.unlink(missing_ok=True)
