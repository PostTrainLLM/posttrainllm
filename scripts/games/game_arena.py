#!/usr/bin/env python3
"""Build deterministic, evidence-preserving ratings across game families."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Callable, Sequence

CONFIG_SCHEMA = "game-arena/config/v1"
REPORT_SCHEMA = "game-arena/report/v1"
FAMILIES = {"head-to-head", "paired-score"}


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires values")
    ordered = sorted(values)
    location = (len(ordered) - 1) * probability
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    fraction = location - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("rating system is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column])
            ]
    return [augmented[index][-1] for index in range(size)]


def _fit_strengths(
    participants: Sequence[str],
    matches: Sequence[dict[str, Any]],
    prior_standard_deviation: float,
) -> dict[str, float]:
    ids = sorted(participants)
    indexes = {policy_id: index for index, policy_id in enumerate(ids)}
    theta = [0.0] * len(ids)
    prior_theta_sd = prior_standard_deviation * math.log(10) / 400
    precision = 1 / (prior_theta_sd * prior_theta_sd)
    for _ in range(100):
        gradient = [-value * precision for value in theta]
        information = [[0.0] * len(ids) for _ in ids]
        for index in range(len(ids)):
            information[index][index] = precision
        for match in matches:
            white = indexes[match["white_policy_id"]]
            black = indexes[match["black_policy_id"]]
            difference = max(-30.0, min(30.0, theta[white] - theta[black]))
            expected = 1 / (1 + math.exp(-difference))
            actual = match["white_score"]
            residual = actual - expected
            gradient[white] += residual
            gradient[black] -= residual
            weight = expected * (1 - expected)
            information[white][white] += weight
            information[black][black] += weight
            information[white][black] -= weight
            information[black][white] -= weight
        step = solve_linear(information, gradient)
        theta = [value + delta for value, delta in zip(theta, step)]
        mean = sum(theta) / len(theta)
        theta = [value - mean for value in theta]
        if max(abs(delta) for delta in step) < 1e-10:
            break
    return dict(zip(ids, theta))


def pool_is_connected(participants: Sequence[str], matches: Sequence[dict[str, Any]]) -> bool:
    if not participants:
        return False
    graph = {policy_id: set() for policy_id in participants}
    for match in matches:
        white = match["white_policy_id"]
        black = match["black_policy_id"]
        graph[white].add(black)
        graph[black].add(white)
    seen = set()
    pending = [participants[0]]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(graph[current] - seen)
    return seen == set(participants)


def fit_arena_elo(
    participants: Sequence[str],
    matches: Sequence[dict[str, Any]],
    rating_config: dict[str, Any],
    qualification_config: dict[str, Any],
) -> dict[str, Any]:
    ids = sorted(set(participants))
    if len(ids) < 2 or not matches:
        raise ValueError("head-to-head ratings require at least two policies and one match")
    for match in matches:
        if match["white_policy_id"] not in ids or match["black_policy_id"] not in ids:
            raise ValueError("match names an unknown policy")
        if match["white_policy_id"] == match["black_policy_id"]:
            raise ValueError("a policy cannot play itself")
        if match["white_score"] not in {0.0, 0.5, 1.0}:
            raise ValueError("white score must be win, draw, or loss")

    strengths = _fit_strengths(ids, matches, rating_config["prior_standard_deviation"])
    conversion = rating_config["scale"] / math.log(10)
    point_ratings = {
        policy_id: rating_config["base"] + conversion * strengths[policy_id]
        for policy_id in ids
    }
    samples = {policy_id: [] for policy_id in ids}
    rng = random.Random(rating_config["bootstrap_seed"])
    for _ in range(rating_config["bootstrap_samples"]):
        resampled = [matches[rng.randrange(len(matches))] for _ in matches]
        fitted = _fit_strengths(ids, resampled, rating_config["prior_standard_deviation"])
        for policy_id in ids:
            samples[policy_id].append(rating_config["base"] + conversion * fitted[policy_id])

    connected = pool_is_connected(ids, matches)
    match_counts = {
        policy_id: sum(
            match["white_policy_id"] == policy_id or match["black_policy_id"] == policy_id
            for match in matches
        )
        for policy_id in ids
    }
    color_counts = {
        policy_id: {
            "white": sum(match["white_policy_id"] == policy_id for match in matches),
            "black": sum(match["black_policy_id"] == policy_id for match in matches),
        }
        for policy_id in ids
    }
    color_balanced = all(abs(counts["white"] - counts["black"]) <= 1 for counts in color_counts.values())
    forfeit_count = sum(bool(match["forfeit"]) for match in matches)
    forfeit_rate = forfeit_count / len(matches)
    gate_checks = {
        "minimum_total_matches": len(matches) >= qualification_config["minimum_total_matches"],
        "minimum_matches_per_policy": all(
            count >= qualification_config["minimum_matches_per_policy"] for count in match_counts.values()
        ),
        "connected_pool": connected or not qualification_config["require_connected_pool"],
        "color_balance": color_balanced or not qualification_config["require_color_balance"],
        "maximum_forfeit_rate": forfeit_rate <= qualification_config["maximum_forfeit_rate"],
    }
    qualified = all(gate_checks.values())

    rows = []
    for policy_id in ids:
        wins = draws = losses = 0
        for match in matches:
            if policy_id not in {match["white_policy_id"], match["black_policy_id"]}:
                continue
            score = match["white_score"] if match["white_policy_id"] == policy_id else 1 - match["white_score"]
            wins += score == 1
            draws += score == 0.5
            losses += score == 0
        rows.append(
            {
                "policy_id": policy_id,
                "rating": round(point_ratings[policy_id], 1),
                "rating_interval_95": {
                    "lower": round(quantile(samples[policy_id], 0.025), 1),
                    "upper": round(quantile(samples[policy_id], 0.975), 1),
                },
                "status": "rated" if qualified else "unrated",
                "matches": match_counts[policy_id],
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "white_matches": color_counts[policy_id]["white"],
                "black_matches": color_counts[policy_id]["black"],
            }
        )
    rows.sort(key=lambda row: (-row["rating"], row["policy_id"]))
    return {
        "rating_name": "Arena Elo",
        "human_elo_equivalence": "unknown-and-not-claimed",
        "method": "regularized-bradley-terry-match-bootstrap",
        "qualification": {
            "qualified": qualified,
            "checks": gate_checks,
            "unmet": [name for name, passed in gate_checks.items() if not passed],
        },
        "matches": len(matches),
        "forfeits": forfeit_count,
        "forfeit_rate": forfeit_rate,
        "connected_pool": connected,
        "color_balanced": color_balanced,
        "ratings": rows,
    }


def score_paired_trials(
    trials: Sequence[dict[str, Any]],
    source_states: dict[str, dict[str, Any]],
    rating_config: dict[str, Any],
    qualification_config: dict[str, Any],
) -> dict[str, Any]:
    if not trials:
        raise ValueError("paired-score ratings require trials")
    by_policy: dict[str, list[dict[str, Any]]] = {}
    for trial in trials:
        if not isinstance(trial.get("policy_score"), (int, float)) or not isinstance(
            trial.get("baseline_score"), (int, float)
        ):
            raise ValueError("paired scores must be numeric")
        by_policy.setdefault(trial["policy_id"], []).append(trial)
    rows = []
    for policy_index, policy_id in enumerate(sorted(by_policy)):
        policy_trials = by_policy[policy_id]
        deltas = [trial["policy_score"] - trial["baseline_score"] for trial in policy_trials]
        rng = random.Random(rating_config["bootstrap_seed"] + policy_index + 1)
        bootstrap = []
        for _ in range(rating_config["bootstrap_samples"]):
            sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
            bootstrap.append(sum(sample) / len(sample))
        complete_source = bool(source_states[policy_id]["complete"])
        checks = {
            "minimum_complete_pairs": len(policy_trials)
            >= qualification_config["minimum_complete_pairs_per_policy"],
            "complete_source": complete_source or not qualification_config["require_complete_source"],
        }
        model_scores = [trial["policy_score"] for trial in policy_trials]
        baseline_scores = [trial["baseline_score"] for trial in policy_trials]
        paired_points = [1 if delta > 0 else 0.5 if delta == 0 else 0 for delta in deltas]
        rows.append(
            {
                "policy_id": policy_id,
                "baseline_policy_id": policy_trials[0]["baseline_policy_id"],
                "pairs": len(policy_trials),
                "policy_mean_score": sum(model_scores) / len(model_scores),
                "baseline_mean_score": sum(baseline_scores) / len(baseline_scores),
                "paired_mean_delta": sum(deltas) / len(deltas),
                "paired_delta_interval_95": {
                    "lower": quantile(bootstrap, 0.025),
                    "upper": quantile(bootstrap, 0.975),
                },
                "paired_win_rate": sum(paired_points) / len(paired_points),
                "status": "qualified" if all(checks.values()) else "unqualified",
                "qualification": {
                    "qualified": all(checks.values()),
                    "checks": checks,
                    "unmet": [name for name, passed in checks.items() if not passed],
                },
                "source_status": source_states[policy_id]["status"],
                "provider_failures": source_states[policy_id]["provider_failures"],
            }
        )
    rows.sort(key=lambda row: (-row["paired_mean_delta"], row["policy_id"]))
    return {
        "rating_name": "Paired score",
        "elo": None,
        "why_no_elo": "Independent single-player episodes do not produce head-to-head win probabilities.",
        "entries": rows,
    }


def adapt_chess(source_path: Path, source: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    if source.get("schema_version") != "chess/mlx-paired-match/v1":
        raise ValueError("unsupported chess match artifact")
    participants = sorted(model["policy_id"] for model in source["models"])
    if len(participants) != len(set(participants)):
        raise ValueError("duplicate chess policy id")
    matches = []
    seen = set()
    for index, game in enumerate(source["games"]):
        evidence_key = f"{source_path.name}:{game['opening_id']}:{game['color_assignment']}"
        if evidence_key in seen:
            raise ValueError(f"duplicate match id: {evidence_key}")
        seen.add(evidence_key)
        match_id = f"{evidence_key}:{index}"
        outcome = game["outcome"]
        white_score = 0.5
        if outcome["winner"] == "white":
            white_score = 1.0
        elif outcome["winner"] == "black":
            white_score = 0.0
        elif outcome["winner"] is not None:
            raise ValueError("unsupported chess winner")
        matches.append(
            {
                "match_id": match_id,
                "white_policy_id": game["white"]["policy_id"],
                "black_policy_id": game["black"]["policy_id"],
                "white_score": white_score,
                "termination": outcome["termination"],
                "forfeit": outcome["termination"] == "invalid-decision-forfeit",
                "source_trace_hash": game.get("trace_hash"),
                "opening_id": game["opening_id"],
            }
        )
    return participants, matches, {
        "path": str(source_path),
        "trace_hash": source.get("trace_hash"),
        "status": source["status"],
        "games": len(matches),
    }


def adapt_2048(
    source_path: Path, source: dict[str, Any]
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    schema = source.get("schema_version")
    policy_id = source["model"]["requested"]
    trials = []
    if schema == "game-2048/frontier-screening-result/v1":
        for seed, model_score, baseline_score in zip(
            source["seeds"], source["model_scores"], source["random_legal_scores"]
        ):
            trials.append(
                {
                    "trial_id": f"{source_path.name}:{seed}",
                    "policy_id": policy_id,
                    "baseline_policy_id": "random-legal",
                    "instance_id": str(seed),
                    "policy_score": model_score,
                    "baseline_score": baseline_score,
                }
            )
        complete = True
    elif schema == "game-2048/frontier-screening-attempt/v1":
        for row in source["completed_games"]:
            trials.append(
                {
                    "trial_id": f"{source_path.name}:{row['seed']}",
                    "policy_id": policy_id,
                    "baseline_policy_id": "random-legal",
                    "instance_id": str(row["seed"]),
                    "policy_score": row["model_score"],
                    "baseline_score": row["random_legal_score"],
                }
            )
        complete = not source.get("interrupted_games")
    else:
        raise ValueError("unsupported 2048 screening artifact")
    return trials, policy_id, {
        "path": str(source_path),
        "trace_hash": source.get("trace_hash"),
        "status": source["status"],
        "complete": complete,
        "provider_failures": source.get("provider_failures", 0),
        "decision": source.get("decision"),
        "observed_cost_usd": source.get("total_cost_usd", source.get("total_observed_cost_usd")),
    }


Adapter = Callable[..., Any]
ADAPTERS: dict[str, Adapter] = {
    "chess-mlx-paired-match-v1": adapt_chess,
    "game-2048-frontier-screen-v1": adapt_2048,
}
ADAPTER_FAMILIES = {
    "chess-mlx-paired-match-v1": "head-to-head",
    "game-2048-frontier-screen-v1": "paired-score",
}


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("unsupported arena config")
    if not isinstance(config.get("games"), list) or not config["games"]:
        raise ValueError("arena config must contain games")
    ids = []
    for game in config["games"]:
        if game.get("competition_family") not in FAMILIES:
            raise ValueError("unsupported competition family")
        if game.get("adapter") not in ADAPTERS:
            raise ValueError("unsupported game adapter")
        if ADAPTER_FAMILIES[game["adapter"]] != game["competition_family"]:
            raise ValueError("adapter is incompatible with competition family")
        if not isinstance(game.get("sources"), list) or not game["sources"]:
            raise ValueError("game adapter requires sources")
        ids.append(game["game_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate game id")
    rating = config.get("rating", {})
    for field in ("base", "scale", "prior_standard_deviation", "bootstrap_samples", "bootstrap_seed"):
        if not isinstance(rating.get(field), (int, float)) or isinstance(rating.get(field), bool):
            raise ValueError(f"invalid rating field: {field}")
    if rating["scale"] <= 0 or rating["prior_standard_deviation"] <= 0 or rating["bootstrap_samples"] < 1:
        raise ValueError("rating scale, prior, and samples must be positive")


def build_report(config_path: Path, root: Path) -> dict[str, Any]:
    config = load_json(config_path)
    validate_config(config)
    games = []
    for game in config["games"]:
        sources = [(Path(path), load_json(root / path)) for path in game["sources"]]
        if game["competition_family"] == "head-to-head":
            participants: set[str] = set()
            matches = []
            provenance = []
            for path, source in sources:
                source_participants, source_matches, source_provenance = ADAPTERS[game["adapter"]](path, source)
                participants.update(source_participants)
                matches.extend(source_matches)
                provenance.append(source_provenance)
            if len({match["match_id"] for match in matches}) != len(matches):
                raise ValueError("duplicate normalized match id")
            result = fit_arena_elo(
                sorted(participants),
                matches,
                config["rating"],
                config["qualification"]["head_to_head"],
            )
            evidence = {"participants": sorted(participants), "matches": matches, "sources": provenance}
        else:
            trials = []
            source_states = {}
            provenance = []
            for path, source in sources:
                source_trials, policy_id, source_state = ADAPTERS[game["adapter"]](path, source)
                if policy_id in source_states:
                    raise ValueError(f"duplicate paired-score policy source: {policy_id}")
                trials.extend(source_trials)
                source_states[policy_id] = source_state
                provenance.append(source_state)
            if len({trial["trial_id"] for trial in trials}) != len(trials):
                raise ValueError("duplicate normalized trial id")
            result = score_paired_trials(
                trials,
                source_states,
                config["rating"],
                config["qualification"]["paired_score"],
            )
            evidence = {"trials": trials, "sources": provenance}
        games.append(
            {
                "game_id": game["game_id"],
                "name": game["name"],
                "competition_family": game["competition_family"],
                "adapter": game["adapter"],
                "replay_path": game["replay_path"],
                "result": result,
                "evidence": evidence,
            }
        )
    report = {
        "schema_version": REPORT_SCHEMA,
        "arena_id": config["arena_id"],
        "status": config["status"],
        "config": config,
        "games": games,
        "claims": {
            "cross_game_universal_rating": False,
            "human_elo_equivalence": False,
            "specialist_win": False,
            "model_calls_performed": 0,
        },
    }
    report["trace_hash"] = canonical_hash(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report(args.config, args.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.check:
        if args.check.read_text(encoding="utf-8") != rendered:
            raise ValueError(f"arena report drifted: {args.check}")
        print(json.dumps({"check": str(args.check), "status": "pass", "trace_hash": report["trace_hash"]}))
    else:
        assert args.output is not None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite arena report: {args.output}")
        args.output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "games": len(report["games"]), "trace_hash": report["trace_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
