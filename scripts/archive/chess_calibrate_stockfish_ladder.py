#!/usr/bin/env python3
"""Calibrate weak Stockfish/random rungs against the Stockfish UCI-Elo anchor."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
from pathlib import Path

import chess

import chess_benchmark as benchmark
import chess_elo
import chess_strength_ladder as ladder

SCHEMA_VERSION = "chess/stockfish-ladder-calibration/v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--openings", type=Path, required=True)
    parser.add_argument("--stockfish")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def score_for_policy(game: dict, policy_id: str) -> float:
    winner = game[game["outcome"]["winner"]]["policy_id"] if game["outcome"]["winner"] else None
    if winner is None:
        return 0.5
    return 1.0 if winner == policy_id else 0.0


def run_calibration(config: dict, openings: dict, binary: str) -> dict:
    anchor_rows = [row for row in config["rungs"] if row["kind"] == "uci-elo" and row["calibrated_rating"]]
    if len(anchor_rows) != 1:
        raise ValueError("calibration requires exactly one pre-calibrated UCI-Elo anchor")
    anchor = anchor_rows[0]
    games = []
    matches = []
    engine_identities = {}
    for first_index, first_rung in enumerate(config["rungs"]):
        for second_index in range(first_index + 1, len(config["rungs"])):
            second_rung = config["rungs"][second_index]
            for opening_index, opening in enumerate(openings["openings"]):
                for first_color in ("white", "black"):
                    color_offset = int(first_color == "black")
                    first = ladder.StockfishRungPolicy(
                        {**first_rung, "seed": first_rung["seed"] + opening_index * 20 + color_offset},
                        config["engine"],
                        binary,
                    )
                    second = ladder.StockfishRungPolicy(
                        {**second_rung, "seed": second_rung["seed"] + opening_index * 20 + color_offset + 10},
                        config["engine"],
                        binary,
                    )
                    try:
                        for policy in (first, second):
                            if policy.engine_identity is not None:
                                engine_identities[policy.policy_id] = policy.engine_identity
                        white, black = (first, second) if first_color == "white" else (second, first)
                        game = benchmark.run_game(
                            white,
                            black,
                            starting_fen=opening["fen"],
                            maximum_plies=config["maximum_plies"],
                        )
                    finally:
                        first.close()
                        second.close()
                    first_score = score_for_policy(game, first.policy_id)
                    matches.append((first.policy_id, second.policy_id, first_score))
                    games.append(
                        {
                            "game_id": f"{first.policy_id}:{second.policy_id}:{opening['id']}:{first_color}",
                            "first_policy_id": first.policy_id,
                            "second_policy_id": second.policy_id,
                            "first_color": first_color,
                            "opening_id": opening["id"],
                            "first_score": first_score,
                            **game,
                        }
                    )
    policy_ids = [row["rung_id"] for row in config["rungs"]]
    ratings = chess_elo.fit_connected_pool(
        policy_ids,
        matches,
        anchor_id=anchor["rung_id"],
        anchor_rating=anchor["calibrated_rating"],
    )
    natural = sum(game["outcome"]["termination"] != "move-cap-draw" for game in games)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "internal-stockfish-ladder-calibration-not-human-elo",
        "config_hash": benchmark.sha256_json(config),
        "opening_set_id": openings["opening_set_id"],
        "anchor": {"rung_id": anchor["rung_id"], "rating": anchor["calibrated_rating"]},
        "method": {
            "name": "regularized-bradley-terry",
            "prior_standard_deviation": 800.0,
            "color_term": False,
            "disclaimer": "Internal Stockfish-ladder Elo; not FIDE, human, Lichess, or Chess.com Elo.",
        },
        "engine": {"binary": binary, "identities": engine_identities},
        "runtime": {"python": platform.python_version(), "python_chess": chess.__version__},
        "aggregate": {
            "games": len(games),
            "natural_completion_rate": natural / len(games),
            "ratings": [
                {"rung_id": policy_id, "rating": ratings[policy_id]}
                for policy_id in sorted(policy_ids, key=lambda item: ratings[item])
            ],
        },
        "games": games,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    return result


def main() -> int:
    args = parse_args()
    config = ladder.load_config(args.config)
    openings = ladder.load_openings(args.openings)
    requested = args.stockfish or config["engine"]["binary"]
    binary = shutil.which(requested) or requested
    if not Path(binary).is_file():
        raise ValueError(f"Stockfish binary not found: {requested}")
    result = run_calibration(config, openings, binary)
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
