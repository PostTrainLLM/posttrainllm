"""Native TGLA conversion preserves named subset projections and MLX scaling."""

import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("safetensors")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from common import digest, file_hash
from decision_native import base_files, export, matrices


def fixture(tmp_path):
    from safetensors.numpy import save_file

    base, adapter = tmp_path / "base", tmp_path / "adapter"
    base.mkdir()
    adapter.mkdir()
    cfg = {
        "architectures": ["Qwen3ForCausalLM"],
        "num_hidden_layers": 3,
        "hidden_size": 8,
        "num_attention_heads": 2,
        "num_key_value_heads": 1,
        "head_dim": 4,
        "max_position_embeddings": 128,
        "intermediate_size": 16,
    }
    (base / "config.json").write_text(json.dumps(cfg))
    (base / "model.safetensors").write_bytes(b"identity-only-fixture")
    config = {
        "num_layers": 1,
        "fine_tune_type": "lora",
        "lora_parameters": {
            "rank": 2,
            "scale": 3.0,
            "keys": ["self_attn.q_proj", "self_attn.v_proj"],
        },
    }
    (adapter / "adapter_config.json").write_text(json.dumps(config))
    tensors = {
        "model.layers.2.self_attn.q_proj.lora_a": np.ones((8, 2), dtype="float32"),
        "model.layers.2.self_attn.q_proj.lora_b": np.full(
            (2, 8), 0.25, dtype="float32"
        ),
        "model.layers.2.self_attn.v_proj.lora_a": np.ones((8, 2), dtype="float32"),
        "model.layers.2.self_attn.v_proj.lora_b": np.full((2, 4), 0.5, dtype="float32"),
    }
    save_file(tensors, adapter / "adapters.safetensors")
    metadata = {
        "base_identity": digest({"backend": "mlx", "files": base_files(base)}),
        "adapter_sha256": file_hash(adapter / "adapters.safetensors"),
        "adapter_config_sha256": file_hash(adapter / "adapter_config.json"),
    }
    (adapter / "specialist.json").write_text(json.dumps(metadata))
    return base, adapter


def test_native_export_preserves_subset_scaling_and_bytes(tmp_path):
    base, adapter = fixture(tmp_path)
    out = tmp_path / "converted.lora"
    receipt = export(base, adapter, out)
    raw = out.read_bytes()
    assert raw[:4] == b"TGLA"
    version, length = struct.unpack("<II", raw[4:12])
    assert version == 2
    header = json.loads(raw[12 : 12 + length])
    assert header["alpha"] / header["rank"] == 3.0
    assert [e["name"] for e in header["entries"]] == [
        "layers.2.self_attn.q_proj",
        "layers.2.self_attn.v_proj",
    ]
    np.testing.assert_array_equal(
        np.frombuffer(raw[12 + length :], dtype="<f4")[:16], np.ones(16)
    )
    assert receipt["native_adapter_sha256"] == file_hash(out)
    assert receipt["base_files"] == base_files(base)
    with pytest.raises(FileExistsError):
        export(base, adapter, out)


def test_native_export_rejects_changed_base_or_adapter(tmp_path):
    base, adapter = fixture(tmp_path)
    (base / "model.safetensors").write_bytes(b"changed-base")
    with pytest.raises(ValueError, match="another base"):
        export(base, adapter, tmp_path / "bad.lora")

    (base / "model.safetensors").write_bytes(b"identity-only-fixture")
    with (adapter / "adapters.safetensors").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        export(base, adapter, tmp_path / "bad.lora")


def test_native_float32_conversion_rejects_overflow(tmp_path):
    from safetensors.numpy import load_file

    base, adapter = fixture(tmp_path)
    tensors = load_file(adapter / "adapters.safetensors")
    key = "model.layers.2.self_attn.q_proj.lora_a"
    tensors[key] = np.full((8, 2), 1e100, dtype="float64")
    with pytest.raises(ValueError, match="overflow"):
        matrices(
            json.loads((base / "config.json").read_text()),
            json.loads((adapter / "adapter_config.json").read_text()),
            tensors,
        )
