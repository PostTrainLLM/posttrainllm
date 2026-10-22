"""Frozen first-20 BFCL simple_python regression using the existing AST scorer."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time

from prepare import OUT, ROOT, write


def harness():
    source = OUT / "bfcl-source"
    (source / "bfcl_eval").mkdir(parents=True, exist_ok=True)
    os.environ["BFCL_ROOT"] = str(source)
    sys.path.insert(0, str(ROOT / "scripts/bfcl"))
    import bfcl_ast_eval

    return bfcl_ast_eval


def fixtures():
    frozen = json.loads((OUT / "bfcl-admission.json").read_text())
    assert (
        hashlib.sha256((OUT / "bfcl.jsonl").read_bytes()).hexdigest()
        == frozen["sha256"]
    )
    return [json.loads(line) for line in (OUT / "bfcl.jsonl").read_text().splitlines()]


def judge(matcher, rows, answers):
    result = []
    for row in rows:
        text = answers.get(row["id"], "")
        calls = matcher.extract_calls(text)
        result.append(
            {
                "id": row["id"],
                "output": text,
                "passed": len(calls) == len(row["ground_truth"])
                and matcher.ast_match(calls, row["ground_truth"]),
            }
        )
    return result


def calibrate():
    target = OUT / "bfcl-frontier-result.json"
    if target.exists():
        raise SystemExit("Preserve original BFCL calibration.")
    matcher, rows = harness(), fixtures()
    requests = []
    for row in rows:
        system, user = matcher.build_prompt(row["function"], row["question"])
        requests.append({"id": row["id"], "system": system, "user": user})
    schema = json.loads((OUT / "frontier-schema.json").read_text())
    write(OUT / "bfcl-frontier-schema.json", schema)
    prompt = (
        "Solve each independent function-calling request. No tools or file access needed. Return one answer string per id in the requested format.\n"
        + json.dumps(requests)
    )
    (OUT / "bfcl-frontier-prompt.txt").write_text(prompt)
    started = time.monotonic()
    sys.path.append(str(ROOT))
    from scripts.factory.frontier_cli import codex_command

    command = codex_command(
        OUT / "bfcl-frontier-schema.json", OUT / "bfcl-frontier-answers.json", prompt
    )
    result = subprocess.run(
        command, cwd="/tmp", capture_output=True, text=True, timeout=300
    )
    if result.returncode:
        write(
            target, {"complete": False, "error": result.stderr[-2000:], "paid_usd": 0}
        )
        raise SystemExit(
            "BFCL frontier infrastructure failure; do not grade local models."
        )
    answers = json.loads((OUT / "bfcl-frontier-answers.json").read_text())["answers"]
    scored = judge(matcher, rows, {r["id"]: r["answer"] for r in answers})
    valid = len(answers) == len(rows) and all(r["passed"] for r in scored)
    write(
        target,
        {
            "complete": True,
            "valid": valid,
            "model": "gpt-6.1-sol",
            "count": len(rows),
            "passed": sum(r["passed"] for r in scored),
            "elapsed_seconds": time.monotonic() - started,
            "paid_usd": 0,
            "rows": scored,
        },
    )
    print(
        json.dumps(
            {
                "valid": valid,
                "passed": sum(r["passed"] for r in scored),
                "count": len(rows),
            }
        )
    )


def evaluate(name):
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    assert json.loads((OUT / "bfcl-frontier-result.json").read_text())["valid"]
    target = OUT / f"bfcl-{name}-result.json"
    if target.exists():
        raise SystemExit("Preserve the original BFCL local result.")
    started = time.monotonic()
    mx.set_memory_limit(12 * 1024**3)
    mx.set_cache_limit(2 * 1024**3)
    mx.random.seed(20020261022)
    model_path = json.loads((OUT / "model-source.json").read_text())["local_path"]
    adapter = str(OUT / "adapters" / name) if name != "baseline" else None
    model, tokenizer = load(model_path, adapter_path=adapter)
    matcher, rows = harness(), fixtures()
    answers, times = {}, []
    for row in rows:
        system, user = matcher.build_prompt(row["function"], row["question"])
        prompt = tokenizer.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        begin = time.monotonic()
        answers[row["id"]] = "".join(
            r.text
            for r in stream_generate(
                model, tokenizer, prompt, max_tokens=192, sampler=make_sampler(temp=0)
            )
        )
        times.append(time.monotonic() - begin)
        scored = judge(matcher, rows[: len(answers)], answers)
        write(
            target,
            {
                "complete": len(answers) == len(rows),
                "count": len(answers),
                "passed": sum(r["passed"] for r in scored),
                "elapsed_seconds": time.monotonic() - started,
                "latencies_seconds": times,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "mlx_peak_memory_bytes": mx.get_peak_memory(),
                "rows": scored,
                "paid_usd": 0,
            },
        )
    print(
        json.dumps(
            {
                "name": name,
                "passed": sum(r["passed"] for r in scored),
                "count": len(rows),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["calibrate", "baseline", "ordinary", "perturbation"]
    )
    args = parser.parse_args()
    calibrate() if args.mode == "calibrate" else evaluate(args.mode)
