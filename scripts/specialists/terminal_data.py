"""Terminal episode identities and public oracle conditions.

Used by training and frozen evaluation. Contract: docs/factory/specialist-labs.md.
"""

import re

from common import digest


def identity(episode):
    return {
        "id": episode["id"],
        "sha256": digest(
            {
                "initial_screen": episode["initial_screen"],
                "frames": [
                    {"event": frame["event"], "screen": frame["screen"]}
                    for frame in episode["frames"]
                ],
            }
        ),
        "record_sha256": digest(episode),
        "world_id": episode.get("world_id", episode["id"]),
        "family": episode.get("family", "unspecified"),
        "seed": episode.get("seed"),
    }


def public_conditions(episode):
    """Hidden initial filesystem/app state must be declared, never inferred."""
    conditions = episode.get("world_conditions")
    if not isinstance(conditions, dict) or not conditions:
        raise ValueError("terminal ceiling needs explicit public world_conditions")
    required = {"cwd", "initial_files", "programs", "environment"}
    if not required.issubset(conditions):
        raise ValueError(
            "world_conditions must declare cwd, initial_files, programs and environment"
        )
    if episode.get("source", {}).get("kind") == "real-docker-terminal":
        image = conditions.get("image_id", "")
        if not isinstance(image, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", image
        ):
            raise ValueError("real terminal oracle needs an immutable image_id")
    return conditions


def heldout_identities(model, episodes):
    training = getattr(model, "training_episode_identities", None)
    if training is None:
        raise ValueError(
            "terminal artifact lacks training episode provenance; retrain before qualification"
        )
    evaluation = [identity(episode) for episode in episodes]
    for key in ("id", "sha256", "world_id"):
        values = [row[key] for row in evaluation]
        if len(set(values)) != len(values):
            raise ValueError(f"duplicate terminal evaluation {key}")
        if set(values) & {row[key] for row in training}:
            raise ValueError(f"terminal train/eval overlap in {key}")
    return evaluation
