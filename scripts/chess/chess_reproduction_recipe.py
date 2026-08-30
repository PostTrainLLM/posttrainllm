#!/usr/bin/env python3
"""Validate and summarize the staged Qwen Chess reproduction recipe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "chess/qwen-reproduction-recipe/v1"
SOURCE_NAMES = {"general", "endgame", "grounded_commentary"}


def load_recipe(path: Path) -> dict[str, Any]:
    recipe = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "recipe_id",
        "status",
        "model_config",
        "source_recipe",
        "sources",
        "stages",
        "evaluation",
        "stop_rules",
    }
    if not isinstance(recipe, dict) or recipe.get("schema_version") != SCHEMA_VERSION or set(recipe) != required:
        raise ValueError("unsupported or incomplete Qwen reproduction recipe")
    if set(recipe["sources"]) != SOURCE_NAMES:
        raise ValueError("reproduction recipe sources are incomplete")
    stages = recipe["stages"]
    if not isinstance(stages, list) or [row.get("total_rows") for row in stages] != [10000, 100000, 1000000, 2000000]:
        raise ValueError("reproduction stages must be ordered 10k, 100k, 1M, 2M")
    ids: set[str] = set()
    for stage in stages:
        if set(stage) != {"stage_id", "total_rows", "training_authorized", "arms", "promotion_gate"}:
            raise ValueError("reproduction stage fields are incomplete")
        if stage["stage_id"] in ids:
            raise ValueError("reproduction stage ids must be unique")
        ids.add(stage["stage_id"])
        if stage["training_authorized"] is not False:
            raise ValueError("frozen reproduction stages must remain operator-gated")
        if set(stage["arms"]) != {"terse", "commentary-8pct"}:
            raise ValueError("every reproduction stage needs matched terse and commentary arms")
        for arm_name, counts in stage["arms"].items():
            if set(counts) != SOURCE_NAMES or any(not isinstance(value, int) or value < 0 for value in counts.values()):
                raise ValueError("reproduction source counts are invalid")
            if sum(counts.values()) != stage["total_rows"]:
                raise ValueError(f"{stage['stage_id']} {arm_name} counts do not sum to total_rows")
        commentary = stage["arms"]["commentary-8pct"]["grounded_commentary"]
        if commentary * 100 != stage["total_rows"] * 8:
            raise ValueError("commentary arm must contain exactly eight percent grounded commentary")
        if stage["arms"]["terse"]["grounded_commentary"] != 0:
            raise ValueError("terse control must not contain commentary")
    evaluation = recipe["evaluation"]
    if evaluation.get("raw_serving_policy") == evaluation.get("guarded_serving_policy"):
        raise ValueError("raw and guarded serving policies must be distinct")
    if not evaluation.get("rerate_after_any_policy_change") or not evaluation.get("report_guard_fire_rate"):
        raise ValueError("reproduction evaluation must rerate policy changes and report guard fire rate")
    return recipe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    recipe = load_recipe(args.config)
    print(
        json.dumps(
            {
                "recipe_id": recipe["recipe_id"],
                "status": recipe["status"],
                "stages": [
                    {"stage_id": row["stage_id"], "total_rows": row["total_rows"], "training_authorized": False}
                    for row in recipe["stages"]
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
