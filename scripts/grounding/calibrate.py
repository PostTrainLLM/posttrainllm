"""Free subscription Codex ceiling check; never provides the hidden gold answers."""

import json
import subprocess
import sys
import time

from prepare import OUT, ROOT, SYSTEM, write


def calibrate():
    target = OUT / "frontier-result.json"
    if target.exists():
        raise SystemExit(
            "Frontier result already exists; preserve the original calibration."
        )
    rows = []
    for name in ["dev", "test", "regression"]:
        rows.extend(
            json.loads(line)
            for line in (OUT / f"{name}.jsonl").read_text().splitlines()
        )
    sys.path.append(str(ROOT))
    from scripts.factory.frontier_cli import answer_schema, codex_command

    schema = answer_schema()
    write(OUT / "frontier-schema.json", schema)
    prompt = (
        SYSTEM
        + "\nFor regression questions use ordinary factual knowledge. No tools or files are needed. Return one answer per id.\n"
    )
    prompt += json.dumps([{k: row[k] for k in ["id", "prompt"]} for row in rows])
    (OUT / "frontier-prompt.txt").write_text(prompt)
    started = time.monotonic()
    command = codex_command(
        OUT / "frontier-schema.json", OUT / "frontier-answers.json", prompt
    )
    result = subprocess.run(
        command, cwd="/tmp", capture_output=True, text=True, timeout=300
    )
    if result.returncode:
        write(
            target,
            {
                "complete": False,
                "error": result.stderr[-2000:],
                "exit_code": result.returncode,
            },
        )
        raise SystemExit(
            "Frontier infrastructure failure; no small-model scoring is permitted."
        )
    response = json.loads((OUT / "frontier-answers.json").read_text())["answers"]
    answers = {r["id"]: r["answer"].strip().casefold() for r in response}
    passed = [r["id"] for r in rows if answers.get(r["id"]) == r["answer"].casefold()]
    valid = len(response) == len(rows) == len(answers) == len(passed)
    write(
        target,
        {
            "complete": True,
            "valid": valid,
            "model": "gpt-6.1-sol",
            "reasoning": "medium",
            "elapsed_seconds": time.monotonic() - started,
            "count": len(rows),
            "passed": len(passed),
            "failed_ids": [r["id"] for r in rows if r["id"] not in passed],
            "paid_usd": 0,
        },
    )
    print(target.read_text())
    if not valid:
        raise SystemExit(
            "Ceiling gate failed; no small-model accuracy may be reported."
        )


if __name__ == "__main__":
    calibrate()
