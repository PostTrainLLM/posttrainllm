#!/usr/bin/env python3
"""Run bounded paired full chess games between two local MLX language models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess_benchmark as benchmark
from chess_mlx_pilot import MlxChessPolicy

SCHEMA_VERSION = "chess/mlx-paired-match/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openings", type=Path, required=True)
    parser.add_argument("--model-a", required=True)
    parser.add_argument("--model-a-ref", required=True)
    parser.add_argument("--policy-a", required=True)
    parser.add_argument("--model-b", required=True)
    parser.add_argument("--model-b-ref", required=True)
    parser.add_argument("--policy-b", required=True)
    parser.add_argument("--maximum-plies", type=int, default=160)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    openings = json.loads(args.openings.read_text(encoding="utf-8"))
    if openings.get("schema_version") != "chess/openings/v1" or not openings.get("openings"):
        raise ValueError("unsupported or empty opening set")
    policy_a = MlxChessPolicy(args.model_a, args.model_a_ref, args.policy_a)
    policy_b = MlxChessPolicy(args.model_b, args.model_b_ref, args.policy_b)
    games = []
    for opening in openings["openings"]:
        games.append({"opening_id": opening["id"], "color_assignment": "a-white", **benchmark.run_game(policy_a, policy_b, starting_fen=opening["fen"], maximum_plies=args.maximum_plies)})
        games.append({"opening_id": opening["id"], "color_assignment": "b-white", **benchmark.run_game(policy_b, policy_a, starting_fen=opening["fen"], maximum_plies=args.maximum_plies)})
    wins = {args.policy_a: 0, args.policy_b: 0}
    draws = 0
    invalid_forfeits = 0
    for game in games:
        winner = game[game["outcome"]["winner"]]["policy_id"] if game["outcome"]["winner"] else None
        if winner is None:
            draws += 1
        else:
            wins[winner] += 1
        invalid_forfeits += game["outcome"]["termination"] == "invalid-decision-forfeit"
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "development-only-not-elo-evidence",
        "opening_set_id": openings["opening_set_id"],
        "models": [
            {"policy_id": args.policy_a, "model_ref": args.model_a_ref, "model_load_time_ms": policy_a.model_load_time_ms},
            {"policy_id": args.policy_b, "model_ref": args.model_b_ref, "model_load_time_ms": policy_b.model_load_time_ms},
        ],
        "aggregate": {"games": len(games), "wins": wins, "draws": draws, "invalid_forfeits": invalid_forfeits},
        "games": games,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
