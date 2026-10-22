"""Matched two-stage QLoRA pilot using the pinned upstream MLX trainer.

The first 20 of each candidate's 100 updates are a tiny repeated TRAIN-only
wiring gate. Continue from that adapter for 80 full-TRAIN updates only if the
two tiny targets are exact and validation loss falls. No TEST selection.
"""

import argparse
import json
import math
import resource
import time
from types import SimpleNamespace

import mlx.core as mx
import numpy as np
from mlx_lm import load, stream_generate
from mlx_lm.lora import CONFIG_DEFAULTS, train_model
from mlx_lm.sample_utils import make_sampler
from mlx_lm.tuner.datasets import load_dataset
from mlx_lm.tuner.trainer import TrainingCallback

from prepare import OUT, jsonl, write


class Receipt(TrainingCallback):
    def __init__(self, path):
        self.path = path
        self.started = time.monotonic()
        self.values = {"train": [], "validation": [], "complete": False}

    def on_train_loss_report(self, info):
        loss = float(info["train_loss"])
        if not math.isfinite(loss):
            raise RuntimeError("Non-finite training loss")
        self.values["train"].append({"iteration": info["iteration"], "loss": loss})
        self.flush()

    def on_val_loss_report(self, info):
        self.values["validation"].append(
            {"iteration": info["iteration"], "loss": float(info["val_loss"])}
        )
        self.flush()

    def flush(self):
        self.values.update(
            {
                "elapsed_seconds": time.monotonic() - self.started,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "mlx_peak_memory_bytes": mx.get_peak_memory(),
                "paid_usd": 0,
            }
        )
        write(self.path, self.values)
        if (
            self.values["elapsed_seconds"] > 900
            or self.values["peak_rss_bytes"] > 16 * 1024**3
        ):
            raise RuntimeError("Frozen per-stage time/memory bound exceeded")


def train(candidate, stage):
    admission = json.loads((OUT / "training-admission.json").read_text())
    contract = json.loads((OUT / "contract.json").read_text())
    assert admission["total_updates_per_candidate"] == contract["adapter"]["iterations"]
    assert json.loads((OUT / "baseline-result.json").read_text())["complete"]
    assert json.loads((OUT / "frontier-result.json").read_text())["valid"]
    receipt = Receipt(OUT / f"{candidate}-{stage}-training.json")
    if receipt.path.exists():
        raise SystemExit("Preserve the existing training receipt; no silent retry.")
    adapter = OUT / "adapters" / candidate
    data = OUT / candidate
    if stage == "tiny":
        tiny = OUT / candidate / "tiny"
        rows = [
            json.loads(line)
            for line in (data / "train.jsonl").read_text().splitlines()[:2]
        ]
        for split in ["train", "valid"]:
            jsonl(tiny / f"{split}.jsonl", rows * 2)
        data = tiny
    else:
        assert json.loads((OUT / f"{candidate}-tiny-gate.json").read_text())["passed"]
    mx.set_memory_limit(12 * 1024**3)
    mx.set_cache_limit(2 * 1024**3)
    np.random.seed(contract["seed"] % 2**32)
    config = {
        **CONFIG_DEFAULTS,
        "model": json.loads((OUT / "model-source.json").read_text())["local_path"],
        "data": str(data),
        "train": True,
        "seed": contract["seed"],
        "num_layers": 4,
        "batch_size": 1,
        "iters": 20 if stage == "tiny" else 80,
        "val_batches": -1 if stage == "tiny" else 4,
        "learning_rate": 0.0001,
        "steps_per_report": 1,
        "steps_per_eval": 20,
        "save_every": 20,
        "adapter_path": str(adapter),
        "max_seq_length": 384,
        "grad_checkpoint": True,
        "mask_prompt": True,
        "lora_parameters": {"rank": 4, "scale": 8, "dropout": 0.0},
    }
    if stage == "full":
        config["resume_adapter_file"] = str(adapter / "adapters.safetensors")
    write(OUT / f"{candidate}-{stage}-config.json", config)
    args = SimpleNamespace(**config)
    model, tokenizer = load(config["model"], trust_remote_code=False)
    train_set, valid_set, _ = load_dataset(args, tokenizer)
    train_model(args, model, train_set, valid_set, receipt)
    receipt.values["complete"] = True
    receipt.flush()
    if stage == "tiny":
        model.eval()
        checks = []
        for row in rows:
            prompt = tokenizer.apply_chat_template(
                row["messages"][:-1],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            text = "".join(
                r.text
                for r in stream_generate(
                    model,
                    tokenizer,
                    prompt,
                    max_tokens=24,
                    sampler=make_sampler(temp=0),
                )
            )
            checks.append(
                {
                    "output": text,
                    "expected": row["messages"][-1]["content"],
                    "correct": text.strip() == row["messages"][-1]["content"],
                }
            )
        losses = receipt.values["validation"]
        passed = (
            all(c["correct"] for c in checks) and losses[-1]["loss"] < losses[0]["loss"]
        )
        write(
            OUT / f"{candidate}-tiny-gate.json",
            {
                "passed": passed,
                "checks": checks,
                "losses": losses,
                "meaning": "TRAIN-only wiring; not held-out quality or a third candidate.",
            },
        )
        if not passed:
            raise SystemExit(
                "Tiny repeated-data gate failed; do not scale this candidate."
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", choices=["ordinary", "perturbation"])
    parser.add_argument("stage", choices=["tiny", "full"])
    args = parser.parse_args()
    train(args.candidate, args.stage)
