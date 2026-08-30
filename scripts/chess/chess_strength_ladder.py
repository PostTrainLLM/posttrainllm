#!/usr/bin/env python3
"""Run paired Character Chess games against a reproducible weak-Stockfish ladder."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import shutil
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Sequence

import chess
import chess.engine

import chess_benchmark as benchmark
import chess_elo

CONFIG_SCHEMA = "chess/strength-ladder/v1"
RESULT_SCHEMA = "chess/strength-ladder-result/v1"
RUNG_KINDS = {"random-legal", "blunder-mix", "uci-elo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--openings", type=Path)
    parser.add_argument("--stockfish")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument(
        "--candidate-backend",
        choices=("first-legal", "random-legal", "mlx", "python-checkpoint"),
        required=True,
    )
    parser.add_argument("--policy-id", required=True)
    parser.add_argument("--candidate-seed", type=int, default=20260805)
    parser.add_argument("--model")
    parser.add_argument("--model-ref")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--candidate-device", default="auto")
    parser.add_argument("--candidate-batch-size", type=int, default=8)
    parser.add_argument(
        "--serving-policy",
        choices=("always-score", "always-score-finishing-guards"),
        default="always-score",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "ladder_id",
        "status",
        "engine",
        "openings_ref",
        "maximum_plies",
        "bootstrap",
        "qualification",
        "rungs",
    }
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA or set(config) != required:
        raise ValueError("unsupported or incomplete chess strength ladder config")
    engine = config["engine"]
    if set(engine) != {"binary", "required_name_prefix", "threads", "hash_mb"}:
        raise ValueError("engine config fields are incomplete")
    if engine["threads"] != 1 or not isinstance(engine["hash_mb"], int) or engine["hash_mb"] < 1:
        raise ValueError("ladder requires one Stockfish thread and positive hash size")
    if not isinstance(config["maximum_plies"], int) or not 1 <= config["maximum_plies"] <= 512:
        raise ValueError("maximum_plies must be from 1 through 512")
    bootstrap = config["bootstrap"]
    if set(bootstrap) != {"seed", "samples", "confidence"}:
        raise ValueError("bootstrap config fields are incomplete")
    if not isinstance(bootstrap["samples"], int) or bootstrap["samples"] < 100:
        raise ValueError("bootstrap requires at least 100 samples")
    if not isinstance(bootstrap["confidence"], (int, float)) or not 0 < bootstrap["confidence"] < 1:
        raise ValueError("bootstrap confidence must be between zero and one")
    qualification = config["qualification"]
    required_qualification = {
        "minimum_completed_games",
        "minimum_games_per_rung",
        "minimum_calibrated_rungs",
        "maximum_color_imbalance",
        "maximum_invalid_forfeit_rate",
    }
    if set(qualification) != required_qualification:
        raise ValueError("qualification config fields are incomplete")
    if any(not isinstance(qualification[key], int) or qualification[key] < 0 for key in required_qualification - {"maximum_invalid_forfeit_rate"}):
        raise ValueError("qualification count gates must be non-negative integers")
    if not isinstance(qualification["maximum_invalid_forfeit_rate"], (int, float)) or not 0 <= qualification["maximum_invalid_forfeit_rate"] <= 1:
        raise ValueError("invalid-forfeit gate must be a probability")
    if not isinstance(config["rungs"], list) or not config["rungs"]:
        raise ValueError("ladder must contain rungs")
    ids: list[str] = []
    rung_fields = {
        "rung_id",
        "kind",
        "random_probability",
        "seed",
        "skill_level",
        "nodes",
        "uci_elo",
        "calibrated_rating",
        "rating_state",
    }
    for rung in config["rungs"]:
        if not isinstance(rung, dict) or set(rung) != rung_fields or rung["kind"] not in RUNG_KINDS:
            raise ValueError("ladder rung fields are incomplete")
        probability = rung["random_probability"]
        if not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
            raise ValueError("rung random_probability must be from zero through one")
        if rung["kind"] == "random-legal" and probability != 1:
            raise ValueError("random-legal rung must have probability one")
        if rung["kind"] == "blunder-mix" and (
            not isinstance(rung["nodes"], int) or rung["nodes"] < 1 or not isinstance(rung["skill_level"], int)
        ):
            raise ValueError("blunder-mix rung requires nodes and skill level")
        if rung["kind"] == "uci-elo" and (not isinstance(rung["uci_elo"], int) or rung["uci_elo"] < 100):
            raise ValueError("uci-elo rung requires uci_elo")
        rating = rung["calibrated_rating"]
        if rating is not None and (not isinstance(rating, (int, float)) or isinstance(rating, bool)):
            raise ValueError("calibrated rating must be numeric or null")
        ids.append(rung["rung_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("ladder rung ids must be unique")
    return config


def load_openings(path: Path) -> dict[str, Any]:
    openings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(openings, dict) or openings.get("schema_version") != "chess/openings/v1":
        raise ValueError("unsupported chess opening set")
    rows = openings.get("openings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("opening set must contain openings")
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "fen"}:
            raise ValueError("opening fields are incomplete")
        if benchmark.normalized_fen(row["fen"]) != row["fen"]:
            raise ValueError("opening FEN is not canonical")
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("opening ids must be unique")
    return openings


def apply_calibration(config: dict[str, Any], calibration: dict[str, Any]) -> dict[str, Any]:
    if calibration.get("schema_version") != "chess/stockfish-ladder-calibration/v1":
        raise ValueError("unsupported Stockfish ladder calibration")
    if calibration.get("config_hash") != benchmark.sha256_json(config):
        raise ValueError("calibration does not match the ladder config")
    rows = calibration.get("aggregate", {}).get("ratings")
    if not isinstance(rows, list):
        raise ValueError("calibration ratings are missing")
    ratings = {row.get("rung_id"): row.get("rating") for row in rows if isinstance(row, dict)}
    if set(ratings) != {row["rung_id"] for row in config["rungs"]}:
        raise ValueError("calibration does not cover every ladder rung")
    calibrated = json.loads(json.dumps(config))
    for rung in calibrated["rungs"]:
        rating = ratings[rung["rung_id"]]
        if not isinstance(rating, (int, float)) or isinstance(rating, bool):
            raise ValueError("calibration rating is not numeric")
        rung["calibrated_rating"] = rating
        rung["rating_state"] = "internally-calibrated-to-stockfish-uci-1320"
    return calibrated


class FirstLegalPolicy:
    revision = "first-legal-smoke/v1"

    def __init__(self, policy_id: str):
        self.policy_id = policy_id

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        del state
        return legal_moves[0]


def stockfish_options(rung: dict[str, Any], engine_config: dict[str, Any]) -> dict[str, Any]:
    """Return only options that python-chess allows clients to configure."""
    options: dict[str, Any] = {
        "Threads": engine_config["threads"],
        "Hash": engine_config["hash_mb"],
    }
    if rung["kind"] == "uci-elo":
        options.update({"UCI_LimitStrength": True, "UCI_Elo": rung["uci_elo"]})
    else:
        options.update({"UCI_LimitStrength": False, "Skill Level": rung["skill_level"]})
    return options


class StockfishRungPolicy:
    revision = "stockfish-rung-policy/v1"

    def __init__(self, rung: dict[str, Any], engine_config: dict[str, Any], binary: str):
        self.rung = dict(rung)
        self.policy_id = rung["rung_id"]
        self._rng = random.Random(rung["seed"])
        self._engine: chess.engine.SimpleEngine | None = None
        self.engine_identity: dict[str, Any] | None = None
        if rung["kind"] != "random-legal":
            self._engine = chess.engine.SimpleEngine.popen_uci(binary)
            name = str(self._engine.id.get("name", ""))
            if not name.startswith(engine_config["required_name_prefix"]):
                self.close()
                raise ValueError(f"Stockfish identity mismatch: {name!r}")
            self._engine.configure(stockfish_options(rung, engine_config))
            self.engine_identity = {"name": name, "author": self._engine.id.get("author")}

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        if not legal_moves:
            raise ValueError("opponent received no legal moves")
        if self._rng.random() < self.rung["random_probability"]:
            return self._rng.choice(list(legal_moves))
        if self._engine is None:
            raise ValueError("Stockfish engine is unavailable for non-random choice")
        board = chess.Board(state["fen"])
        limit = (
            chess.engine.Limit(nodes=self.rung["nodes"])
            if self.rung["kind"] == "blunder-mix"
            else chess.engine.Limit(time=0.01)
        )
        result = self._engine.play(board, limit)
        if result.move is None:
            raise ValueError("Stockfish returned no move")
        return result.move.uci()

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            finally:
                self._engine = None


def _candidate_outcome(game: dict[str, Any], candidate_id: str) -> float:
    winner = game[game["outcome"]["winner"]]["policy_id"] if game["outcome"]["winner"] else None
    if winner is None:
        return 0.5
    return 1.0 if winner == candidate_id else 0.0


def bootstrap_interval(values: Sequence[float], *, samples: int, confidence: float, seed: int) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    estimates = sorted(
        statistics.fmean(rng.choice(values) for _ in values)
        for _ in range(samples)
    )
    tail = (1 - confidence) / 2
    low = estimates[max(0, min(samples - 1, int(math.floor(tail * samples))))]
    high = estimates[max(0, min(samples - 1, int(math.ceil((1 - tail) * samples)) - 1))]
    return [low, high]


def bootstrap_paired_ladder_rating(
    games: list[dict[str, Any]],
    candidate_id: str,
    rung_ratings: dict[str, float | None],
    *,
    samples: int,
    confidence: float,
    seed: int,
) -> list[float] | None:
    """Resample paired-color opening blocks while preserving every ladder rung."""
    blocks: dict[str, dict[str, list[tuple[float, float]]]] = {}
    for game in games:
        opponent_rating = rung_ratings[game["rung_id"]]
        if opponent_rating is None:
            continue
        blocks.setdefault(game["rung_id"], {}).setdefault(game["opening_id"], []).append(
            (opponent_rating, _candidate_outcome(game, candidate_id))
        )
    if not blocks:
        return None
    if any(len(rows) != 2 for rung in blocks.values() for rows in rung.values()):
        raise ValueError("rating bootstrap requires complete paired-color opening blocks")
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        observations = []
        for rung in blocks.values():
            opening_blocks = list(rung.values())
            for _ in opening_blocks:
                observations.extend(rng.choice(opening_blocks))
        estimate, _ = chess_elo.fit_single_rating(observations)
        estimates.append(estimate)
    estimates.sort()
    tail = (1 - confidence) / 2
    low = estimates[max(0, min(samples - 1, int(math.floor(tail * samples))))]
    high = estimates[max(0, min(samples - 1, int(math.ceil((1 - tail) * samples)) - 1))]
    return [low, high]


def summarize_games(games: list[dict[str, Any]], candidate_id: str, config: dict[str, Any]) -> dict[str, Any]:
    outcomes = [_candidate_outcome(game, candidate_id) for game in games]
    wins = sum(value == 1 for value in outcomes)
    draws = sum(value == 0.5 for value in outcomes)
    losses = sum(value == 0 for value in outcomes)
    candidate_decisions = [
        decision
        for game in games
        for decision in game["decisions"]
        if decision["policy_id"] == candidate_id
    ]
    invalid = sum(game["outcome"]["termination"] == "invalid-decision-forfeit" for game in games)
    natural = sum(
        game["outcome"]["termination"] not in {"invalid-decision-forfeit", "move-cap-draw"}
        for game in games
    )
    white_games = sum(game["candidate_color"] == "white" for game in games)
    black_games = len(games) - white_games
    by_rung: dict[str, Any] = {}
    for rung in config["rungs"]:
        rows = [game for game in games if game["rung_id"] == rung["rung_id"]]
        rung_outcomes = [_candidate_outcome(game, candidate_id) for game in rows]
        by_rung[rung["rung_id"]] = {
            "games": len(rows),
            "score": statistics.fmean(rung_outcomes) if rung_outcomes else None,
            "score_interval": bootstrap_interval(
                rung_outcomes,
                samples=config["bootstrap"]["samples"],
                confidence=config["bootstrap"]["confidence"],
                seed=config["bootstrap"]["seed"] + len(by_rung),
            ),
            "calibrated_rating": rung["calibrated_rating"],
            "rating_state": rung["rating_state"],
        }
    q = config["qualification"]
    calibrated = sum(rung["calibrated_rating"] is not None for rung in config["rungs"])
    failures = []
    if len(games) < q["minimum_completed_games"]:
        failures.append("minimum-completed-games")
    if any(row["games"] < q["minimum_games_per_rung"] for row in by_rung.values()):
        failures.append("minimum-games-per-rung")
    if calibrated < q["minimum_calibrated_rungs"]:
        failures.append("minimum-calibrated-rungs")
    if abs(white_games - black_games) > q["maximum_color_imbalance"]:
        failures.append("color-balance")
    if invalid / len(games) > q["maximum_invalid_forfeit_rate"]:
        failures.append("invalid-forfeit-rate")
    rung_ratings = {row["rung_id"]: row["calibrated_rating"] for row in config["rungs"]}
    rating_observations = [
        (rung_ratings[game["rung_id"]], _candidate_outcome(game, candidate_id))
        for game in games
        if rung_ratings[game["rung_id"]] is not None
    ]
    rating_estimate = None
    rating_interval = None
    rating_fit_state = "missing-calibrated-opponents"
    if rating_observations:
        rating_estimate, rating_fit_state = chess_elo.fit_single_rating(rating_observations)
        rating_interval = bootstrap_paired_ladder_rating(
            games,
            candidate_id,
            rung_ratings,
            samples=config["bootstrap"]["samples"],
            confidence=config["bootstrap"]["confidence"],
            seed=config["bootstrap"]["seed"] + 991,
        )
    calibrated_values = sorted(value for value in rung_ratings.values() if value is not None)
    range_state = "unavailable"
    display = None
    status = "unrated"
    if rating_estimate is not None and calibrated_values:
        floor, ceiling = calibrated_values[0], calibrated_values[-1]
        tolerance = 1e-6
        if rating_estimate < floor - tolerance:
            range_state = "below-calibrated-floor"
            display = f"<{round(floor):d}"
        elif rating_estimate > ceiling + tolerance:
            range_state = "above-calibrated-ceiling"
            display = f">{round(ceiling):d}"
        else:
            range_state = "on-calibrated-ladder"
            display = f"{round(rating_estimate):d}"
        if not failures and rating_fit_state == "finite":
            status = "qualified-internal-rating" if range_state == "on-calibrated-ladder" else range_state
    guard_rows = [
        row["policy_metadata"]
        for row in candidate_decisions
        if isinstance(row.get("policy_metadata"), dict)
        and row["policy_metadata"].get("serving_policy") == "always-score-finishing-guards/v1"
    ]
    guard_counts: Counter[str] = Counter(
        event["guard"]
        for row in guard_rows
        for event in row.get("events", [])
        if isinstance(event, dict) and isinstance(event.get("guard"), str)
    )
    return {
        "games": len(games),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score": statistics.fmean(outcomes),
        "score_interval": bootstrap_interval(
            outcomes,
            samples=config["bootstrap"]["samples"],
            confidence=config["bootstrap"]["confidence"],
            seed=config["bootstrap"]["seed"],
        ),
        "natural_completion_rate": natural / len(games),
        "invalid_decision_forfeits": invalid,
        "invalid_forfeit_rate": invalid / len(games),
        "candidate_raw_legal_rate": (
            sum(row["legal"] for row in candidate_decisions) / len(candidate_decisions)
            if candidate_decisions
            else None
        ),
        "serving_policy": {
            "guarded_decisions": len(guard_rows),
            "guard_fire_rate": (
                sum(bool(row.get("guard_fired")) for row in guard_rows) / len(guard_rows)
                if guard_rows
                else None
            ),
            "intervention_rate": (
                sum(bool(row.get("intervened")) for row in guard_rows) / len(guard_rows)
                if guard_rows
                else None
            ),
            "guard_counts": dict(sorted(guard_counts.items())),
        },
        "colors": {"white": white_games, "black": black_games},
        "rungs": by_rung,
        "rating": {
            "label": "Internal Stockfish-ladder Elo",
            "estimate": rating_estimate,
            "display": display,
            "interval": rating_interval,
            "fit_state": rating_fit_state,
            "range_state": range_state,
            "calibrated_range": calibrated_values and [calibrated_values[0], calibrated_values[-1]],
            "diagnostic_extrapolation": rating_estimate if range_state != "on-calibrated-ladder" else None,
            "sample_size": len(rating_observations),
            "status": status,
            "qualification_failures": failures,
            "disclaimer": "Not FIDE, human, engine, Lichess, or Chess.com Elo.",
        },
    }


def build_candidate(args: argparse.Namespace):
    def finalize(policy, metadata):
        if args.serving_policy == "always-score-finishing-guards":
            if not hasattr(policy, "last_scores"):
                raise ValueError("finishing guards require an always-score candidate backend")
            from chess_finishing_guards import FinishingGuardPolicy

            policy = FinishingGuardPolicy(policy)
            metadata = {
                **metadata,
                "base_policy_revision": policy.base_policy.revision,
                "serving_policy": policy.revision,
                "serving_assistance": "engine-free-one-ply-finishing-guards",
            }
        else:
            scored = hasattr(policy, "last_scores")
            metadata = {
                **metadata,
                "serving_policy": (
                    "always-score-legal-argmax/v1" if scored else f"native-policy/{policy.revision}"
                ),
                "serving_assistance": "none-beyond-legal-candidate-selection",
            }
        return policy, metadata

    if args.candidate_backend == "first-legal":
        return finalize(FirstLegalPolicy(args.policy_id), {"backend": "first-legal", "model_ref": None})
    if args.candidate_backend == "random-legal":
        return finalize(benchmark.RandomLegalPolicy(args.candidate_seed, args.policy_id), {
            "backend": "random-legal",
            "model_ref": None,
        })
    if args.candidate_backend == "python-checkpoint":
        if not args.checkpoint or not args.model_ref:
            raise ValueError("Python checkpoint candidate requires --checkpoint and --model-ref")
        from chess_python_checkpoint import PythonCheckpointChessPolicy

        policy = PythonCheckpointChessPolicy(
            args.checkpoint,
            args.model_ref,
            args.policy_id,
            device=args.candidate_device,
            candidate_batch_size=args.candidate_batch_size,
        )
        return finalize(policy, {
            "backend": "python-checkpoint",
            "model_ref": args.model_ref,
            "checkpoint_sha256": policy.checkpoint_sha256,
            "device": policy.device,
            "model_load_time_ms": policy.model_load_time_ms,
        })
    if not args.model or not args.model_ref:
        raise ValueError("MLX candidate requires --model and --model-ref")
    from chess_mlx_pilot import MlxChessPolicy

    policy = MlxChessPolicy(args.model, args.model_ref, args.policy_id)
    return finalize(policy, {
        "backend": "mlx",
        "model_ref": args.model_ref,
        "model_load_time_ms": policy.model_load_time_ms,
    })


def run_ladder(
    candidate,
    candidate_metadata: dict[str, Any],
    config: dict[str, Any],
    openings: dict[str, Any],
    binary: str,
    opponent_factory: Callable[[dict[str, Any]], StockfishRungPolicy] | None = None,
    calibration_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    games: list[dict[str, Any]] = []
    identities: dict[str, Any] = {}
    factory = opponent_factory or (lambda rung: StockfishRungPolicy(rung, config["engine"], binary))
    for rung_index, rung in enumerate(config["rungs"]):
        for opening_index, opening in enumerate(openings["openings"]):
            for candidate_color in ("white", "black"):
                seeded_rung = {**rung, "seed": rung["seed"] + rung_index * 10000 + opening_index * 2 + (candidate_color == "black")}
                opponent = factory(seeded_rung)
                try:
                    if opponent.engine_identity is not None:
                        identities[rung["rung_id"]] = opponent.engine_identity
                    white, black = (candidate, opponent) if candidate_color == "white" else (opponent, candidate)
                    game = benchmark.run_game(
                        white,
                        black,
                        starting_fen=opening["fen"],
                        maximum_plies=config["maximum_plies"],
                    )
                finally:
                    opponent.close()
                games.append(
                    {
                        "game_id": f"{rung['rung_id']}:{opening['id']}:{candidate_color}",
                        "rung_id": rung["rung_id"],
                        "opening_id": opening["id"],
                        "candidate_color": candidate_color,
                        **game,
                    }
                )
    result = {
        "schema_version": RESULT_SCHEMA,
        "status": "candidate-evidence",
        "ladder_id": config["ladder_id"],
        "config_hash": benchmark.sha256_json(config),
        "opening_set_id": openings["opening_set_id"],
        "candidate": {"policy_id": candidate.policy_id, "revision": candidate.revision, **candidate_metadata},
        "engine": {
            "binary": binary,
            "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            "identities": identities,
        },
        "runtime": {"python": platform.python_version(), "python_chess": chess.__version__},
        "calibration": calibration_metadata,
        "aggregate": summarize_games(games, candidate.policy_id, config),
        "games": games,
    }
    result["trace_hash"] = benchmark.sha256_json(result)
    return result


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    calibration_metadata = None
    if args.calibration:
        calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
        config = apply_calibration(config, calibration)
        calibration_metadata = {
            "path": str(args.calibration),
            "trace_hash": calibration.get("trace_hash"),
            "method": calibration.get("method"),
        }
    openings_path = args.openings or Path(config["openings_ref"])
    openings = load_openings(openings_path)
    requested_binary = args.stockfish or config["engine"]["binary"]
    binary = shutil.which(requested_binary) or requested_binary
    if not Path(binary).is_file():
        raise ValueError(f"Stockfish binary not found: {requested_binary}")
    candidate, metadata = build_candidate(args)
    result = run_ladder(
        candidate,
        metadata,
        config,
        openings,
        binary,
        calibration_metadata=calibration_metadata,
    )
    benchmark.write_json_exclusive(args.output, result)
    print(json.dumps({"output": str(args.output), **result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
