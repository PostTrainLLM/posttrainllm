"""Record aligned key → real-screen episodes inside a disposable Docker shell.

Only explicitly supplied recorder recipes execute; model output is never a
recipe. No host mounts, network, image pulls or privileged containers. Contract:
docs/factory/specialist-labs.md. The recorder is not a security boundary for
untrusted Docker images; use a known local image.
"""

from __future__ import annotations

import os
import pty
import select
import subprocess
import time
import tty
import uuid
import re

from terminal_codec import Screen, event_tokens


def image_identity(image):
    inspected = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", inspected):
        raise ValueError("local Docker image has no immutable identity")
    return inspected


def record(recipe, image, budget):
    import pyte

    image = image_identity(image)

    rows, cols = recipe.get("rows", 8), recipe.get("cols", 48)
    Screen.custom("", rows, cols)  # Validate before launching a process.
    events = recipe["events"]
    if not 1 <= len(events) <= 10000:
        raise ValueError("recipe needs 1–10000 events")
    for event in events:
        event_tokens(event)
    name = "posttrainllm-record-" + uuid.uuid4().hex[:12]
    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)
    command = [
        "docker",
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=32",
        "--memory=128m",
        "--cpus=0.5",
        "--tmpfs=/tmp:rw,nosuid,noexec,size=16m",
        "--workdir=/tmp",
        "--user=65534:65534",
        "-e",
        "TERM=xterm",
        "-e",
        "PS1=lab$ ",
        "-e",
        f"LINES={rows}",
        "-e",
        f"COLUMNS={cols}",
        "-i",
        "-t",
        "--entrypoint=/bin/sh",
        image,
        "-i",
    ]
    master, slave = pty.openpty()
    tty.setraw(slave)
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)

    def drain(minimum=0.0):
        start, last = time.monotonic(), time.monotonic()
        while time.monotonic() - start < 2:
            budget.check()
            ready, _, _ = select.select([master], [], [], 0.02)
            if ready:
                data = os.read(master, 65536)
                if not data:
                    raise RuntimeError(
                        "recorder shell exited; use a local image with /bin/sh"
                    )
                stream.feed(data)
                last = time.monotonic()
            if time.monotonic() - start >= minimum and time.monotonic() - last > 0.06:
                break

    def snapshot():
        lines = tuple(
            "".join(char if 32 <= ord(char) <= 126 else "?" for char in line)
            for line in screen.display
        )
        return Screen(
            lines,
            min(screen.cursor.y, rows - 1),
            min(screen.cursor.x, cols - 1),
            not screen.cursor.hidden,
        ).as_dict()

    try:
        return capture(recipe, budget, drain, snapshot, master, image)
    finally:
        # Only this invocation's named container is targeted, even on timeout.
        subprocess.run(
            ["docker", "container", "rm", "-f", name], capture_output=True, timeout=10
        )
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        os.close(master)


def capture(recipe, budget, drain, snapshot, master, image):
    rows, cols = recipe.get("rows", 8), recipe.get("cols", 48)
    events = recipe["events"]
    drain(0.3)
    os.write(
        master, f"stty rows {rows} cols {cols}; printf '\\033[2J\\033[H'\r".encode()
    )
    drain(0.3)
    initial = snapshot()
    frames = []
    for event in events:
        budget.check()
        if "keys" in event:
            os.write(master, bytes(event["keys"]))
        else:
            # A wait is an input with real elapsed time, capped by the budget.
            remaining = event["wait_ms"] / 1000
            while remaining > 0:
                budget.check()
                duration = min(remaining, 0.05)
                time.sleep(duration)
                remaining -= duration
        drain()
        frame = {"event": event, "screen": snapshot()}
        probe = recipe.get("probes", {}).get(str(len(frames)))
        if probe is not None:
            if probe not in [line.strip() for line in frame["screen"]["lines"]]:
                raise RuntimeError(
                    "probe output is not visible; add an explicit wait event to the recorder recipe"
                )
            frame["memory_probe_expected"] = probe
        frames.append(frame)
    return {
        "id": recipe["id"],
        "world_id": recipe.get("world_id", recipe["id"]),
        "family": recipe.get("family", "shell"),
        "seed": recipe.get("seed"),
        "world_conditions": {
            "image_id": image,
            "cwd": "/tmp",
            "initial_files": {},
            "programs": {"shell": "/bin/sh from the pinned image"},
            "environment": {
                "TERM": "xterm",
                "PS1": "lab$ ",
                "rows": rows,
                "cols": cols,
            },
        },
        "initial_screen": initial,
        "frames": frames,
        "source": {
            "kind": "real-docker-terminal",
            "image": image,
            "network": False,
            "host_mounts": False,
            "timing": "screen sampled after 60ms output quiescence; not an application completion oracle",
        },
    }


def synthetic_recipe(seed=7, rows=8, cols=48, memory=False):
    """Deterministic training recipe; random held-out names/values are separate seeds."""
    import random

    rng = random.Random(seed)
    filename = "note_" + format(rng.getrandbits(24), "x")
    value = "value_" + format(rng.getrandbits(32), "x")
    commands = [
        f"printf '{value}\\n' > {filename}\r",
        "pwd\r",
        "ls\r",
        f"cat {filename}\r",
    ]
    probes = {}
    if memory:
        second_file = "other_" + format(rng.getrandbits(24), "x")
        second_value = "value_" + format(rng.getrandbits(32), "x")
        commands = [
            commands[0],
            f"printf '{second_value}\\n' > {second_file}\r",
            "pwd\r",
            "ls\r",
            f"cat {filename}\r",
            f"cat {second_file}\r",
        ]
    events = []
    for index, command in enumerate(commands):
        events.extend({"keys": [byte]} for byte in command.encode("ascii"))
        # Output can arrive after the Enter event (especially with CPU quotas).
        # Represent elapsed time explicitly rather than labeling an unfinished
        # command's immediate frame as a completed memory readback.
        events.append({"wait_ms": 500})
        if memory and index >= len(commands) - 2:
            probes[str(len(events) - 1)] = (
                value if index == len(commands) - 2 else second_value
            )
    return {
        "id": f"terminal-{seed}",
        "seed": seed,
        "family": "memory" if memory else "shell",
        "rows": rows,
        "cols": cols,
        "events": events,
        "memory_probe": {"filename": filename, "value": value},
        "probes": probes,
    }
