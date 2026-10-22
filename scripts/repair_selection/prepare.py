"""Original problem-disjoint Python repairs for issue #201's bounded pilot.

Hidden cases are withheld from every coder prompt and TEST outcomes from all
predictor updates/selection. Programs execute only in the qualified Mac runner.
"""

import argparse
import hashlib
import itertools
import json
import os.path
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs/2026-10-22-repair-selection-201-v1"
GROUNDING = ROOT / "runs/2026-10-22-grounding-200-v1"
RUNNER = ROOT / "scripts/humaneval-sandbox/target/debug/humaneval-sandbox"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def balanced(text):
    depth = 0
    for char in text:
        depth += (char == "(") - (char == ")")
        if depth < 0:
            return False
    return depth == 0


def nested_sum(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return sum(nested_sum(v) for v in value.values())
    if isinstance(value, list):
        return sum(nested_sum(v) for v in value)
    return 0


def inverted(mapping):
    result = {}
    for key, value in mapping.items():
        result.setdefault(value, []).append(key)
    return result


def ranges(values):
    result = []
    for value in sorted(set(values)):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def task(identifier, split, spec, buggy, reference, public, hidden):
    def cases(examples):
        return [{"args": args, "expected": reference(*args)} for args in examples]

    return {
        "id": identifier,
        "template": identifier,
        "split": split,
        "spec": spec,
        "buggy_code": "def candidate" + buggy,
        "public": cases(public),
        "hidden": cases(hidden),
    }


TASKS = [
    task(
        "clamp",
        "train",
        "Clamp x to the inclusive interval [lo,hi], with lo<=hi.",
        "(x, lo, hi):\n    return min(lo, max(hi, x))\n",
        lambda x, lo, hi: max(lo, min(hi, x)),
        [[3, 1, 5], [-2, 0, 9], [20, 0, 9]],
        [[0, 0, 0], [-8, -5, -2], [9, 1, 9]],
    ),
    task(
        "positive_count",
        "train",
        "Count strictly positive numbers in xs; zero is not positive.",
        "(xs):\n    return sum(x >= 0 for x in xs)\n",
        lambda xs: sum(x > 0 for x in xs),
        [[[1, 0, -2]], [[]], [[4, 5]]],
        [[[0, 0]], [[-3, -1]], [[0, 2, 0, -1, 7]]],
    ),
    task(
        "stable_unique",
        "train",
        "Return unique integers in first-occurrence order.",
        "(xs):\n    return sorted(set(xs))\n",
        lambda xs: list(dict.fromkeys(xs)),
        [[[2, 1, 2]], [[]], [[3, 3]]],
        [[[7, -1, 7, 2, -1]], [[9, 8, 7]], [[0, 0, 0]]],
    ),
    task(
        "sum_absolute",
        "train",
        "Return the sum of absolute values in xs.",
        "(xs):\n    return sum(xs)\n",
        lambda xs: sum(abs(x) for x in xs),
        [[[-2, 3]], [[]], [[0, -4]]],
        [[[-1, -2, -3]], [[5]], [[2, -2, 0]]],
    ),
    task(
        "alternate_strings",
        "train",
        "Alternate characters from a then b, retaining either remainder.",
        "(a,b):\n    return ''.join(x+y for x,y in zip(a,b))\n",
        lambda a, b: "".join(
            "".join(pair) for pair in itertools.zip_longest(a, b, fillvalue="")
        ),
        [["ab", "12"], ["abc", "x"], ["", "pq"]],
        [["r", ""], ["a", "1234"], ["cat", "doggy"]],
    ),
    task(
        "run_lengths",
        "train",
        "Return consecutive runs as a list of [character,count] lists; empty input returns [].",
        "(s):\n    return [[c,s.count(c)] for c in dict.fromkeys(s)]\n",
        lambda s: [[c, len(list(group))] for c, group in itertools.groupby(s)],
        [["aabb"], [""], ["aba"]],
        [["zzzxzz"], ["q"], ["112211"]],
    ),
    task(
        "second_distinct",
        "train",
        "Return the second largest distinct integer, or None if fewer than two distinct values.",
        "(xs):\n    return sorted(xs)[-2] if len(xs)>1 else None\n",
        lambda xs: sorted(set(xs))[-2] if len(set(xs)) > 1 else None,
        [[[1, 3, 2]], [[4, 4]], [[]]],
        [[[8, 8, 7]], [[0, -2, -1]], [[-5]]],
    ),
    task(
        "balanced_parentheses",
        "train",
        "Return whether parentheses balance, rejecting an unmatched closing prefix; ignore other characters.",
        "(s):\n    return s.count('(')==s.count(')')\n",
        balanced,
        [["(a)"], [")("], ["abc"]],
        [["(()())"], ["())("], ["((x)"]],
    ),
    task(
        "remove_prefix_once",
        "dev",
        "Remove prefix only when it occurs at the beginning, and only once.",
        "(s,prefix):\n    return s.replace(prefix,'')\n",
        lambda s, prefix: s[len(prefix) :] if s.startswith(prefix) else s,
        [["abab", "ab"], ["cat", "x"], ["abc", ""]],
        [["xxabcxx", "xx"], ["ababa", "aba"], ["", "z"]],
    ),
    task(
        "transpose",
        "dev",
        "Transpose a rectangular matrix into lists; the empty matrix returns [].",
        "(matrix):\n    return [[matrix[j][i] for j in range(len(matrix))] for i in range(len(matrix))]\n",
        lambda matrix: [list(row) for row in zip(*matrix)],
        [[[[1, 2], [3, 4]]], [[[1, 2, 3], [4, 5, 6]]], [[]]],
        [[[[1], [2], [3]]], [[[]]], [[[7, 8, 9, 10]]]],
    ),
    task(
        "leap_year",
        "dev",
        "Return whether a positive Gregorian year is a leap year, including century and 400-year rules.",
        "(year):\n    return year % 4 == 0\n",
        lambda year: year % 400 == 0 or (year % 4 == 0 and year % 100 != 0),
        [[2024], [1900], [2000]],
        [[2100], [2400], [2023]],
    ),
    task(
        "decimal_digits",
        "dev",
        "Return decimal digits of abs(n) as integers, with zero represented by [0].",
        "(n):\n    return [int(c) for c in str(n)]\n",
        lambda n: [int(c) for c in str(abs(n))],
        [[123], [-45], [0]],
        [[-1002], [7], [90000]],
    ),
    task(
        "chunks",
        "test",
        "Split xs into consecutive lists of positive size n, including a short final chunk.",
        "(xs,n):\n    return [xs[i:i+n] for i in range(0,len(xs)-n+1,n)]\n",
        lambda xs, n: [xs[i : i + n] for i in range(0, len(xs), n)],
        [[[1, 2, 3, 4], 2], [[1, 2, 3], 2], [[], 3]],
        [[[1], 9], [[1, 2, 3, 4, 5], 3], [[0, 1], 1]],
    ),
    task(
        "rotate_right",
        "test",
        "Rotate xs right by integer k, modulo length; negative k rotates left and [] stays [].",
        "(xs,k):\n    return xs[-k:]+xs[:-k]\n",
        lambda xs, k: (
            xs[-(k % len(xs)) :] + xs[: -(k % len(xs))] if xs and k % len(xs) else xs[:]
        ),
        [[[1, 2, 3], 1], [[1, 2], 0], [[], 7]],
        [[[1, 2, 3], 4], [[1, 2, 3], -4], [[8], 100]],
    ),
    task(
        "nested_numeric_sum",
        "test",
        "Recursively sum ints/floats in lists and dictionary values. Ignore booleans, strings and None.",
        "(value):\n    return sum(value) if isinstance(value,list) else value\n",
        nested_sum,
        [[[1, 2]], [[1, [2, 3]]], [{"a": 2, "b": [3]}]],
        [[{"a": [True, 2, "4"], "b": {"z": 3}}], [None], [[False, -2, 1.5]]],
    ),
    task(
        "invert_groups",
        "test",
        "Group string dictionary keys by their string values, preserving original key order in each list.",
        "(mapping):\n    return {v:k for k,v in mapping.items()}\n",
        inverted,
        [[{"a": "x", "b": "x"}], [{}], [{"c": "y"}]],
        [
            [{"c": "x", "a": "z", "b": "x"}],
            [{"a": "", "b": ""}],
            [{"x": "a", "y": "b"}],
        ],
    ),
    task(
        "common_prefix",
        "test",
        "Return the longest common prefix of every string; an empty list returns ''.",
        "(words):\n    return words[0] if words else ''\n",
        os.path.commonprefix,
        [[["flower", "flow", "flight"]], [[]], [["cat", "dog"]]],
        [[["same"]], [["prefix", "pre", "prevent"]], [["abc", "", "abd"]]],
    ),
    task(
        "integer_ranges",
        "test",
        "Sort and deduplicate integers, compressing consecutive values into inclusive [start,end] lists.",
        "(xs):\n    return [[x,x] for x in sorted(xs)]\n",
        ranges,
        [[[3, 1, 2, 5]], [[]], [[7]]],
        [[[2, 2, 1, 4, 5, 5]], [[-3, -2, 0]], [[9, 8, 7, 6]]],
    ),
]


def prepare(runner=RUNNER):
    if (OUT / "contract.json").exists():
        raise SystemExit("Frozen repair run already exists.")
    OUT.mkdir(parents=True)
    data = "".join(json.dumps(row) + "\n" for row in TASKS)
    (OUT / "tasks.jsonl").write_text(data)
    model = json.loads((GROUNDING / "model-source.json").read_text())
    contract = {
        "issue": 201,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "seed": 20120261022,
        "data_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "source": "Original operator-authorized engineering repair fixtures; one distinct problem/template per task.",
        "counts": {
            split: sum(r["split"] == split for r in TASKS)
            for split in ["train", "dev", "test"]
        },
        "model": model,
        "runtime": json.loads((GROUNDING / "contract.json").read_text())["runtime"],
        "coder": {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 256,
            "enable_thinking": False,
            "candidates_per_round": 4,
            "rounds": 2,
            "seed_formula": "master%2**32 + task_index*100 + round*10 + candidate",
        },
        "predictor": {
            "kind": "ridge linear outcome predictor, clipped to[0,1]",
            "ridge": 1.0,
            "initial": "TRAIN round1 outcomes only",
            "update": "one fit on TRAIN rounds1+2 only",
            "retain_update": "DEV round2 selected success does not fall and Brier score strictly improves",
        },
        "ranking": {
            "random": "seeded index",
            "static": "valid restricted Python, then fewer pass/raise nodes, then shorter AST, then index",
            "execution": "public all-pass first, then index",
            "learned": "predicted hidden all-pass probability, then index",
        },
        "caps": {
            "total_model_executor_seconds": 3600,
            "peak_process_gib": 16,
            "paid_api_cloud_usd": 0,
            "preparation_hours": 4,
            "predictor_fits": 2,
            "runner_timeout_seconds": 2,
            "runner_memory_mb": 256,
        },
        "acceptance": {
            "gain_over_strongest_baseline_pp": 5,
            "maximum_regression_pp": 2,
            "uncertainty": "paired task bootstrap10000 seed201; inconclusive if gain interval includes zero",
            "adaptation_claim": "adapted must beat frozen parent on held-out second round",
        },
        "executor": {
            "path": str(runner.resolve()),
            "sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
            "source_sha": "935b1b3ff4074c14743019a4dc463391b8ec35d2",
            "qualified": "PR203 Mac negative controls and normal exits",
        },
        "bfcl": "Reuse exact unchanged coder's measured calibrated grounding200 BFCL baseline; no coder update in this experiment.",
        "limitations": "18-task pilot with only6 TEST problems; cannot establish a small general population improvement. No JEPA/RSI reproduction claim.",
    }
    write(OUT / "contract.json", contract)
    print(
        json.dumps(
            {"counts": contract["counts"], "tasks_sha256": contract["data_sha256"]}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", type=Path, default=RUNNER)
    prepare(parser.parse_args().runner)
