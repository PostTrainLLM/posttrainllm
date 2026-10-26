"""Real Timestral inference, synthetic data, pinball adaptation and backtesting.

Uses mistralai/timestral at the commit pinned in pyproject.toml. Code is
Apache-2.0; upstream model weights have their separate Modified MIT license.
Contract: docs/factory/specialist-labs.md. No downloads at import.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from pathlib import Path

import numpy as np

from common import (
    Budget,
    digest,
    file_hash,
    read_json,
    read_rows,
    write_json,
    write_rows,
)

COVARIATES = (
    "past_covariates",
    "known_covariates",
    "categorical_past_covariates",
    "categorical_known_covariates",
)


def matrix(value, name):
    result = np.asarray(
        value, dtype=np.float64 if name.startswith("categorical") else np.float32
    )
    if result.ndim != 2 or not all(result.shape) or np.isinf(result).any():
        raise ValueError(
            f"{name} must be a nonempty variates × time matrix; use null for missing"
        )
    return result


def inputs(row, horizon):
    if not isinstance(horizon, int) or not 1 <= horizon <= 1024:
        raise ValueError("horizon must be in [1,1024]")
    context = matrix(row["context"], "context")
    if context.shape[0] > 32 or not 1 <= context.shape[1] <= 32768:
        raise ValueError("context exceeds the local row/context budget")
    if not np.isfinite(context).any(axis=1).all():
        raise ValueError("each target variate needs an observed history value")
    kwargs = {}
    for name in COVARIATES:
        if name not in row:
            continue
        values = matrix(row[name], name)
        expected = context.shape[1] + (horizon if "known" in name else 0)
        if values.shape[1] != expected or values.shape[0] > 32:
            raise ValueError(
                f"{name} must cover exactly {expected} time steps and <=32 rows"
            )
        kwargs[name] = values[None]
    if "observation_mask" in row:
        mask = np.asarray(row["observation_mask"])
        if mask.dtype != bool or mask.shape != context.shape:
            raise ValueError("observation_mask must be boolean and match context")
        if not (mask & np.isfinite(context)).any(axis=1).all():
            raise ValueError("each target needs an unmasked observation")
        kwargs["observation_mask"] = mask[None]
    return context[None], kwargs


def load(model, revision=None, offline=True, budget=None):
    budget = budget or Budget()
    budget.torch()
    from timestral import TimestralForecaster
    from timestral.loading import resolve_checkpoint

    path = resolve_checkpoint(
        model, revision=revision, local_files_only=offline, token=False
    )
    identity = digest(
        {
            "config": file_hash(path / "config.json"),
            "weights": file_hash(path / "model.safetensors"),
        }
    )
    if (path / "specialist.json").exists() and read_json(path / "specialist.json").get(
        "artifact_identity"
    ) != identity:
        raise ValueError("forecast checkpoint does not match its artifact identity")
    forecaster = TimestralForecaster.from_pretrained(
        path,
        device="cpu",
        revision=revision,
        local_files_only=offline,
        token=False,
    )
    forecaster.model.eval()
    forecaster.source_identity = identity
    return forecaster


def forecast(forecaster, row, horizon):
    context, kwargs = inputs(row, horizon)
    output = forecaster.forecast(context, prediction_length=horizon, **kwargs)
    values = output.quantiles.detach().cpu().numpy()[0]
    if values.shape != (context.shape[1], horizon, len(output.quantile_levels)):
        raise ValueError("upstream forecast shape mismatch")
    if not np.isfinite(values).all() or (np.diff(values, axis=-1) < 0).any():
        raise ValueError("forecast contains nonfinite or crossing quantiles")
    return {
        "id": row["id"],
        "quantile_levels": list(output.quantile_levels),
        "quantiles": values.tolist(),
        "median": output.median[0].detach().cpu().tolist(),
        "input_sha256": digest(row),
        "quality": "unqualified",
        "model_identity": getattr(forecaster, "source_identity", None),
    }


def pinball(prediction, target, levels):
    """Masked differentiable pinball loss; observations with null gold are absent."""
    import torch

    mask = torch.isfinite(target)
    if not mask.any():
        raise ValueError("training target has no observed values")
    error = torch.where(mask, target, 0).unsqueeze(-1) - prediction
    q = torch.tensor(levels, device=prediction.device, dtype=prediction.dtype)
    losses = torch.maximum(q * error, (q - 1) * error)
    return losses[mask].mean()


def training_tensors(forecaster, row):
    """Use the pinned upstream inference preprocessing, with differentiable decode.

    Private helpers are intentionally bound to the dependency commit. This keeps
    forward fill, categorical encoding, padding and masks identical at inference
    and adaptation, rather than maintaining a second subtly different pipeline.
    """
    import torch

    target = matrix(row["target"], "target")
    horizon = target.shape[1]
    context, kwargs = inputs(row, horizon)
    if target.shape[0] != context.shape[1]:
        raise ValueError("target variates must match context")
    values, observed = forecaster._as_context(context, kwargs.get("observation_mask"))
    length = context.shape[-1]
    patch = forecaster.config.patch_size
    patches = math.ceil(horizon / patch)
    if patches > forecaster.config.block_size:
        raise ValueError("adaptation target exceeds one trained forecast block")
    encoding_target = forecaster._encoding_target(values, observed)
    covariates = []
    for name in ("past_covariates", "known_covariates"):
        size = length + (horizon if "known" in name else 0)
        numeric = forecaster._as_covariates(kwargs.get(name), 1, size, name)
        codes = forecaster._as_categorical(
            kwargs.get("categorical_" + name), 1, size, "categorical_" + name
        )
        encoded = forecaster._encode_categorical(codes, encoding_target)
        pieces = [v for v in (numeric, encoded) if v is not None]
        covariates.append(torch.cat(pieces, dim=1) if pieces else None)
    packed, mask, roles, future, future_mask, _ = forecaster._assemble_rows(
        values, observed, horizon, *covariates
    )
    return (
        {
            "inputs": packed[0],
            "observed": mask[0],
            "group_ids": torch.zeros(packed.shape[1], dtype=torch.long),
            "horizon_patches": patches,
            "role_ids": roles,
            "known_future": future,
            "known_future_mask": future_mask,
        },
        torch.tensor(target),
        horizon,
    )


def train(forecaster, rows, out, steps, budget):
    import torch
    from safetensors.torch import save_file

    if not 1 <= steps <= 10000:
        raise ValueError("steps must be in [1,10000]")
    if Path(out).exists():
        raise FileExistsError(out)
    if not rows or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("training rows need unique ids")
    torch.manual_seed(7)
    tensors = [training_tensors(forecaster, row) for row in rows]
    optimizer = torch.optim.AdamW(forecaster.model.parameters(), lr=1e-5)
    forecaster.model.train()
    losses = []
    for step in range(steps):
        budget.check()
        kwargs, target, horizon = tensors[step % len(tensors)]
        optimizer.zero_grad()
        result = forecaster.model.predict_block(**kwargs)[: len(target), :horizon]
        loss = pinball(result, target, forecaster.quantile_levels)
        if not torch.isfinite(loss):
            raise ValueError("nonfinite forecast training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(forecaster.model.parameters(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach()))
        budget.progress(step + 1, steps, losses[-1])
    out = Path(out)
    out.mkdir(parents=True)
    save_file(
        {k: v.detach().contiguous() for k, v in forecaster.model.state_dict().items()},
        out / "model.safetensors",
    )
    write_json(out / "config.json", dataclasses.asdict(forecaster.config))
    artifact_identity = digest(
        {
            "config": file_hash(out / "config.json"),
            "weights": file_hash(out / "model.safetensors"),
        }
    )
    write_json(
        out / "specialist.json",
        {
            "kind": "forecast",
            "base_identity": getattr(forecaster, "source_identity", None),
            "artifact_identity": artifact_identity,
            "train_sha256": digest(rows),
            "steps": steps,
            "losses": losses,
            "quality": "unqualified",
            **budget.measurements(),
        },
    )
    forecaster.model.eval()
    forecaster.source_identity = artifact_identity


def seasonal_naive(context, horizon, season):
    if not isinstance(season, int) or not 1 <= season <= context.shape[-1]:
        raise ValueError("season must be a positive lag no longer than context")
    # Forward-fill within each variate; no future observations enter baseline.
    filled = context.copy()
    for row in filled:
        previous = float(row[np.isfinite(row)][0])
        for index in range(len(row)):
            if np.isfinite(row[index]):
                previous = row[index]
            else:
                row[index] = previous
    return np.stack([filled[:, -season + i % season] for i in range(horizon)], axis=1)


def origin_input(series, data, origin, horizon):
    row = {"id": f"{series['id']}:{origin}"}
    # Use JSON null rather than NaN in hashable source records.
    row["context"] = [
        [float(v) if np.isfinite(v) else None for v in r] for r in data[:, :origin]
    ]
    for name in COVARIATES:
        if name not in series:
            continue
        values = matrix(series[name], name)
        if values.shape[1] != data.shape[1]:
            raise ValueError(f"{name} must align with the full series")
        cutoff = origin + (horizon if "known" in name else 0)
        row[name] = [
            [float(v) if np.isfinite(v) else None for v in r]
            for r in values[:, :cutoff]
        ]
    return row


def backtest(forecaster, series, horizon, origins, season, budget):
    """Strict rolling origins. Input has complete targets, sliced before each call."""
    data = matrix(series["values"], "values")
    if not origins or len(set(origins)) != len(origins):
        raise ValueError("need distinct rolling origins")
    results = []
    for origin in origins:
        budget.check()
        if not season <= origin or origin + horizon > data.shape[1]:
            raise ValueError("rolling origin is outside the available history/future")
        row = origin_input(series, data, origin, horizon)
        predicted = forecast(forecaster, row, horizon)
        median = np.asarray(predicted["median"])
        gold = data[:, origin : origin + horizon]
        mask = np.isfinite(gold)
        if not mask.any():
            raise ValueError("rolling holdout has no observed targets")
        naive = seasonal_naive(data[:, :origin], horizon, season)
        errors = gold[..., None] - np.asarray(predicted["quantiles"])
        levels = np.asarray(predicted["quantile_levels"])
        losses = np.maximum(levels * errors, (levels - 1) * errors)
        results.append(
            {
                "origin": origin,
                "model_mae": float(np.abs(median - gold)[mask].mean()),
                "naive_mae": float(np.abs(naive - gold)[mask].mean()),
                "pinball": float(losses[mask].mean()),
                "observed_targets": int(mask.sum()),
            }
        )
    return {
        "kind": "forecast-backtest",
        "rows": results,
        "interpretation": "chronological numeric backtest; not frontier capability accuracy",
        "decision": "unqualified",
        **budget.measurements(),
    }


def synthetic(seed=7, length=128):
    if not 32 <= length <= 32768:
        raise ValueError("synthetic length must be in [32,32768]")
    rng = np.random.default_rng(seed)
    time = np.arange(length)
    schedule = ((time % 24) < 12).astype(float)
    source = np.sin(time * 2 * np.pi / 24) + time * 0.002 + rng.normal(0, 0.05, length)
    related = 0.5 * source + 0.3 * source**2 + schedule + rng.normal(0, 0.03, length)
    return {
        "id": f"synthetic-{seed}",
        "values": [source.tolist(), related.tolist()],
        "known_covariates": [schedule.tolist()],
        "categorical_known_covariates": [(time % 7).astype(float).tolist()],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    child = sub.add_parser("synthetic")
    child.add_argument("--seed", type=int, default=7)
    child.add_argument("--length", type=int, default=128)
    child.add_argument("--out", required=True)
    for command in ("predict", "train", "backtest", "export-browser"):
        child = sub.add_parser(command)
        child.add_argument("--model", default="mistralai/Timestral-5M")
        child.add_argument("--revision")
        child.add_argument("--download", action="store_true")
        child.add_argument("--data", required=True)
        child.add_argument("--out", required=True)
        child.add_argument("--seconds", type=float, default=60)
        if command == "train":
            child.add_argument("--steps", type=int, default=1)
        else:
            child.add_argument("--horizon", type=int, default=24)
        if command == "backtest":
            child.add_argument("--origins", type=int, nargs="+", required=True)
            child.add_argument("--season", type=int, default=24)
    args = parser.parse_args()
    if args.command == "synthetic":
        write_rows(args.out, [synthetic(args.seed, args.length)])
        return
    budget = Budget(args.seconds)
    forecaster = load(args.model, args.revision, not args.download, budget)
    rows = read_rows(args.data)
    if args.command == "export-browser":
        from forecast_browser import export

        if len(rows) != 1:
            raise ValueError(
                "browser export accepts one example defining its input shape"
            )
        receipt = export(forecaster, rows[0], args.horizon, args.out, budget)
        print(json.dumps(receipt["measurements"]))
    elif args.command == "train":
        train(forecaster, rows, args.out, args.steps, budget)
    elif args.command == "predict":
        write_rows(args.out, [forecast(forecaster, row, args.horizon) for row in rows])
        print(json.dumps(budget.measurements()))
    else:
        if len(rows) != 1:
            raise ValueError("backtest accepts one multivariate series per run")
        write_json(
            args.out,
            backtest(
                forecaster, rows[0], args.horizon, args.origins, args.season, budget
            ),
        )


if __name__ == "__main__":
    main()
