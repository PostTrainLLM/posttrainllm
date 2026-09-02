#!/usr/bin/env python3
"""Run one frozen ReST requalification arm through the BFCL stateful checker.

The Python implementation remains the readable correctness oracle. Each arm is
run in a fresh process on the same host/runtime so peak RSS and decode timing do
not leak across models. The orchestrator alternates arm order by suite.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import resource
import sys
import time
from pathlib import Path
from typing import Any

from bfcl_paths import resolve_bfcl_root
from rest_protocol import SYSTEM_PROMPT


MAX_STEPS = 12
SIDE_EFFECT_FUNCTIONS = {
    "cancel_booking",
    "close_ticket",
    "comment",
    "cp",
    "create_ticket",
    "delete_message",
    "echo",
    "mkdir",
    "mv",
    "post_tweet",
    "purchase_insurance",
    "register_credit_card",
    "resolve_ticket",
    "retweet",
    "rm",
    "send_message",
    "set_budget_limit",
    "touch",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--exclude-id", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def function_name(call: str) -> str:
    return call.split("(", 1)[0].rsplit(".", 1)[-1].strip()


def expected_names(gold_turn: list[str]) -> set[str]:
    return {function_name(call) for call in gold_turn}


def schema_failure_count(
    raw: str, calls: list[tuple[str, Any]], catalog: set[str]
) -> int:
    markers = raw.count("<tool_call>")
    failures = max(0, markers - len(calls))
    for name, arguments in calls:
        if (
            not isinstance(name, str)
            or name not in catalog
            or not isinstance(arguments, dict)
        ):
            failures += 1
    return failures


def main() -> int:
    args = parse_args()
    bfcl_root = resolve_bfcl_root()
    sys.path.insert(0, str(bfcl_root))

    from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
        multi_turn_checker,
    )
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
        execute_multi_turn_func_call,
    )
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    original_argv = sys.argv
    sys.argv = ["bfcl_ast_eval"]
    import bfcl_ast_eval as parser_helpers

    sys.argv = original_argv

    func_doc = bfcl_root / "bfcl_eval/data/multi_turn_func_doc"
    examples = [
        json.loads(line) for line in args.data.read_text().splitlines() if line.strip()
    ]
    random.Random(args.seed).shuffle(examples)
    excluded_ids = set(args.exclude_id)
    examples = [item for item in examples if item["id"] not in excluded_ids]
    golds = {
        value["id"]: value
        for value in (
            json.loads(line)
            for line in args.gold.read_text().splitlines()
            if line.strip()
        )
    }

    started = time.perf_counter()
    model, tokenizer = load(str(args.model))
    sampler = make_sampler(temp=0.0)
    load_seconds = time.perf_counter() - started
    traces: list[dict[str, Any]] = []
    passed = 0
    total_generated_tokens = 0
    total_decode_seconds = 0.0
    schema_failures = 0
    unexpected_side_effects = 0

    def load_catalog(example: dict[str, Any]) -> list[dict[str, Any]]:
        functions = []
        excluded = set(example.get("excluded_function", []))
        for class_name in example["involved_classes"]:
            filename = CLASS_FILE_PATH_MAPPING[class_name].split(".")[-1] + ".json"
            for line in (func_doc / filename).read_text().splitlines():
                if line.strip():
                    function = json.loads(line)
                    if function.get("name") not in excluded:
                        functions.append(function)
        return functions

    for example in examples:
        gold = golds[example["id"]]
        catalog = load_catalog(example)
        catalog_names = {item["name"] for item in catalog}
        tools = [
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "parameters": item.get("parameters", {}),
                },
            }
            for item in catalog
        ]
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        decoded: list[list[list[str]]] = []
        example_schema_failures = 0
        example_side_effects = 0
        example_tokens = 0
        example_decode_seconds = 0.0

        for turn_index, turn in enumerate(example["question"]):
            user_content = " ".join(
                item["content"] for item in turn if item.get("role") == "user"
            )
            messages.append({"role": "user", "content": user_content})
            turn_steps: list[list[str]] = []
            expected = expected_names(gold["ground_truth"][turn_index])
            for _ in range(MAX_STEPS):
                prompt = tokenizer.apply_chat_template(
                    messages, tools=tools, add_generation_prompt=True, tokenize=False
                )
                decode_started = time.perf_counter()
                raw = generate(
                    model,
                    tokenizer,
                    prompt=prompt,
                    sampler=sampler,
                    max_tokens=512,
                    verbose=False,
                )
                decode_seconds = time.perf_counter() - decode_started
                token_count = len(tokenizer.encode(raw))
                example_tokens += token_count
                example_decode_seconds += decode_seconds
                calls = parser_helpers.extract_calls(raw)
                example_schema_failures += schema_failure_count(
                    raw, calls, catalog_names
                )
                messages.append({"role": "assistant", "content": raw})
                if not calls:
                    break
                call_strings = [
                    f"{name}("
                    + ", ".join(f"{key}={value!r}" for key, value in arguments.items())
                    + ")"
                    for name, arguments in calls
                    if isinstance(name, str) and isinstance(arguments, dict)
                ]
                turn_steps.append(call_strings)
                for name, _ in calls:
                    if name in SIDE_EFFECT_FUNCTIONS and name not in expected:
                        example_side_effects += 1
                try:
                    results, _ = execute_multi_turn_func_call(
                        call_strings,
                        example["initial_config"],
                        example["involved_classes"],
                        args.model_id,
                        example["id"],
                        is_evaL_run=False,
                    )
                except Exception as exc:
                    results = [f"<execution error: {exc}>"]
                    example_schema_failures += 1
                if any(
                    str(result).startswith("Error during execution:")
                    for result in results
                ):
                    example_schema_failures += sum(
                        str(result).startswith("Error during execution:")
                        for result in results
                    )
                messages.append({"role": "tool", "content": json.dumps(results)})
            decoded.append(turn_steps if turn_steps else [[]])

        checker = multi_turn_checker(
            decoded,
            gold["ground_truth"],
            example,
            "multi_turn_base",
            args.model_id,
        )
        valid = (
            bool(checker.get("valid", False))
            if isinstance(checker, dict)
            else bool(checker)
        )
        passed += int(valid)
        total_generated_tokens += example_tokens
        total_decode_seconds += example_decode_seconds
        schema_failures += example_schema_failures
        unexpected_side_effects += example_side_effects
        traces.append(
            {
                "id": example["id"],
                "valid": valid,
                "generated_tokens": example_tokens,
                "decode_seconds": example_decode_seconds,
                "schema_failures": example_schema_failures,
                "unexpected_side_effects": example_side_effects,
                "decoded": decoded,
                "checker": checker,
            }
        )
        print(
            f"{args.model_id} {args.suite}: {len(traces)}/{len(examples)} "
            f"pass={passed / len(traces):.1%}",
            flush=True,
        )

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        peak_rss_bytes = int(peak_rss)
    else:
        peak_rss_bytes = int(peak_rss * 1024)
    result = {
        "schema_version": "posttrainllm.rest-arm-eval.v1",
        "model_id": args.model_id,
        "model_path": str(args.model.resolve()),
        "suite": args.suite,
        "data": str(args.data),
        "gold": str(args.gold),
        "seed": args.seed,
        "excluded_ids": sorted(excluded_ids),
        "count": len(examples),
        "passed": passed,
        "accuracy": passed / max(len(examples), 1),
        "schema_failures": schema_failures,
        "unexpected_side_effects": unexpected_side_effects,
        "load_seconds": load_seconds,
        "decode_seconds": total_decode_seconds,
        "generated_tokens": total_generated_tokens,
        "decode_tokens_per_second": total_generated_tokens
        / max(total_decode_seconds, 1e-9),
        "peak_rss_bytes": peak_rss_bytes,
        "wall_seconds": time.perf_counter() - started,
        "python": sys.version,
        "bfcl_root": str(bfcl_root),
        "traces": traces,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{json.dumps(result, indent=2)}\n", encoding="utf-8")
    del model
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
