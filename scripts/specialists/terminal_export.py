"""Export terminal weights for existing GPT WASM/WebGPU inference kernels.

The bundle carries Python logit probes and source identities. It is an inference
artifact, not a browser training checkpoint. Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib

import numpy as np
import torch

from common import file_hash, write_json
from terminal_codec import Screen, event_tokens, snapshot
from terminal_model import load


def weights(model):
    """collect_params() order; PyTorch [out,in] linears become [in,out]."""
    state = model.state_dict()
    arrays = [
        state[name]
        for name in ("embedding.weight", "position.weight", "norm.weight", "norm.bias")
    ]
    for i in range(model.config.n_layers):
        prefix = f"transformer.layers.{i}."

        def get(name):
            return state[prefix + name]

        qkv = get("self_attn.in_proj_weight").chunk(3)
        biases = get("self_attn.in_proj_bias").chunk(3)
        arrays += [get("norm1.weight"), get("norm1.bias")]
        for weight, bias in zip(qkv, biases):
            arrays += [weight.T, bias]
        arrays += [
            get("self_attn.out_proj.weight").T,
            get("self_attn.out_proj.bias"),
            get("norm2.weight"),
            get("norm2.bias"),
            get("linear1.weight").T,
            get("linear1.bias"),
            get("linear2.weight").T,
            get("linear2.bias"),
        ]
    return [value.detach().cpu().contiguous().numpy().astype("<f4") for value in arrays]


def parity_probes(model):
    probes = [
        snapshot(Screen.custom("$ ", 1, 8)) + event_tokens({"keys": [97]}),
        snapshot(Screen.custom("lab$ ", 2, 12)) + event_tokens({"wait_ms": 100}),
        [320, 321, 2, 12, 256, 0, 97, 98, 323, 0, 2, 1, 322, 324, 13, 325],
    ]
    probes = [tokens for tokens in probes if len(tokens) < model.config.context_length]
    if len(probes) != 3:
        raise ValueError("portable terminal context is too short for parity probes")
    with torch.inference_mode():
        expected = [model(torch.tensor([tokens]))[0, -1].tolist() for tokens in probes]
    return [
        {"tokens": tokens, "logits": logits} for tokens, logits in zip(probes, expected)
    ]


def validate_envelope(cfg, arrays):
    if (
        cfg.d_model > 256
        or cfg.n_heads > 16
        or cfg.n_layers > 8
        or cfg.context_length > 2048
        or cfg.d_mlp > 1024
        or cfg.dropout != 0
    ):
        raise ValueError("terminal artifact exceeds the portable inference envelope")
    count = sum(value.size for value in arrays)
    attention = cfg.n_heads * cfg.context_length**2
    activations = cfg.n_layers * (
        attention + cfg.context_length * (12 * cfg.d_model + 2 * cfg.d_mlp)
    )
    estimate = 4 * (activations + cfg.context_length * 333 + 5 * count)
    if count > 5_000_000 or attention * 4 > 128 * 1024**2 or estimate > 256 * 1024**2:
        raise ValueError(
            "terminal artifact exceeds the 256 MiB portable estimated tensor allocation envelope"
        )


def export(path, out, dtype="f32"):
    if dtype not in ("f32", "f16"):
        raise ValueError("terminal export dtype must be f32 or f16")
    model = load(path)
    cfg = model.config
    arrays = weights(model)
    validate_envelope(cfg, arrays)
    flat = np.concatenate([value.reshape(-1) for value in arrays])
    packed = flat.astype("<f4" if dtype == "f32" else "<f2").tobytes()
    if not np.isfinite(
        np.frombuffer(packed, dtype="<f4" if dtype == "f32" else "<f2")
    ).all():
        raise ValueError("compression produced nonfinite weights")
    artifact = {
        "schema": "posttrainllm-terminal-browser-v1",
        "codec": "posttrainllm-terminal-v1",
        "config": dataclasses.asdict(cfg),
        "dtype": dtype,
        "weights_base64": base64.b64encode(packed).decode("ascii"),
        "weights_sha256": hashlib.sha256(packed).hexdigest(),
        "parameter_sizes": [value.size for value in arrays],
        "source": {
            "weights_sha256": file_hash(path / "model.safetensors"),
            "config_sha256": file_hash(path / "config.json"),
        },
        "training_episode_identities": getattr(
            model, "training_episode_identities", None
        ),
        "parity": {
            "max_absolute_error": 0.002 if dtype == "f32" else 0.05,
            "require_argmax_agreement": True,
            "probes": parity_probes(model),
        },
        "quality": "unqualified; numerical probes do not establish terminal capability",
        "inference_only": True,
    }
    write_json(out, artifact)
    return {
        key: value
        for key, value in artifact.items()
        if key not in ("weights_base64", "parity")
    }
