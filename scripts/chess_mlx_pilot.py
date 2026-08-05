#!/usr/bin/env python3
"""Run one bounded strict chess-tactics pilot with a local MLX model."""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path
from typing import Any, Sequence

import chess_benchmark as benchmark
import chess_llm_policy as llm_policy

SCHEMA_VERSION = "chess/mlx-puzzle-pilot/v1"


class MlxChessPolicy:
    revision = "mlx-chess-policy/v1"

    def __init__(self, model_path: str, model_ref: str, policy_id: str):
        from mlx_lm import load
        from mlx_lm.sample_utils import make_sampler

        started = time.perf_counter_ns()
        self.model, self.tokenizer = load(model_path)
        self.model_load_time_ms = (time.perf_counter_ns() - started) / 1_000_000
        self.model_ref = model_ref
        self.policy_id = policy_id
        self._sampler = make_sampler(temp=0.0)

    def _prompt(self, state: dict[str, Any]) -> str:
        messages = llm_policy.messages(state)
        try:
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        del legal_moves
        from mlx_lm import generate

        return generate(
            self.model,
            self.tokenizer,
            prompt=self._prompt(state),
            max_tokens=8,
            sampler=self._sampler,
            verbose=False,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Local MLX model directory")
    parser.add_argument("--model-ref", required=True, help="Portable model identity recorded in evidence")
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite = benchmark.load_puzzle_suite(args.suite)
    policy = MlxChessPolicy(args.model, args.model_ref, args.policy_id)
    result = benchmark.evaluate_puzzles(policy, suite)
    result.update(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "development-only-not-frozen-evidence",
            "model": {"policy_id": args.policy_id, "model_ref": args.model_ref},
            "runtime": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "mlx_lm": "0.31.3",
                "model_load_time_ms": policy.model_load_time_ms,
            },
        }
    )
    result["trace_hash"] = benchmark.sha256_json({key: value for key, value in result.items() if key != "trace_hash"})
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
