#!/usr/bin/env python3
"""Target-masked SFT trainer for compiled Character Chess rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shlex
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import torch

REPO = Path(__file__).resolve().parent.parent
PYTHON_REF = REPO / "python_ref"
if str(PYTHON_REF) not in sys.path:
    sys.path.insert(0, str(PYTHON_REF))

from checkpoint import load_checkpoint, save_checkpoint  # noqa: E402
from model import ModelConfig, posttrainllm  # noqa: E402
from train import TrainConfig, build_optimizer, pick_device  # noqa: E402

import chess_benchmark as benchmark  # noqa: E402
import chess_sft_corpus as corpus  # noqa: E402
from autocorrect_adapter import GPULock  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--maximum-train-rows", type=int)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_compiled_rows(path: Path, maximum_train_rows: int | None = None) -> dict[str, list[dict[str, Any]]]:
    if maximum_train_rows is not None and maximum_train_rows < 1:
        raise ValueError("maximum_train_rows must be positive")
    splits = {"train": [], "validation": [], "test": []}
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as source:
        for line_number, raw_line in enumerate(source, 1):
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if not isinstance(row, dict) or row.get("schema_version") != corpus.ROW_SCHEMA:
                raise ValueError(f"unsupported compiled row at line {line_number}")
            unhashed = {key: value for key, value in row.items() if key != "row_hash"}
            if row.get("row_hash") != benchmark.sha256_json(unhashed):
                raise ValueError(f"compiled row hash mismatch at line {line_number}")
            fen = row.get("fen")
            split = row.get("split")
            if not isinstance(fen, str) or split not in splits or fen in seen:
                raise ValueError(f"invalid or duplicate compiled row at line {line_number}")
            if row.get("target") not in row.get("legal_moves", []):
                raise ValueError(f"compiled target is not legal at line {line_number}")
            sequence = f"{row['input']}{row['target']}\n".encode("utf-8")
            prompt = row["input"].encode("utf-8")
            if len(sequence) > 512 or len(prompt) < 1:
                raise ValueError(f"compiled sequence length is invalid at line {line_number}")
            seen.add(fen)
            if split != "train" or maximum_train_rows is None or len(splits["train"]) < maximum_train_rows:
                splits[split].append(row)
    if not splits["train"] or not splits["validation"] or not splits["test"]:
        raise ValueError("compiled pilot requires non-empty train, validation, and test splits")
    return splits


def encode_row(row: dict[str, Any]) -> tuple[list[int], list[int]]:
    prompt = list(row["input"].encode("utf-8"))
    completion = list(f"{row['target']}\n".encode("ascii"))
    sequence = prompt + completion
    inputs = sequence[:-1]
    targets = sequence[1:]
    masked = [-100] * (len(prompt) - 1) + targets[len(prompt) - 1 :]
    if len(inputs) != len(masked) or masked.count(-100) != len(prompt) - 1:
        raise AssertionError("target-mask alignment failed")
    return inputs, masked


def collate_rows(rows: Sequence[dict[str, Any]], device: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    encoded = [encode_row(row) for row in rows]
    maximum = max(len(inputs) for inputs, _ in encoded)
    inputs = [tokens + [0] * (maximum - len(tokens)) for tokens, _ in encoded]
    targets = [labels + [-100] * (maximum - len(labels)) for _, labels in encoded]
    return (
        torch.tensor(inputs, dtype=torch.long, device=device),
        torch.tensor(targets, dtype=torch.long, device=device),
    )


def sample_rows(rows: Sequence[dict[str, Any]], batch_size: int, generator: torch.Generator) -> list[dict[str, Any]]:
    indices = torch.randint(0, len(rows), (batch_size,), generator=generator).tolist()
    return [rows[index] for index in indices]


@torch.no_grad()
def evaluate_loss(
    model: posttrainllm,
    rows: Sequence[dict[str, Any]],
    batch_size: int,
    device: torch.device,
    *,
    seed: int,
    batches: int = 20,
) -> float:
    model.eval()
    generator = torch.Generator().manual_seed(seed)
    losses = []
    for _ in range(batches):
        batch = sample_rows(rows, batch_size, generator)
        inputs, targets = collate_rows(batch, device)
        _, loss = model(inputs, targets)
        losses.append(float(loss.item()))
    model.train()
    return sum(losses) / len(losses)


def train(args: argparse.Namespace) -> None:
    if args.out.exists() and args.resume is None:
        raise ValueError(f"refusing to overwrite existing checkpoint directory: {args.out}")
    model_cfg = ModelConfig.from_json(args.model_config)
    if model_cfg.vocab_size != 256:
        raise ValueError("Character Chess SFT requires the byte vocabulary")
    train_cfg = TrainConfig.from_json(args.config)
    if args.max_steps is not None:
        if args.max_steps < 1:
            raise ValueError("max_steps must be positive")
        train_cfg.max_steps = args.max_steps
    rows = load_compiled_rows(args.data, args.maximum_train_rows)
    device = pick_device(args.device)
    torch.manual_seed(train_cfg.seed)
    generator = torch.Generator().manual_seed(train_cfg.seed)
    model = posttrainllm(model_cfg).to(device)
    optimizer = build_optimizer(model, train_cfg)
    start_step, loss_history, best_val = 0, [], math.inf
    prior_tokens_seen = 0
    prior_wall_time = 0.0
    if args.resume is not None:
        checkpoint = load_checkpoint(args.resume, map_location=device)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_step = checkpoint["step"]
        loss_history = checkpoint["loss_history"]
        best_val = checkpoint["trainer_state"].get("best_val_loss", math.inf)
        prior_tokens_seen = int(checkpoint["trainer_state"].get("tokens_seen", 0))
        prior_wall_time = float(checkpoint["trainer_state"].get("wall_time_sec", 0.0))
        if checkpoint["torch_rng_state"] is not None:
            torch.set_rng_state(checkpoint["torch_rng_state"].cpu())
        if start_step >= train_cfg.max_steps:
            raise ValueError("resume checkpoint is already at or beyond max_steps")
        # sample_rows uses a dedicated CPU generator. Advance it by the exact
        # number of indices consumed before the checkpoint so a resumed run
        # sees the same batches as an uninterrupted run.
        torch.randint(
            0,
            len(rows["train"]),
            (start_step * train_cfg.batch_size,),
            generator=generator,
        )
    manifest = {
        "schema_version": "chess/target-masked-sft-manifest/v1",
        "dataset_sha256": sha256_file(args.data),
        "rows": {name: len(values) for name, values in rows.items()},
        "objective": "completion-only-next-byte-cross-entropy",
        "prompt_loss_weight": 0,
        "completion_loss_weight": 1,
    }
    print(
        f"dataset: train={len(rows['train']):,} validation={len(rows['validation']):,} "
        f"test={len(rows['test']):,} sha={manifest['dataset_sha256'][:12]}..."
    )
    print(f"model: {model_cfg.model_name} {model.num_params():,} params device={device}")
    print("objective: completion-only loss; prompt bytes masked to -100")
    started = time.time()
    tokens_seen = prior_tokens_seen
    model.train()
    for step in range(start_step, train_cfg.max_steps + 1):
        if step % train_cfg.eval_interval == 0:
            train_loss = evaluate_loss(
                model, rows["train"], train_cfg.batch_size, device, seed=train_cfg.seed + step
            )
            val_loss = evaluate_loss(
                model, rows["validation"], train_cfg.batch_size, device, seed=train_cfg.seed + 1_000_000 + step
            )
            best_val = min(best_val, val_loss)
            loss_history.append({"step": step, "train_loss": train_loss, "val_loss": val_loss})
            print(f"step {step:>6} train {train_loss:.4f} val {val_loss:.4f}", flush=True)
        if step > start_step and step % train_cfg.checkpoint_interval == 0:
            save_checkpoint(
                args.out,
                model=model,
                optimizer=optimizer,
                model_config=model_cfg,
                training_config=train_cfg,
                manifest=manifest,
                step=step,
                loss_history=loss_history,
                best_val_loss=best_val,
                tokens_seen=tokens_seen,
                wall_time=prior_wall_time + time.time() - started,
            )
        if step == train_cfg.max_steps:
            break
        batch = sample_rows(rows["train"], train_cfg.batch_size, generator)
        inputs, targets = collate_rows(batch, device)
        _, loss = model(inputs, targets)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), train_cfg.grad_clip)
        optimizer.step()
        tokens_seen += int((targets != -100).sum().item())
        if not math.isfinite(float(loss.item())):
            raise RuntimeError(f"non-finite training loss at step {step}")
    save_checkpoint(
        args.out,
        model=model,
        optimizer=optimizer,
        model_config=model_cfg,
        training_config=train_cfg,
        manifest=manifest,
        step=train_cfg.max_steps,
        loss_history=loss_history,
        best_val_loss=best_val,
        tokens_seen=tokens_seen,
        wall_time=prior_wall_time + time.time() - started,
    )
    print(f"done: best validation loss={best_val:.4f} checkpoint={args.out}")


def main() -> int:
    command = shlex.join(sys.argv)
    with GPULock(command):
        train(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
