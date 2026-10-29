"""Single-forward decision scoring, calibration and selective evaluation.

Independent implementation of the method described by Nish Tahir (2026-10-10):
https://nishtahir.com/build-your-own-decision-model/
Contract and commands: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from common import (
    Budget,
    ROOT,
    digest,
    file_hash,
    read_json,
    read_rows,
    softmax,
    write_json,
    write_rows,
)


def validate_item(item):
    options = item.get("options")
    if not isinstance(item.get("question"), str) or not item["question"].strip():
        raise ValueError("question must be nonempty")
    if not isinstance(options, dict) or not 2 <= len(options) <= 26:
        raise ValueError("options must contain 2–26 label/text pairs")
    if any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v
        for k, v in options.items()
    ):
        raise ValueError("option labels and text must be nonempty strings")
    if "answer" in item and item["answer"] not in options:
        raise ValueError("answer must name an option")
    return list(options)


def identity(item):
    validate_item(item)
    # Option permutation or relabeling cannot disguise a repeated question.
    return digest(
        {
            "question": item["question"].strip(),
            "choices": sorted(item["options"].values()),
        }
    )


def validate_splits(splits):
    seen = set()
    for name, rows in splits.items():
        local = [identity(row) for row in rows]
        if not rows or len(local) != len(set(local)) or seen.intersection(local):
            raise ValueError(f"duplicate examples or leakage in split {name}")
        seen.update(local)


def prompt(item, tokenizer):
    labels = validate_item(item)
    text = (
        item["question"]
        + "\n"
        + "\n".join(f"{key}. {item['options'][key]}" for key in labels)
    )
    text += "\nAnswer with exactly one option label.\nAnswer:"
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": text}],
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def option_ids(labels, tokenizer):
    encoded = [tokenizer.encode(label, add_special_tokens=False) for label in labels]
    if any(len(tokens) != 1 for tokens in encoded):
        raise ValueError(
            "every option label must encode as exactly one token; use A, B, C…"
        )
    ids = [tokens[0] for tokens in encoded]
    if len(ids) != len(set(ids)):
        raise ValueError("option token ids collide")
    return ids


class DecisionModel:
    def __init__(
        self,
        model,
        backend="torch",
        revision=None,
        offline=True,
        budget=None,
        adapter=None,
    ):
        self.budget = budget or Budget()
        self.backend = backend
        self.training_identities = set()
        if backend == "mlx":
            from mlx_lm import load

            # MLX supports a local directory. Resolve remote ids explicitly so
            # offline mode and immutable revisions have the same contract as HF.
            from huggingface_hub import snapshot_download

            path = str(model)
            if not Path(path).is_dir():
                path = snapshot_download(
                    path, revision=revision, local_files_only=offline, token=False
                )
            self.model, self.tokenizer = load(path)
            revision = Path(path).name
        else:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            torch = self.budget.torch()
            self.tokenizer = AutoTokenizer.from_pretrained(
                model, revision=revision, local_files_only=offline, token=False
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model,
                revision=revision,
                local_files_only=offline,
                token=False,
                torch_dtype=torch.float32,
                attn_implementation="eager",
            ).eval()
            revision = getattr(self.model.config, "_commit_hash", revision)
            path = str(model)
        local_files = {}
        if Path(path).is_dir():
            metadata_path = Path(path) / "specialist.json"
            if metadata_path.exists():
                self.training_identities.update(
                    read_json(metadata_path).get("train_identities", [])
                )
            for file in sorted(Path(path).iterdir()):
                if file.is_file() and file.suffix in (".json", ".safetensors"):
                    local_files[file.name] = file_hash(file)
        self.model_identity = digest(
            {"backend": backend, "files": local_files}
            if local_files
            else {"model": str(model), "revision": revision, "backend": backend}
        )
        if adapter is not None:
            if backend != "mlx":
                raise ValueError(
                    "adapter directory is for MLX; torch exports a merged model"
                )
            from mlx_lm.tuner.utils import load_adapters

            metadata = read_json(Path(adapter) / "specialist.json")
            if metadata["base_identity"] != self.model_identity:
                raise ValueError("adapter belongs to another base/tokenizer")
            adapter_hash = file_hash(Path(adapter) / "adapters.safetensors")
            if metadata["adapter_sha256"] != adapter_hash:
                raise ValueError("adapter checksum mismatch")
            config_hash = file_hash(Path(adapter) / "adapter_config.json")
            if metadata.get("adapter_config_sha256") != config_hash:
                raise ValueError("adapter configuration checksum mismatch")
            load_adapters(self.model, adapter)
            self.training_identities.update(metadata.get("train_identities", []))
            self.model_identity = digest(
                {
                    "base": self.model_identity,
                    "adapter": adapter_hash,
                    "config": config_hash,
                }
            )

    def score(self, item):
        self.budget.check()
        labels = validate_item(item)
        ids = option_ids(labels, self.tokenizer)
        tokens = self.tokenizer.encode(
            prompt(item, self.tokenizer), add_special_tokens=False
        )
        if not tokens or len(tokens) > 4096:
            raise ValueError(
                "decision prompt must contain 1–4096 tokens; no silent truncation"
            )
        if self.backend == "mlx":
            import mlx.core as mx

            logits = self.model(mx.array([tokens]))[0, -1, ids]
            mx.eval(logits)
            values = np.array(logits.astype(mx.float32)).tolist()
        else:
            import torch

            with torch.no_grad():
                values = (
                    self.model(torch.tensor([tokens]))
                    .logits[0, -1, ids]
                    .float()
                    .tolist()
                )
        return {
            "id": item.get("id", identity(item)),
            "identity": identity(item),
            "labels": labels,
            "logits": values,
            "model_identity": self.model_identity,
            "answer": item.get("answer"),
            "prompt_tokens": len(tokens),
            "seen_in_training": identity(item) in self.training_identities,
        }


def prediction(record, calibration=None, threshold=0.0):
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0,1]")
    if calibration and calibration["model_identity"] != record["model_identity"]:
        raise ValueError("calibration belongs to another model or adapter")
    if len(record["labels"]) != len(record["logits"]) or len(
        set(record["labels"])
    ) != len(record["labels"]):
        raise ValueError("labels/logits mismatch")
    temperature = calibration["temperature"] if calibration else 1.0
    probabilities = softmax(record["logits"], temperature)
    index = int(probabilities.argmax())
    return {
        "label": record["labels"][index] if probabilities[index] >= threshold else None,
        "probabilities": dict(zip(record["labels"], probabilities.tolist())),
        "calibration": "temperature-fitted; domain validation required"
        if calibration
        else "uncalibrated",
        "temperature": temperature,
    }


def validate_records(records):
    if not records or len({r["id"] for r in records}) != len(records):
        raise ValueError("need nonempty uniquely identified scores")
    if len({r["model_identity"] for r in records}) != 1:
        raise ValueError("scores mix models")
    for row in records:
        if row.get("seen_in_training"):
            raise ValueError(
                "training examples cannot calibrate or evaluate the adapted model"
            )
        if len(row["labels"]) != len(row["logits"]) or len(set(row["labels"])) != len(
            row["labels"]
        ):
            raise ValueError("labels/logits mismatch")
        if row["answer"] not in row["labels"]:
            raise ValueError("each calibration/eval row needs a gold label")
        softmax(row["logits"])


def nll(records, temperature):
    return float(
        np.mean(
            [
                -math.log(
                    max(
                        softmax(r["logits"], temperature)[
                            r["labels"].index(r["answer"])
                        ],
                        1e-300,
                    )
                )
                for r in records
            ]
        )
    )


def calibrate(records, excluded=()):
    validate_records(records)
    identities = [r["identity"] for r in records]
    forbidden = {r["identity"] for r in excluded}
    if len(set(identities)) != len(identities) or forbidden.intersection(identities):
        raise ValueError(
            "calibration overlaps training/test/regression or repeats examples"
        )
    # Bounded golden-section search in log temperature, plus identity fallback.
    low, high = math.log(0.05), math.log(20.0)
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(80):
        a, b = high - ratio * (high - low), low + ratio * (high - low)
        if nll(records, math.exp(a)) <= nll(records, math.exp(b)):
            high = b
        else:
            low = a
    temperature = min([1.0, math.exp((low + high) / 2)], key=lambda t: nll(records, t))
    return {
        "schema": "decision-temperature-v1",
        "model_identity": records[0]["model_identity"],
        "temperature": temperature,
        "calibration_identities": identities,
        "excluded_identities": sorted(forbidden),
        "scores_sha256": digest(records),
        "nll_before": nll(records, 1.0),
        "nll_after": nll(records, temperature),
    }


def metrics(records, calibration=None, threshold=0.0):
    validate_records(records)
    if calibration and set(calibration["calibration_identities"]).intersection(
        r["identity"] for r in records
    ):
        raise ValueError("test examples overlap temperature calibration")
    confidences, correct, briers, accepted = [], [], [], []
    for row in records:
        result = prediction(row, calibration, threshold)
        p = np.array(list(result["probabilities"].values()))
        target = row["labels"].index(row["answer"])
        gold = np.eye(len(p))[target]
        confidences.append(float(p.max()))
        correct.append(int(p.argmax() == target))
        briers.append(float(((p - gold) ** 2).sum()))
        accepted.append(result["label"] is not None)
    confidence, right, accept = map(np.array, (confidences, correct, accepted))
    ece = 0.0
    for index in range(10):
        mask = (confidence > index / 10) & (confidence <= (index + 1) / 10)
        if mask.any():
            ece += float(
                mask.mean() * abs(confidence[mask].mean() - right[mask].mean())
            )
    return {
        "count": len(records),
        "accuracy": float(right.mean()),
        "nll": nll(records, calibration["temperature"] if calibration else 1.0),
        "brier": float(np.mean(briers)),
        "ece_10_bins": ece,
        "coverage": float(accept.mean()),
        "selective_accuracy": float(right[accept].mean()) if accept.any() else None,
    }


def train(model_name, rows, out, steps, budget, revision=None, offline=True):
    """Option-normalized SFT with the existing readable LoRA numerical reference."""
    if not 1 <= steps <= 10000:
        raise ValueError("steps must be in [1,10000]")
    validate_splits({"train": rows})
    if Path(out).exists():
        raise FileExistsError(out)
    backend = DecisionModel(
        model_name, revision=revision, offline=offline, budget=budget
    )
    sys.path.insert(0, str(ROOT / "python_ref"))
    from lora import inject_lora, mark_only_lora_trainable, lora_parameters

    torch = budget.torch()
    torch.manual_seed(7)
    inject_lora(backend.model, ("q_proj", "v_proj"), rank=4, alpha=8)
    mark_only_lora_trainable(backend.model)
    backend.model.train()
    optimizer = torch.optim.AdamW(lora_parameters(backend.model), lr=1e-3)
    losses = []
    for step in range(steps):
        budget.check()
        row = rows[step % len(rows)]
        ids = option_ids(validate_item(row), backend.tokenizer)
        tokens = backend.tokenizer.encode(
            prompt(row, backend.tokenizer), add_special_tokens=False
        )
        if len(tokens) > 4096:
            raise ValueError("training prompt exceeds 4096 tokens")
        logits = backend.model(torch.tensor([tokens])).logits[:, -1, ids]
        loss = torch.nn.functional.cross_entropy(
            logits, torch.tensor([list(row["options"]).index(row["answer"])])
        )
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(lora_parameters(backend.model), 1.0)
        optimizer.step()
        losses.append(float(loss.detach()))
        budget.progress(step + 1, steps, losses[-1])
    # Merge the adapter for a standard HF-loadable portable artifact. No custom
    # pickle loader or dependence on the original base directory is needed.
    for parent in backend.model.modules():
        for name, layer in list(parent.named_children()):
            if hasattr(layer, "lora_A"):
                with torch.no_grad():
                    layer.base.weight.add_(
                        (layer.lora_A @ layer.lora_B).T * layer.scale
                    )
                setattr(parent, name, layer.base)
    backend.model.save_pretrained(out, safe_serialization=True)
    backend.tokenizer.save_pretrained(out)
    write_json(
        Path(out) / "specialist.json",
        {
            "kind": "decision",
            "base_identity": backend.model_identity,
            "train_identities": [identity(r) for r in rows],
            "steps": steps,
            "losses": losses,
            "quality": "unqualified",
            **budget.measurements(),
        },
    )


def train_mlx(model_name, rows, out, steps, budget, revision=None, offline=True):
    """QLoRA on the existing Mac-local quantized base; standard MLX adapters."""
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten
    from mlx_lm.tuner.utils import linear_to_lora_layers

    if not 1 <= steps <= 10000 or Path(out).exists():
        raise ValueError("need 1–10000 steps and a new output directory")
    validate_splits({"train": rows})
    backend = DecisionModel(model_name, "mlx", revision, offline, budget)
    backend.model.freeze()
    configuration = {
        "num_layers": min(4, len(backend.model.layers)),
        "fine_tune_type": "lora",
        "lora_parameters": {
            "rank": 4,
            "scale": 2.0,
            "dropout": 0.0,
            "keys": ["self_attn.q_proj", "self_attn.v_proj"],
        },
    }
    linear_to_lora_layers(
        backend.model, configuration["num_layers"], configuration["lora_parameters"]
    )
    if not tree_flatten(backend.model.trainable_parameters()):
        raise ValueError("no LoRA parameters selected")
    optimizer = optim.Adam(learning_rate=1e-4)
    backend.model.train()
    mx.random.seed(7)

    def loss_function(model, tokens, ids, target):
        logits = model(tokens)[:, -1, ids].astype(mx.float32)
        return nn.losses.cross_entropy(logits, target).mean()

    loss_and_grad = nn.value_and_grad(backend.model, loss_function)
    losses = []
    for step in range(steps):
        budget.check()
        row = rows[step % len(rows)]
        labels = validate_item(row)
        ids = option_ids(labels, backend.tokenizer)
        tokens = backend.tokenizer.encode(
            prompt(row, backend.tokenizer), add_special_tokens=False
        )
        if not 1 <= len(tokens) <= 4096:
            raise ValueError("training prompt exceeds local token budget")
        loss, gradients = loss_and_grad(
            backend.model,
            mx.array([tokens]),
            ids,
            mx.array([labels.index(row["answer"])]),
        )
        optimizer.update(backend.model, gradients)
        mx.eval(backend.model.trainable_parameters(), optimizer.state, loss)
        if not math.isfinite(loss.item()):
            raise ValueError("nonfinite MLX training loss")
        losses.append(loss.item())
        budget.progress(step + 1, steps, losses[-1])
    out = Path(out)
    out.mkdir(parents=True)
    mx.save_safetensors(
        str(out / "adapters.safetensors"),
        dict(tree_flatten(backend.model.trainable_parameters())),
    )
    write_json(out / "adapter_config.json", configuration)
    write_json(
        out / "specialist.json",
        {
            "kind": "decision-mlx-adapter",
            "base_identity": backend.model_identity,
            "base_model": str(model_name),
            "revision": revision,
            "adapter_sha256": file_hash(out / "adapters.safetensors"),
            "adapter_config_sha256": file_hash(out / "adapter_config.json"),
            "train_identities": [identity(row) for row in rows],
            "steps": steps,
            "losses": losses,
            "quality": "unqualified",
            **budget.measurements(),
            "gpu_memory_bytes": mx.get_peak_memory(),
        },
    )


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("score", "train"):
        child = sub.add_parser(command)
        child.add_argument("--model", required=True)
        child.add_argument("--data", required=True)
        child.add_argument("--out", required=True)
        child.add_argument("--revision")
        child.add_argument("--download", action="store_true")
        child.add_argument("--seconds", type=float, default=60)
        child.add_argument("--backend", choices=("torch", "mlx"), default="torch")
        if command == "score":
            child.add_argument("--adapter")
        else:
            child.add_argument("--steps", type=int, default=1)
    child = sub.add_parser("calibrate")
    child.add_argument("--scores", required=True)
    child.add_argument(
        "--exclude", nargs="+", required=True, help="training and test score files"
    )
    child.add_argument("--out", required=True)
    child = sub.add_parser("predict")
    child.add_argument("--scores", required=True)
    child.add_argument("--calibration")
    child.add_argument("--threshold", type=float, default=0)
    child.add_argument("--out", required=True)
    child = sub.add_parser("eval")
    child.add_argument("--scores", required=True)
    child.add_argument("--ceiling", required=True)
    child.add_argument("--calibration")
    child.add_argument("--baseline")
    child.add_argument("--threshold", type=float, default=0)
    child.add_argument("--out", required=True)
    child = sub.add_parser("ceiling")
    child.add_argument("--data", required=True)
    child.add_argument("--out", required=True)
    child = sub.add_parser("prepare")
    child.add_argument("--data", required=True)
    child.add_argument("--out", required=True)
    child = sub.add_parser("export-native")
    child.add_argument("--base", required=True)
    child.add_argument("--adapter", required=True)
    child.add_argument("--out", required=True)
    child = sub.add_parser("score-native")
    child.add_argument("--binary", required=True)
    child.add_argument("--base", required=True)
    child.add_argument("--source-revision", required=True)
    child.add_argument("--adapter")
    child.add_argument("--data", required=True)
    child.add_argument("--out", required=True)
    child.add_argument("--seconds", type=float, default=60)
    child = sub.add_parser("export-browser")
    child.add_argument("--base", required=True)
    child.add_argument("--adapter")
    child.add_argument("--data", required=True)
    child.add_argument("--out", required=True)
    child.add_argument("--max-tokens", type=int, default=256)
    child.add_argument("--seconds", type=float, default=60)
    return parser


def run_model(args):
    budget = Budget(args.seconds)
    rows = read_rows(args.data)
    if args.command == "train":
        trainer = train_mlx if args.backend == "mlx" else train
        trainer(
            args.model,
            rows,
            args.out,
            args.steps,
            budget,
            args.revision,
            not args.download,
        )
    else:
        model = DecisionModel(
            args.model,
            args.backend,
            args.revision,
            not args.download,
            budget,
            args.adapter,
        )
        write_rows(args.out, [model.score(row) for row in rows])
        print(json.dumps(budget.measurements()))


def run_native(args):
    if args.command == "export-native":
        from decision_native import export

        print(json.dumps(export(args.base, args.adapter, args.out)))
        return
    from decision_native_score import NativeDecisionModel

    budget = Budget(args.seconds)
    rows = read_rows(args.data)
    if Path(args.out).exists():
        raise FileExistsError(args.out)
    model = NativeDecisionModel(
        args.binary, args.base, args.source_revision, args.adapter, budget
    )
    model.preflight(rows)
    scores = [model.score(row) for row in rows]
    model.finish()
    write_rows(args.out, scores)
    print(json.dumps(budget.measurements()))


def main():
    args = argument_parser().parse_args()
    if args.command in ("score-native", "export-native"):
        run_native(args)
    elif args.command == "export-browser":
        from decision_browser import export

        rows = read_rows(args.data)
        if len(rows) != 1:
            raise ValueError("browser export requires exactly one example row")
        print(
            json.dumps(
                export(
                    args.base,
                    args.adapter,
                    rows[0],
                    args.out,
                    args.max_tokens,
                    args.seconds,
                )
            )
        )
    elif args.command in ("score", "train"):
        run_model(args)
    elif args.command == "calibrate":
        excluded = [r for path in args.exclude for r in read_rows(path)]
        write_json(args.out, calibrate(read_rows(args.scores), excluded))
    elif args.command == "predict":
        calibration = read_json(args.calibration) if args.calibration else None
        write_rows(
            args.out,
            [
                {"id": row["id"], **prediction(row, calibration, args.threshold)}
                for row in read_rows(args.scores)
            ],
        )
    else:
        from decision_eval import ceiling, evaluate, prepare

        if args.command == "prepare":
            prepare(read_rows(args.data), args.out)
        elif args.command == "ceiling":
            ceiling(read_rows(args.data), args.out)
        else:
            write_json(
                args.out,
                evaluate(
                    read_rows(args.scores),
                    read_json(args.ceiling),
                    read_json(args.calibration) if args.calibration else None,
                    read_rows(args.baseline) if args.baseline else None,
                    args.threshold,
                ),
            )


if __name__ == "__main__":
    main()
