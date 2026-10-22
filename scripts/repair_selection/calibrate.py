"""Free frontier repair calibration before grading any small-model repair."""

import hashlib
import json
import subprocess
import sys
import time

from executor import clean, execute, verify_executor
from prepare import OUT, ROOT, write

INSTRUCTION = (
    "Repair the supplied Python function to satisfy the specification for all inputs. "
    "Return only a single def candidate(...) function, no prose, imports, decorators, "
    "file/network access or type annotations. Builtins and ordinary list/string/dict methods are enough."
)


def request(task):
    return {
        "id": task["id"],
        "instruction": INSTRUCTION,
        "specification": task["spec"],
        "buggy_code": task["buggy_code"],
        "public_examples": task["public"],
    }


def frontier_request(tasks, target):
    sys.path.append(str(ROOT))
    from scripts.factory.frontier_cli import answer_schema, codex_command

    schema = answer_schema()
    write(OUT / "frontier-schema.json", schema)
    prompt = "Solve each independent repair. Do not use tools or read files; solve only from this prompt. Answer strings must contain repaired Python.\n"
    prompt += json.dumps([request(task) for task in tasks])
    (OUT / "frontier-prompt.txt").write_text(prompt)
    started = time.monotonic()
    result = subprocess.run(
        codex_command(
            OUT / "frontier-schema.json",
            OUT / "frontier-answers.json",
            prompt,
            json_events=True,
        ),
        cwd="/tmp",
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode:
        write(
            target, {"complete": False, "error": result.stderr[-2000:], "paid_usd": 0}
        )
        raise SystemExit(
            "Frontier infrastructure failure; no local-model accuracy is permitted."
        )
    return result, started


def calibrate():
    target = OUT / "frontier-result.json"
    if target.exists():
        raise SystemExit("Preserve the original calibration.")
    contract = json.loads((OUT / "contract.json").read_text())
    assert (
        hashlib.sha256((OUT / "tasks.jsonl").read_bytes()).hexdigest()
        == contract["data_sha256"]
    )
    verify_executor(contract)
    tasks = [
        json.loads(line) for line in (OUT / "tasks.jsonl").read_text().splitlines()
    ]
    result, started = frontier_request(tasks, target)
    kinds = []
    for line in result.stdout.splitlines():
        event = json.loads(line)
        if "item" in event:
            kinds.append(event["item"].get("type"))
    assert all(kind in ["agent_message", "reasoning"] for kind in kinds), kinds
    answers = json.loads((OUT / "frontier-answers.json").read_text())["answers"]
    mapping = {row["id"]: clean(row["answer"]) for row in answers}
    rows = []
    for task in tasks:
        result = execute(
            mapping.get(task["id"], ""),
            task["public"] + task["hidden"],
            "frontier-" + task["id"],
        )
        rows.append({"id": task["id"], "passed": result["passed"]})
    valid = len(mapping) == len(answers) == len(tasks) and all(
        row["passed"] for row in rows
    )
    write(
        target,
        {
            "complete": True,
            "valid": valid,
            "model": "gpt-6.1-sol",
            "count": len(tasks),
            "executor_source_sha256": hashlib.sha256(
                open(__file__.replace("calibrate.py", "executor.py"), "rb").read()
            ).hexdigest(),
            "passed": sum(row["passed"] for row in rows),
            "elapsed_seconds": time.monotonic() - started,
            "observed_item_types": sorted(set(kinds)),
            "rows": rows,
            "paid_usd": 0,
        },
    )
    print(target.read_text())
    if not valid:
        raise SystemExit(
            "Frontier ceiling failed; no local repair accuracy is permitted."
        )


if __name__ == "__main__":
    calibrate()
