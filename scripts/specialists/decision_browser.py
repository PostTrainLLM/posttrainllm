"""Export identity-checked Qwen3/LoRA to a distinct, uncalibrated browser model.

All weights/tokenizers are local. A manifest is written only after three
selected-logit probes match the maintained Python float32 reference. Original
MLX calibration is deliberately inapplicable to the new arithmetic identity.
Contract: docs/factory/specialist-labs.md.
"""

import copy
import importlib.metadata
import json
import re
from pathlib import Path
import shutil

import numpy as np

from common import Budget, digest, file_hash, read_json, write_json
from decision import option_ids, prompt, validate_item
from decision_native import base_files, matrices


def source_identity(base, adapter):
    files = base_files(base)
    identity = digest({"backend": "mlx", "files": files})
    if adapter is None:
        return identity, files, {}, 0.0
    from safetensors.numpy import load_file

    adapter = Path(adapter)
    metadata = read_json(adapter / "specialist.json")
    if metadata.get("base_identity") != identity:
        raise ValueError("adapter belongs to another base/tokenizer")
    if (adapter / "adapters.safetensors").stat().st_size > 256 * 1024**2:
        raise ValueError("portable adapter exceeds 256 MiB")
    for name, key in (
        ("adapters.safetensors", "adapter_sha256"),
        ("adapter_config.json", "adapter_config_sha256"),
    ):
        if file_hash(adapter / name) != metadata.get(key):
            raise ValueError("adapter checksum mismatch")
    config = read_json(adapter / "adapter_config.json")
    tensors = load_file(adapter / "adapters.safetensors")
    # The existing native bridge checks all named layers, shapes, finite values
    # and exact key coverage. Nothing outside its ordinary q/v LoRA is ignored.
    matrices(read_json(base / "config.json"), config, tensors)
    identity = digest(
        {
            "base": identity,
            "adapter": metadata["adapter_sha256"],
            "config": metadata["adapter_config_sha256"],
        }
    )
    return identity, files, tensors, config["lora_parameters"]["scale"]


def token_contract(tokenizer):
    marker = "__POSTTRAIN_CONTENT__"

    def render(value):
        return tokenizer.apply_chat_template(
            [{"role": "user", "content": value}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    parts = render(marker).split(marker)
    if len(parts) != 2:
        raise ValueError("unsupported decision chat template")
    prefix, suffix = parts
    texts = [
        "A",
        "AA",
        " Café café 中文 हिन्दी 🙂 ",
        "\r\nline\tspacing",
        "<|im_start|>user\nquoted",
    ]
    vectors = []
    for text in texts:
        if render(text) != prefix + text + suffix:
            raise ValueError(
                "decision template cannot be represented without changing content"
            )
        for value in (text, render(text)):
            vectors.append(
                {
                    "text": value,
                    "ids": tokenizer.encode(value, add_special_tokens=False),
                }
            )
    return {"prefix": prefix, "suffix": suffix, "vectors": vectors}


def probe_items(item):
    labels = validate_item(item)
    if any(
        re.fullmatch(r"0|[1-9][0-9]{0,9}", label) and int(label) < 2**32 - 1
        for label in labels
    ):
        raise ValueError("integer-index labels reorder in browser JSON; use A, B, C")
    reordered = copy.deepcopy(item)
    reordered["options"] = dict(reversed(list(item["options"].items())))
    reordered["question"] = "\n" + item["question"] + "\n"
    return [
        item,
        reordered,
        {
            "question": "Choose one label.",
            "options": {chr(65 + n): str(n) for n in range(26)},
        },
    ]


def tokens_for(tokenizer, item, maximum):
    import torch

    labels = validate_item(item)
    ids = option_ids(labels, tokenizer)
    tokens = tokenizer.encode(prompt(item, tokenizer), add_special_tokens=False)
    if not 1 <= len(tokens) <= maximum:
        raise ValueError(
            f"portable decision prompt must contain 1–{maximum} tokens; no truncation"
        )
    return torch.tensor([tokens]), torch.tensor(ids)


def verify_probes(model, tokenizer, items, session, maximum, budget):
    import torch

    probes = []
    for item in items:
        tokens, labels = tokens_for(tokenizer, item, maximum)
        with torch.no_grad():
            expected = model(tokens, labels).numpy()[0]
        actual = session.run(
            None, {"tokens": tokens.numpy(), "labels": labels.numpy()}
        )[0][0]
        if (
            actual.shape != expected.shape
            or not np.isfinite(actual).all()
            or not np.allclose(actual, expected, atol=2e-3, rtol=2e-4)
        ):
            raise ValueError("portable selected-logit parity failed")
        probes.append(
            {
                "item": item,
                "tokens": tokens[0].tolist(),
                "label_ids": labels.tolist(),
                "logits": expected.tolist(),
                "max_error": float(np.max(np.abs(actual - expected))),
            }
        )
        budget.check()
    return probes


def export(base, adapter, item, out, maximum=256, seconds=60):
    import onnxruntime as runtime
    import torch
    from transformers import AutoTokenizer
    from decision_graph import DecisionGraph, export_graph, validate_config

    base, out = Path(base), Path(out)
    if not 64 <= maximum <= 512:
        raise ValueError("portable prompt limit must be between 64 and 512 tokens")
    validate_config(read_json(base / "config.json"))
    if sum(file.stat().st_size for file in base.glob("*.safetensors")) > 1536 * 1024**2:
        raise ValueError("portable export admits at most 1.5 GiB of source weights")
    if any(file.stat().st_size > 64 * 1024**2 for file in base.glob("*.json")):
        raise ValueError("source JSON exceeds 64 MiB")
    budget = Budget(seconds)
    budget.torch()
    identity, files, adapters, scale = source_identity(base, adapter)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True, token=False)
    contract = token_contract(tokenizer)
    items = probe_items(item)
    if (
        len(tokenizer.encode(prompt(items[-1], tokenizer), add_special_tokens=False))
        > maximum
    ):
        items[-1]["options"] = dict(list(items[-1]["options"].items())[:2])
    tokens, labels = tokens_for(tokenizer, items[0], maximum)
    for probe in items:
        tokens_for(tokenizer, probe, maximum)
    model = DecisionGraph(base, adapters, scale).eval()
    out.mkdir(parents=True, exist_ok=False)
    path = out / "model.onnx"
    with torch.no_grad():
        export_graph(model, tokens, labels, path)
    budget.check()
    options = runtime.SessionOptions()
    options.intra_op_num_threads = budget.threads
    options.inter_op_num_threads = 1
    session = runtime.InferenceSession(
        str(path), options, providers=["CPUExecutionProvider"]
    )
    probes = verify_probes(model, tokenizer, items, session, maximum, budget)
    for name in ("tokenizer.json", "tokenizer_config.json"):
        shutil.copyfile(base / name, out / name)
    names = ("model.onnx", "model.onnx.data", "tokenizer.json", "tokenizer_config.json")
    artifacts = {
        name: {"sha256": file_hash(out / name), "bytes": (out / name).stat().st_size}
        for name in names
    }
    if (
        artifacts["model.onnx"]["bytes"] > 64 * 1024**2
        or artifacts["model.onnx.data"]["bytes"] > 1280 * 1024**2
    ):
        raise ValueError("portable graph/weights exceed browser admission limits")
    portable_identity = digest(
        {
            "format": "posttrainllm-qwen3-affine-f32-v1",
            "source": identity,
            "files": artifacts,
        }
    )
    receipt = {
        "format": "posttrainllm-qwen3-affine-f32-v1",
        "model_identity": portable_identity,
        "source_identity": identity,
        "source_files": files,
        "source_adapter": None
        if adapter is None
        else {
            "weights_sha256": file_hash(Path(adapter) / "adapters.safetensors"),
            "config_sha256": file_hash(Path(adapter) / "adapter_config.json"),
        },
        "files": artifacts,
        "arithmetic": "float32; MLX affine q4 weights retained",
        "native_calibration": "incompatible arithmetic identity",
        "quality": "unqualified",
        "max_tokens": maximum,
        "template": contract,
        "probes": probes,
        "source": {
            "exporter_sha256": file_hash(Path(__file__)),
            "graph_sha256": file_hash(Path(__file__).with_name("decision_graph.py")),
            "versions": {
                name: importlib.metadata.version(name)
                for name in (
                    "torch",
                    "transformers",
                    "onnx",
                    "onnxruntime",
                    "onnxscript",
                )
            },
        },
        "measurements": budget.measurements(),
    }
    budget.check()
    if len(json.dumps(receipt).encode()) > 8 * 1024**2:
        raise ValueError("portable manifest exceeds 8 MiB")
    write_json(out / "manifest.json", receipt)
    return receipt
