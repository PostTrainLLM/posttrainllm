
# These modules moved to sibling group folders when scripts/ was grouped;
# add those folders to the import path so this archived script still runs.
import sys as _sys
from pathlib import Path as _Path
for _g in ["chess"]:
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / _g))

#!/usr/bin/env python3
"""Compile chess development evidence into a portable site replay artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import chess_benchmark as benchmark

SCHEMA_VERSION = "chess/site-replay/v1"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def model_row(result: dict[str, Any], role: str, size: str) -> dict[str, Any]:
    model = result.get("model") or result.get("policy")
    return {
        "policy_id": model["policy_id"],
        "name": {
            "qwen3-4b-instruct-2507-4bit": "Qwen3 4B",
            "qwen3.5-9b-mlx-4bit": "Qwen3.5 9B",
            "codex-gpt-5.5-development": "Codex gpt-5.5",
        }.get(model["policy_id"], model["policy_id"]),
        "model_ref": model.get("model_ref") or model.get("requested_model"),
        "role": role,
        "size": size,
        "identity_state": model.get("identity_state", "recorded-local-artifact"),
        "aggregate": result["aggregate"],
        "trace_hash": result["trace_hash"],
        "decisions": result["decisions"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--random", type=Path, required=True)
    parser.add_argument("--local-4b", type=Path, required=True)
    parser.add_argument("--local-9b", type=Path, required=True)
    parser.add_argument("--frontier", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suite = benchmark.load_puzzle_suite(args.suite)
    random_result = load(args.random)
    local_4b = load(args.local_4b)
    local_9b = load(args.local_9b)
    frontier = load(args.frontier)
    gate = load(args.gate)
    matches = load(args.matches)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": {
            "id": "chess-character-policy",
            "name": "Character Chess",
            "status": "development-gate-passed" if gate["passed"] else "development-gate-failed",
            "claim": "Can chess specialization compress frontier move selection into a 30–50M Mac-local model?",
            "primary_lane": "tactical-puzzles",
            "secondary_lane": "paired-full-games",
            "suite_id": suite["suite_id"],
            "environment_revision": benchmark.ENVIRONMENT_REVISION,
            "observation_revision": benchmark.OBSERVATION_REVISION,
            "limitations": gate["limitations"],
        },
        "gate": gate,
        "puzzles": suite["puzzles"],
        "models": [
            model_row(local_4b, "local-general-llm", "4B"),
            model_row(local_9b, "larger-local-general-llm", "9B"),
            model_row(frontier, "frontier-calibration-anchor", "frontier"),
            {
                "policy_id": "custom-chess-slm",
                "name": "Our chess specialist",
                "model_ref": None,
                "role": "specialist-candidate",
                "size": "30–50M (≤50M)",
                "identity_state": "not-trained",
                "aggregate": None,
                "trace_hash": None,
                "decisions": [],
            },
        ],
        "random": {
            "name": "Random legal",
            "representative": random_result["aggregate"],
            "calibration": random_result["calibration"],
            "trace_hash": random_result["trace_hash"],
            "decisions": random_result["decisions"],
        },
        "matches": matches,
        "reproduce": {
            "runtime": "python-chess 1.999 / Stockfish 18 labels / MLX-LM 0.31.3 on Apple Silicon",
            "puzzle_command": "python3.12 scripts/chess/chess_mlx_pilot.py --suite evals/chess/fixtures/development-puzzles-v1.json --model <MODEL_PATH> --model-ref <MODEL_REF> --policy-id <ID> --output runs/chess/<ID>.json",
            "match_command": "python3.12 scripts/chess/chess_mlx_match.py --openings configs/chess/openings-development-v1.json --model-a <PATH_A> --model-a-ref <REF_A> --policy-a <ID_A> --model-b <PATH_B> --model-b-ref <REF_B> --policy-b <ID_B> --output runs/chess/match.json",
            "protocol": "Same FEN, sorted legal UCI set, greedy decoding, eight output tokens maximum, no engine/tools/search/code/rollouts.",
        },
    }
    benchmark.write_json_exclusive(args.output, artifact)
    print(json.dumps({"output": str(args.output), "models": len(artifact["models"]), "puzzles": len(artifact["puzzles"]), "games": len(matches["games"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
