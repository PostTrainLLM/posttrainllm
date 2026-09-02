#!/usr/bin/env python3
"""Run the frozen Needle tiny-overfit or 2x2 LoRA training stage."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import pickle
import random
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
ARMS = (
    "plain-standard",
    "plain-safety",
    "distractor-standard",
    "distractor-safety",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(source: Path, patch: Path, expected_revision: str) -> None:
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if revision != expected_revision:
        raise ValueError(f"Needle source revision mismatch: {revision}")
    subprocess.run(
        ["git", "-C", str(source), "apply", "--reverse", "--check", str(patch)],
        check=True,
    )
    changed = set(
        subprocess.run(
            ["git", "-C", str(source), "diff", "--name-only"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    expected = {"needle/cli.py", "needle/model/finetune.py"}
    if changed != expected:
        raise ValueError(f"Needle source has unexpected changes: {sorted(changed)}")


def load_adapter_receipt(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        adapter = pickle.load(handle)
    losses = adapter["loss_history"]
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "seed": adapter["seed"],
        "steps": len(losses),
        "initial_loss": losses[0],
        "final_loss": adapter["final_loss"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("tiny", "full"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--tiny-gate", type=Path)
    return parser.parse_args()


def training_plan(config: dict[str, object], stage: str) -> list[tuple[str, int]]:
    seeds = (
        [config["factorial"]["seeds"][0]]
        if stage == "tiny"
        else config["factorial"]["seeds"]
    )
    order_rng = random.Random(13804)
    plan = []
    for seed in seeds:
        block = list(ARMS)
        order_rng.shuffle(block)
        plan.extend((arm, seed) for arm in block)
    return plan


def run_training(
    args: argparse.Namespace,
    recipe: dict[str, object],
    plan: list[tuple[str, int]],
    finetune_local: object,
) -> tuple[list[dict[str, object]], float]:
    adapter_dir = args.run_dir / (
        "tiny-adapters" if args.stage == "tiny" else "adapters"
    )
    adapter_dir.mkdir(parents=True, exist_ok=True)
    lock_path = Path.home() / ".cache/posttrainllm/gpu.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    outputs = []
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(f"GPU lock is already held: {lock_path}") from exc
        for arm, seed in plan:
            if (time.perf_counter() - started) / 3600 >= 3:
                raise SystemExit("Needle aggregate 3-hour training cap reached")
            data = ROOT / (
                "evals/needle2/successor-v1/"
                f"{'tiny' if args.stage == 'tiny' else 'train'}-{arm}.jsonl"
            )
            out = adapter_dir / f"{arm}-seed-{seed}.pkl"
            run_started = time.perf_counter()
            finetune_local(
                SimpleNamespace(
                    jsonl_path=str(data),
                    checkpoint=str(args.checkpoint),
                    epochs=recipe["epochs"],
                    batch_size=recipe["batch_size"],
                    lr=recipe["learning_rate"],
                    lora_rank=recipe["lora_rank"],
                    lora_alpha=recipe["lora_alpha"],
                    max_len=recipe["max_length"],
                    val_split=recipe["validation_split"],
                    generate=0,
                    model=None,
                    workers=1,
                    checkpoint_dir=str(adapter_dir),
                    out=str(out),
                    seed=seed,
                )
            )
            receipt = load_adapter_receipt(out)
            receipt.update(
                {
                    "arm": arm,
                    "model_id": arm if args.stage == "tiny" else f"{arm}-seed-{seed}",
                    "data": str(data),
                    "data_sha256": sha256(data),
                    "elapsed_seconds": time.perf_counter() - run_started,
                }
            )
            outputs.append(receipt)
            print(
                f"completed {receipt['model_id']} "
                f"loss={receipt['initial_loss']:.4f}->{receipt['final_loss']:.4f}",
                flush=True,
            )
        fcntl.flock(lock_file, fcntl.LOCK_UN)
    return outputs, time.perf_counter() - started


def main() -> int:
    args = parse_args()

    config = json.loads((ROOT / "configs/needle2-successor-v1.json").read_text())
    patch = ROOT / config["source"]["seed_patch"]
    if sha256(patch) != config["source"]["seed_patch_sha256"]:
        raise ValueError("Needle seed patch hash mismatch")
    verify_source(args.source_root, patch, config["source"]["revision"])
    if sha256(args.checkpoint) != config["base"]["checkpoint_sha256"]:
        raise ValueError("Needle checkpoint hash mismatch")
    if args.stage == "full":
        if not args.tiny_gate or not args.tiny_gate.is_file():
            raise ValueError("full training requires --tiny-gate")
        tiny_gate = json.loads(args.tiny_gate.read_text())
        if tiny_gate.get("passed") is not True:
            raise ValueError("tiny-overfit gate did not pass")

    sys.path.insert(0, str(args.source_root))
    import jax
    from needle.model.finetune import finetune_local

    recipe = config["tiny_overfit" if args.stage == "tiny" else "training"]
    plan = training_plan(config, args.stage)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    outputs, elapsed_seconds = run_training(args, recipe, plan, finetune_local)

    payload = {
        "schema_version": "posttrainllm.needle-training.v1",
        "stage": args.stage,
        "backend": jax.default_backend(),
        "devices": [str(device) for device in jax.devices()],
        "source_revision": config["source"]["revision"],
        "source_patch_sha256": sha256(patch),
        "checkpoint_sha256": sha256(args.checkpoint),
        "plan": [{"arm": arm, "seed": seed} for arm, seed in plan],
        "elapsed_seconds": elapsed_seconds,
        "runs": outputs,
    }
    output = args.run_dir / f"{args.stage}-training.json"
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
