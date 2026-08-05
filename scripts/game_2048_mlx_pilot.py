#!/usr/bin/env python3
"""Run one bounded text-only MLX policy pilot; not a frozen benchmark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Sequence

import game_2048 as game
import game_2048_llm_policy as llm_policy


class MlxCharacterPolicy:
    revision = "mlx-character-policy-pilot/v1"

    def __init__(self, model_path: str, policy_id: str, track: str):
        from mlx_lm import load
        from mlx_lm.sample_utils import make_sampler

        started = time.perf_counter_ns()
        self.model, self.tokenizer = load(model_path)
        self.model_load_time_ms = (time.perf_counter_ns() - started) / 1_000_000
        self.policy_id = policy_id
        llm_policy.validate_track(track)
        self.track = track
        self._sampler = make_sampler(temp=0.0)
        self.raw_outputs: list[str] = []

    def _prompt(self, observation: dict[str, Any]) -> str:
        messages = [
            *llm_policy.messages(observation),
        ]
        try:
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def choose(self, observation: dict[str, Any], legal_actions: Sequence[str]) -> str:
        from mlx_lm import generate

        sampler = self._sampler
        max_tokens = 2
        if self.track == llm_policy.LEGAL_CONSTRAINED_TRACK:
            import mlx.core as mx

            allowed_ids = []
            for character in llm_policy.legal_characters(legal_actions):
                token_ids = self.tokenizer.encode(character, add_special_tokens=False)
                if len(token_ids) != 1:
                    raise ValueError(f"action character is not one token: {character}")
                allowed_ids.append(token_ids[0])
            allowed = mx.array(allowed_ids)

            def legal_sampler(logits):
                selected = mx.argmax(logits[..., allowed], axis=-1)
                return allowed[selected]

            sampler = legal_sampler
            max_tokens = 1
        raw = generate(
            self.model,
            self.tokenizer,
            prompt=self._prompt(observation),
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )
        self.raw_outputs.append(raw)
        try:
            return game.parse_character_action(raw)
        except ValueError:
            return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Local MLX model directory")
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--track", choices=llm_policy.TRACKS, default=llm_policy.STRICT_TRACK)
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--max-moves", type=int, default=128)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_moves <= 0 or args.max_moves > 512:
        raise ValueError("pilot max-moves must be from 1 through 512")
    policy = MlxCharacterPolicy(args.model, args.policy_id, args.track)
    episodes = [
        game.run_episode(
            policy,
            seed,
            max_moves=args.max_moves,
            per_move_milliseconds=60_000,
        )
        for seed in args.seed
    ]
    summary = {
        "schema_version": "game-2048/mlx-character-pilot/v1",
        "status": "development-only-not-frozen-evidence",
        "evaluation_track": args.track,
        "character_observation_revision": game.CHARACTER_OBSERVATION_REVISION,
        "model": {"policy_id": args.policy_id, "path": args.model},
        "model_load_time_ms": policy.model_load_time_ms,
        "max_moves": args.max_moves,
        "episodes": episodes,
        "raw_outputs": policy.raw_outputs,
        "aggregate": {
            "games": len(episodes),
            "mean_score": sum(episode["final_observation"]["score"] for episode in episodes) / len(episodes),
            "mean_maximum_tile": sum(episode["metrics"]["maximum_tile"] for episode in episodes) / len(episodes),
            "invalid_decisions": sum(
                episode["metrics"]["decisions"] - episode["metrics"]["legal_decisions"] for episode in episodes
            ),
            "mean_moves": sum(episode["final_observation"]["move_count"] for episode in episodes) / len(episodes),
        },
    }
    game.write_json_exclusive(args.output, summary)
    print(json.dumps(summary["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
