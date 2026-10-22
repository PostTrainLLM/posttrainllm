"""Execute the already frozen remaining issue-200 comparisons once, serially."""

import json
import subprocess
import sys
import time

from prepare import OUT, ROOT, write


def run():
    output = OUT / "execution.json"
    if output.exists():
        raise SystemExit(
            "Execution receipt exists; inspect it rather than retrying silently."
        )
    started = time.monotonic()
    baseline = json.loads((OUT / "baseline-result.json").read_text())
    tiny = json.loads((OUT / "ordinary-tiny-gate.json").read_text())
    assert baseline["complete"] and tiny["passed"]
    commands = [
        ["train.py", "ordinary", "full"],
        ["train.py", "perturbation", "tiny"],
        ["train.py", "perturbation", "full"],
        ["bfcl.py", "calibrate"],
        ["bfcl.py", "baseline"],
        ["evaluate.py", "ordinary", "--adapter", str(OUT / "adapters/ordinary")],
        ["bfcl.py", "ordinary"],
        [
            "evaluate.py",
            "perturbation",
            "--adapter",
            str(OUT / "adapters/perturbation"),
        ],
        ["bfcl.py", "perturbation"],
    ]
    steps = []
    (OUT / "logs").mkdir(exist_ok=True)
    for index, command in enumerate(commands):
        remaining = 3600 - baseline["elapsed_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            raise SystemExit("Total compute budget exhausted; reject the run.")
        log = OUT / "logs" / f"{index + 1:02d}-{command[0][:-3]}-{command[1]}.log"
        begin = time.monotonic()
        with log.open("w") as stream:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/grounding" / command[0]),
                    *command[1:],
                ],
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=min(900, remaining),
            )
        steps.append(
            {
                "command": command,
                "exit_code": result.returncode,
                "elapsed_seconds": time.monotonic() - begin,
                "log": str(log.relative_to(ROOT)),
            }
        )
        write(
            output,
            {
                "complete": len(steps) == len(commands) and result.returncode == 0,
                "steps": steps,
                "elapsed_seconds": time.monotonic() - started,
                "paid_usd": 0,
            },
        )
        print(json.dumps(steps[-1]), flush=True)
        if result.returncode:
            raise SystemExit(f"Step failed; inspect {log} before any continuation.")


if __name__ == "__main__":
    run()
