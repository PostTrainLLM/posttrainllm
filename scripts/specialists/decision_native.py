"""Convert identity-checked MLX decision adapters to the native TGLA format.

Only ordinary LoRA projections are admitted. Keep the matching base directory;
TGLA architecture checks alone do not identify its weights or tokenizer.
Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path

import numpy as np

from common import digest, file_hash, read_json, write_json


def base_files(base):
    return {
        file.name: file_hash(file)
        for file in sorted(base.iterdir())
        if file.is_file() and file.suffix in (".json", ".safetensors")
    }


def validate_config(config, rank, scale, count, layers):
    if (
        config.get("fine_tune_type") != "lora"
        or not isinstance(rank, int)
        or not 0 < rank <= 4096
        or not math.isfinite(scale)
        or not isinstance(count, int)
        or not 0 < count <= layers
    ):
        raise ValueError("unsupported native LoRA configuration")
    if len(set(config["lora_parameters"]["keys"])) != len(
        config["lora_parameters"]["keys"]
    ):
        raise ValueError("duplicate native adapter projection keys")


def matrices(base_config, config, tensors):
    params = config["lora_parameters"]
    rank, scale = params["rank"], params["scale"]
    layers, hidden = base_config["num_hidden_layers"], base_config["hidden_size"]
    count = config["num_layers"]
    validate_config(config, rank, scale, count, layers)
    entries, arrays, used = [], [], set()
    for layer in range(layers - count, layers):
        for key in params["keys"]:
            if key not in ("self_attn.q_proj", "self_attn.v_proj"):
                raise ValueError("native decision export supports q/v LoRA only")
            name = f"model.layers.{layer}.{key}"
            a_key, b_key = name + ".lora_a", name + ".lora_b"
            a, b = tensors[a_key], tensors[b_key]
            if a.dtype.kind != "f" or b.dtype.kind != "f":
                raise ValueError("native adapter weights must be floating point")
            head_dim = base_config.get(
                "head_dim", hidden // base_config["num_attention_heads"]
            )
            heads = (
                base_config["num_attention_heads"]
                if key.endswith("q_proj")
                else base_config["num_key_value_heads"]
            )
            if a.shape != (hidden, rank) or b.shape != (rank, head_dim * heads):
                raise ValueError(f"invalid native adapter shape: {name}")
            if not np.isfinite(a).all() or not np.isfinite(b).all():
                raise ValueError("nonfinite adapter weights")
            entries.append(
                {
                    "name": name.removeprefix("model."),
                    "loraAShape": list(a.shape),
                    "loraBShape": list(b.shape),
                }
            )
            with np.errstate(over="ignore", invalid="ignore"):
                converted = [a.astype("<f4"), b.astype("<f4")]
            if any(not np.isfinite(value).all() for value in converted):
                raise ValueError("native float32 conversion overflow")
            arrays.extend(converted)
            used.update((a_key, b_key))
    if not entries or used != set(tensors):
        raise ValueError("unexpected or duplicate native adapter projections")
    return rank, scale * rank, entries, arrays


def export(base, adapter, out):
    from safetensors.numpy import load_file

    base, adapter, out = Path(base), Path(adapter), Path(out)
    metadata = read_json(adapter / "specialist.json")
    files = base_files(base)
    if metadata["base_identity"] != digest({"backend": "mlx", "files": files}):
        raise ValueError("adapter belongs to another base/tokenizer")
    for name, key in (
        ("adapters.safetensors", "adapter_sha256"),
        ("adapter_config.json", "adapter_config_sha256"),
    ):
        if file_hash(adapter / name) != metadata[key]:
            raise ValueError("adapter checksum mismatch")
    cfg = read_json(base / "config.json")
    if not re.fullmatch(r"(?:Qwen3|Llama|Mistral)ForCausalLM", cfg["architectures"][0]):
        raise ValueError("unsupported native architecture")
    rank, alpha, entries, arrays = matrices(
        cfg,
        read_json(adapter / "adapter_config.json"),
        load_file(adapter / "adapters.safetensors"),
    )
    header = {
        "rank": rank,
        "alpha": alpha,
        "targetSuffixes": ["q_proj", "v_proj"],
        "baseLayers": cfg["num_hidden_layers"],
        "baseDModel": cfg["hidden_size"],
        "baseCtx": cfg["max_position_embeddings"],
        "baseHeads": cfg["num_attention_heads"],
        "baseDMlp": cfg["intermediate_size"],
        "entries": entries,
    }
    encoded = json.dumps(header, allow_nan=False, separators=(",", ":")).encode()
    provenance = out.with_suffix(out.suffix + ".json")
    if out.exists() or provenance.exists():
        raise FileExistsError("native export refuses to overwrite evidence")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as stream:
        stream.write(b"TGLA" + struct.pack("<II", 2, len(encoded)) + encoded)
        for array in arrays:
            stream.write(array.tobytes())
    receipt = {
        "schema": "decision-native-adapter-v1",
        "base_files": files,
        "base_identity": metadata["base_identity"],
        "source_adapter_sha256": metadata["adapter_sha256"],
        "native_adapter_sha256": file_hash(out),
        "entries": len(entries),
        "quality": "unqualified; recalibrate after runtime conversion",
    }
    write_json(provenance, receipt)
    return receipt
