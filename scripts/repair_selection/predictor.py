"""Frozen ordinary outcome-prediction and ranking baselines; no coder update."""

import random
import time

import numpy as np

from executor import inspect

FEATURES = [
    "bias",
    "public_all_pass",
    "valid",
    "nodes/500",
    "ifs/10",
    "comparisons/10",
    "literals/20",
    "pass_raise/10",
    "characters/4096",
]
METHODS = ["random", "static", "execution", "frozen", "adapted"]


def features(row):
    info = inspect(row["code"])
    return [
        1,
        int(row["public"]["passed"]),
        int(info["valid"]),
        info["nodes"] / 500,
        info["ifs"] / 10,
        info["comparisons"] / 10,
        info["literals"] / 20,
        info["pass_raise"] / 10,
        len(row["code"]) / 4096,
    ]


def fit(rows):
    started = time.monotonic()
    x = np.array([features(row) for row in rows], dtype=float)
    y = np.array([row["hidden"]["passed"] for row in rows], dtype=float)
    weights = np.linalg.solve(x.T @ x + np.eye(x.shape[1]), x.T @ y)
    assert np.isfinite(weights).all()
    return {
        "weights": weights.tolist(),
        "training_rows": len(rows),
        "seconds": time.monotonic() - started,
        "ridge": 1.0,
    }


def predict(row, model):
    return float(np.clip(np.dot(features(row), model["weights"]), 0, 1))


def select(pool, method, models, seed):
    started = time.monotonic()
    if method == "random":
        index = random.Random(seed).randrange(len(pool))
    elif method == "static":

        def key(index):
            info = inspect(pool[index]["code"])
            return not info["valid"], info["pass_raise"], info["nodes"], index

        index = min(range(len(pool)), key=key)
    elif method == "execution":
        index = min(
            range(len(pool)), key=lambda i: (not pool[i]["public"]["passed"], i)
        )
    else:
        index = max(
            range(len(pool)), key=lambda i: (predict(pool[i], models[method]), -i)
        )
    return {"index": index, "seconds": time.monotonic() - started}


def brier(rows, model):
    return float(
        np.mean(
            [(predict(row, model) - int(row["hidden"]["passed"])) ** 2 for row in rows]
        )
    )


def charged_public(pool, method, selection, final=False):
    # Static/random do not inspect execution feedback to rank candidates. Their
    # selected round-one candidate still needs public feedback for round two.
    if method in ["random", "static"]:
        return [] if final else [pool[selection["index"]]["public"]]
    return [row["public"] for row in pool]
