"""One owned subprocess at a time, durable history and hard cancellation.

Contract: docs/factory/specialist-labs.md. Never signals a recorded/stale PID.
Run phases follow the existing factory lifecycle; jobs do not imply quality.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from common import digest, read_json, file_hash

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


class Jobs:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lease = (self.root / ".runtime.lock").open("a")
        try:
            fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise ValueError("another runtime owns this workspace") from None
        self.lock = threading.RLock()
        self.process = None
        self.active = None
        self.watchers = []
        for path in self.root.glob("*/state.json"):
            state = read_json(path)
            if state["status"] not in TERMINAL:
                self.update(
                    state["run_id"],
                    status="interrupted",
                    phase="failed",
                    error="Runtime stopped before completion. Start a new run; partial artifacts are not activated.",
                )

    def folder(self, key):
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", key):
            raise ValueError("invalid run id")
        return self.root / key

    def read(self, key, recipe=False):
        path = self.folder(key)
        state = read_json(path / "state.json")
        if (path / "progress.json").is_file():
            state["progress"] = read_json(path / "progress.json")
        if state["status"] == "completed":
            state["output"] = read_json(path / "result.json")
        if recipe:
            state["recipe"] = read_json(path / "request.json")
        return state

    def update(self, key, **values):
        with self.lock:
            path = self.folder(key) / "state.json"
            state = read_json(path)
            state.update(values, updated_at=now(), revision=state["revision"] + 1)
            atomic(path, state)

    def list(self):
        rows = [read_json(path) for path in self.root.glob("*/state.json")]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:100]

    def start(self, request):
        with self.lock:
            if self.active:
                raise ValueError("another job is running; wait or cancel it")
            key = uuid.uuid4().hex
            request = {
                **request,
                "acceptance": {
                    "primary_delta_min": 0,
                    "regression_delta_min": 0,
                    "decision": "report-only; no automatic ship",
                },
                "condition": {
                    "python": sys.version.split()[0],
                    "sources": {
                        p.name: file_hash(p) for p in Path(__file__).parent.glob("*.py")
                    },
                },
            }
            folder = self.folder(key)
            folder.mkdir()
            atomic(folder / "request.json", request)
            stamp = now()
            atomic(
                folder / "state.json",
                {
                    "schema_version": 1,
                    "run_id": key,
                    "revision": 1,
                    "mode": request["mode"],
                    "action": request["action"],
                    "created_at": stamp,
                    "updated_at": stamp,
                    "status": "queued",
                    "phase": "created",
                    "dataset_sha256": digest(request["payload"]),
                    "model": request.get("selection"),
                    "error": None,
                },
            )
            command = [
                sys.executable,
                str(Path(__file__).with_name("job_worker.py")),
                str(folder),
            ]
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.active = key
            self.update(
                key,
                status="running",
                phase="training" if request["action"] == "train" else "evaluating",
            )
            watcher = threading.Thread(
                target=self.watch, args=(key, self.process), daemon=True
            )
            self.watchers.append(watcher)
            watcher.start()
            return self.read(key)

    def stop_process(self, process):
        if process.poll() is None:
            self.signal_process(process, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.signal_process(process, signal.SIGKILL)
                process.wait(timeout=3)

    def signal_process(self, process, kind):
        try:
            os.killpg(process.pid, kind)
        except ProcessLookupError:
            pass

    def watch(self, key, process):
        deadline = time.monotonic() + 180
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
        with self.lock:
            state = self.read(key)
            if state["status"] not in TERMINAL:
                if process.poll() is None:
                    self.stop_process(process)
                    self.update(
                        key,
                        status="failed",
                        phase="failed",
                        error="Job exceeded its 180-second wall-time limit.",
                    )
                elif (
                    process.returncode
                    or not (self.folder(key) / "result.json").is_file()
                ):
                    error_path = self.folder(key) / "error.json"
                    error = (
                        read_json(error_path)["error"]
                        if error_path.is_file()
                        else "Worker stopped without a complete result."
                    )
                    self.update(key, status="failed", phase="failed", error=error)
                else:
                    self.update(
                        key,
                        status="completed",
                        phase="trained" if state["action"] == "train" else "evaluated",
                    )
            if self.active == key:
                self.active = self.process = None

    def cancel(self, key):
        with self.lock:
            if key != self.active or self.process is None:
                raise ValueError("only the current running job can be cancelled")
            self.stop_process(self.process)
            self.update(
                key,
                status="cancelled",
                phase="failed",
                error="Cancelled by operator. Partial artifacts remain unqualified.",
            )
            self.active = self.process = None
            return self.read(key)

    def close(self):
        with self.lock:
            if self.active:
                self.cancel(self.active)
            fcntl.flock(self.lease, fcntl.LOCK_UN)
            self.lease.close()
        for watcher in self.watchers:
            watcher.join(timeout=5)
