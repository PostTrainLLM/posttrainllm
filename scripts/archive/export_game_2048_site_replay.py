
# These modules moved to sibling group folders when scripts/ was grouped;
# add those folders to the import path so this archived script still runs.
import sys as _sys
from pathlib import Path as _Path
for _g in ["games"]:
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / _g))

#!/usr/bin/env python3
"""Compile local 2048 pilot runs into a portable, path-scrubbed site artifact."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import game_2048 as game  # noqa: E402

MODEL_METADATA = {
    "qwen3-0.6b-bf16": {
        "name": "Qwen3 0.6B",
        "size": "0.6B",
        "role": "small-base",
        "model_ref": "Qwen/Qwen3-0.6B",
    },
    "qwen3-4b-instruct-2507-4bit": {
        "name": "Qwen3 4B Instruct",
        "size": "4B",
        "role": "larger-general-llm",
        "model_ref": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
    },
    "qwen3.5-9b-mlx-4bit": {
        "name": "Qwen3.5 9B",
        "size": "9B class",
        "role": "larger-general-llm",
        "model_ref": "lmstudio-community/Qwen3.5-9B-MLX-4bit",
    },
}

DIAGNOSTIC_METADATA = {
    "random-legal": {
        "name": "Random legal moves",
        "explanation": "Uniformly samples only from actions that change the current board.",
        "structural_advantage": "It can never choose an illegal or no-op direction, so it measures a valid-executor floor rather than intelligence.",
    },
    "greedy-one-ply": {
        "name": "One-move heuristic",
        "explanation": "Simulates every legal move once and scores merge gain, empty cells, monotonicity, and corner position.",
        "structural_advantage": "It receives the exact transition function; it is an engine sanity check, not an LLM competitor or teacher.",
    },
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "game-2048/mlx-character-pilot/v1":
        raise ValueError(f"unsupported pilot artifact: {path}")
    return value


def compact_episode(result: dict[str, Any], episode: dict[str, Any], raw_offset: int) -> dict[str, Any]:
    raw_outputs = result["raw_outputs"][raw_offset : raw_offset + len(episode["records"])]
    if len(raw_outputs) != len(episode["records"]):
        raise ValueError("raw output count does not match decisions")
    decisions = []
    for record, raw in zip(episode["records"], raw_outputs):
        pre_score = record["cumulative_score"] - record["score_delta"]
        pre_moves = record["move_count"] - (1 if record["valid"] else 0)
        observation = {
            "board": record["pre_move_board"],
            "score": pre_score,
            "move_count": pre_moves,
            "legal_actions": record["legal_actions"],
        }
        decisions.append(
            {
                "step": record["step_index"],
                "input": game.serialize_character_observation(observation),
                "board": record["pre_move_board"],
                "score": pre_score,
                "move_count": pre_moves,
                "legal_actions": record["legal_actions"],
                "raw_output": raw,
                "action": record["chosen_action"],
                "valid": record["valid"],
                "failure": record["failure"],
                "post_board": record["post_move_board"],
                "post_score": record["cumulative_score"],
            }
        )
    metrics = episode["metrics"]
    return {
        "seed": episode["seed"],
        "score": metrics["score"],
        "maximum_tile": metrics["maximum_tile"],
        "moves": metrics["move_count"],
        "invalid_decisions": metrics["decisions"] - metrics["legal_decisions"],
        "terminal_reason": episode["terminal_reason"],
        "trace_hash": episode["trace_hash"],
        "final_board": episode["final_observation"]["board"],
        "decision_latencies_ns": episode["decision_latencies_ns"],
        "decisions": decisions,
    }


def aggregate(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [value / 1_000_000 for episode in episodes for value in episode["decision_latencies_ns"]]
    return {
        "games": len(episodes),
        "mean_score": statistics.fmean(episode["score"] for episode in episodes),
        "mean_maximum_tile": statistics.fmean(episode["maximum_tile"] for episode in episodes),
        "mean_moves": statistics.fmean(episode["moves"] for episode in episodes),
        "invalid_decisions": sum(episode["invalid_decisions"] for episode in episodes),
        "median_decision_latency_ms": statistics.median(latencies),
    }


def diagnostic_rows(seeds: list[int], config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for entry in config["baselines"]:
        episodes = [
            game.run_episode(game.make_policy(entry, seed), seed, max_moves=128, per_move_milliseconds=1_000)
            for seed in seeds
        ]
        rows.append(
            {
                "policy_id": entry["policy_id"],
                **DIAGNOSTIC_METADATA[entry["policy_id"]],
                "role": "algorithmic-diagnostic-only",
                "mean_score": statistics.fmean(episode["metrics"]["score"] for episode in episodes),
                "mean_maximum_tile": statistics.fmean(episode["metrics"]["maximum_tile"] for episode in episodes),
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--evaluation-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    model_load_ms: dict[str, list[float]] = {}
    for path in args.input:
        result = load(path)
        policy_id = result["model"]["policy_id"]
        if policy_id not in MODEL_METADATA:
            raise ValueError(f"model metadata is not declared for {policy_id}")
        offset = 0
        for episode in result["episodes"]:
            compact = compact_episode(result, episode, offset)
            offset += len(episode["records"])
            if episode["seed"] in grouped.setdefault(policy_id, {}):
                raise ValueError(f"duplicate {policy_id} seed {episode['seed']}")
            grouped[policy_id][episode["seed"]] = compact
        model_load_ms.setdefault(policy_id, []).append(result["model_load_time_ms"])

    seed_sets = {tuple(sorted(episodes)) for episodes in grouped.values()}
    if len(seed_sets) != 1:
        raise ValueError("every model must have the same paired development seeds")
    seeds = list(next(iter(seed_sets)))
    models = []
    for policy_id, episodes_by_seed in grouped.items():
        episodes = [episodes_by_seed[seed] for seed in seeds]
        models.append(
            {
                "policy_id": policy_id,
                **MODEL_METADATA[policy_id],
                "status": "measured-development-pilot",
                "evaluation_track": "strict",
                "mean_load_time_ms": statistics.fmean(model_load_ms[policy_id]),
                "aggregate": aggregate(episodes),
                "episodes": episodes,
            }
        )
    models.sort(key=lambda model: float(model["size"].split("B")[0].strip()))
    models.append(
        {
            "policy_id": "custom-2048-slm",
            "name": "Our 2048 specialist",
            "size": "30–50M (≤50M)",
            "role": "specialist-candidate",
            "model_ref": None,
            "status": "blocked-benchmark-rejected",
            "aggregate": None,
            "episodes": [],
        }
    )

    evaluation_config = json.loads(args.evaluation_config.read_text(encoding="utf-8"))
    artifact = {
        "schema_version": "game-2048/site-replay/v1",
        "benchmark": {
            "id": "game-2048-character-policy",
            "name": "Character 2048",
            "status": "rejected-current-character-form",
            "artifact_disposition": "retained-negative-result",
            "reproduction_status": "intelligence-advantage-not-reproduced",
            "claim": "Can a 30–50M specialist compress game intelligence from a frontier general LLM?",
            "environment_revision": game.ENVIRONMENT_REVISION,
            "observation_revision": game.CHARACTER_OBSERVATION_REVISION,
            "seeds": seeds,
            "max_moves": 128,
            "admission_gate": {
                "status": "failed-development-intelligence-gradient",
                **evaluation_config["benchmark_admission"],
                "paired_seed_count": 30,
            },
            "limitations": [
                "Three development seeds; this is not frozen benchmark evidence.",
                "This artifact is intentionally retained as a failed benchmark attempt, not presented as a successful or complete reproduction.",
                "The 9B-class local model is the closest installed general model to the requested 8B comparison.",
                "No 30–50M custom specialist was trained because the benchmark failed before training.",
                "Pinned Sonnet matched random legal play on the valid four-game screen (0.995× mean score).",
                "Pinned Opus completed three games at 1.058× random, below the 1.10× threshold, before a provider disconnect invalidated its fourth game.",
                "These prerecorded local results are strict-track only; the legal-constrained diagnostic is not yet recorded.",
                "Algorithmic policies are diagnostics only and never determine the LLM proof gate.",
            ],
        },
        "models": models,
        "diagnostics": diagnostic_rows(seeds, evaluation_config),
        "reproduce": {
            "runtime": "MLX-LM 0.31.3 on Apple Silicon",
            "command_template": "python3.12 scripts/games/game_2048_mlx_pilot.py --model <MODEL_REF> --policy-id <ID> --track strict --seed 2048000000 --seed 2048000001 --seed 2048000002 --max-moves 128 --output runs/game-2048/model-pilot/<ID>.json",
            "protocol": "Same character observation, greedy decoding, two output tokens maximum, no tools/search/code/rollouts.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError(f"refusing to overwrite {args.output}")
    args.output.write_text(json.dumps(artifact, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(models) - 1} measured models, {len(seeds)} paired seeds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
