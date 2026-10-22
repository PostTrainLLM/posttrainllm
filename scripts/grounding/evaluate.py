"""Evaluate a frozen base/adapter after the frontier gate, preserving raw outputs."""

import argparse
import hashlib
import json
import resource
import time

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler

from prepare import OUT, SYSTEM, write


def score(rows):
    present = [r for r in rows if r.get("present") is True]
    absent = [r for r in rows if r.get("present") is False]
    regression = [r for r in rows if "present" not in r]

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    return {
        "answerable_accuracy": mean([r["correct"] for r in present]),
        "unsupported_answer_rate": mean([not r["abstained"] for r in absent]),
        "correct_abstention": mean([r["abstained"] for r in absent]),
        "inappropriate_abstention": mean([r["abstained"] for r in present]),
        "regression_accuracy": mean([r["correct"] for r in regression]),
        "counts": {
            "present": len(present),
            "absent": len(absent),
            "regression": len(regression),
        },
    }


def answer(model, tokenizer, row):
    system = (
        "Return only the short factual answer, without explanation."
        if row["id"].startswith("regression-")
        else SYSTEM
    )
    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": row["prompt"]},
        ],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    begin = time.monotonic()
    text = ""
    last = None
    for response in stream_generate(
        model, tokenizer, prompt, max_tokens=24, sampler=make_sampler(temp=0)
    ):
        text += response.text
        last = response
    elapsed = time.monotonic() - begin
    normalized = text.strip().strip('"').rstrip(".").casefold()
    result = {
        **row,
        "output": text,
        "correct": normalized == row["answer"].casefold(),
        "abstained": normalized == "abstain",
        "seconds": elapsed,
        "generation_tokens": last.generation_tokens if last else 0,
        "generation_tps": last.generation_tps if last else None,
    }
    return result


def evaluate(name, adapter):
    started = time.monotonic()
    output = OUT / f"{name}-result.json"
    if output.exists():
        raise SystemExit("Result already exists; preserve the original run.")
    contract = json.loads((OUT / "contract.json").read_text())
    for path, expected in contract["files_sha256"].items():
        assert hashlib.sha256((OUT / path).read_bytes()).hexdigest() == expected, path
    assert json.loads((OUT / "frontier-result.json").read_text())["valid"]
    model_path = json.loads((OUT / "model-source.json").read_text())["local_path"]
    mx.set_memory_limit(12 * 1024**3)
    mx.set_cache_limit(2 * 1024**3)
    mx.random.seed(contract["seed"])
    model, tokenizer = load(model_path, adapter_path=adapter)
    rows = []
    for split in ["dev", "test", "regression"]:
        rows.extend(
            json.loads(line)
            for line in (OUT / f"{split}.jsonl").read_text().splitlines()
        )
    results = []
    for row in rows:
        if time.monotonic() - started >= 1200:
            raise SystemExit(
                "Evaluation time cap reached; retained partial output is not a completed score."
            )
        result = answer(model, tokenizer, row)
        results.append(result)
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write(
            output,
            {
                "name": name,
                "complete": len(results) == len(rows),
                "count": len(results),
                "elapsed_seconds": time.monotonic() - started,
                "peak_rss_bytes": rss,
                "mlx_peak_memory_bytes": mx.get_peak_memory(),
                "paid_usd": 0,
                "slices": {
                    split: score([r for r in results if r.get("split") == split])
                    for split in ["dev", "test"]
                },
                "regression": score(
                    [r for r in results if r["id"].startswith("regression-")]
                ),
                "rows": results,
            },
        )
        print(
            f"{name} {len(results)}/{len(rows)} {row['id']} correct={result['correct']}",
            flush=True,
        )
        if rss > 16 * 1024**3:
            raise SystemExit(
                "Observed peak process memory exceeded cap; reject this run."
            )
    print(json.dumps(json.loads(output.read_text())["slices"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=["baseline", "ordinary", "perturbation"])
    parser.add_argument("--adapter")
    args = parser.parse_args()
    evaluate(args.name, args.adapter)
