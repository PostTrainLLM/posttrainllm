"""Numerical portability and fail-closed identity checks, not model quality."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("onnxscript")
pytest.importorskip("onnxruntime")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from decision_browser import export, probe_items, source_identity
from decision_graph import validate_config


def tiny_source(folder):
    from safetensors.torch import save_file
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast, Qwen3Config

    folder.mkdir()
    config = Qwen3Config(
        hidden_size=64,
        intermediate_size=128,
        num_hidden_layers=1,
        num_attention_heads=1,
        num_key_value_heads=1,
        head_dim=64,
        vocab_size=64,
        max_position_embeddings=512,
        tie_word_embeddings=True,
    )
    config.architectures = ["Qwen3ForCausalLM"]
    config.quantization = {"group_size": 64, "bits": 4}
    config.save_pretrained(folder)
    random = np.random.default_rng(210)
    weights = {}
    shapes = {"model.embed_tokens": (64, 64)}
    for name in ("q_proj", "k_proj", "v_proj", "o_proj"):
        shapes["model.layers.0.self_attn." + name] = (64, 64)
    for name, shape in (
        ("gate_proj", (128, 64)),
        ("up_proj", (128, 64)),
        ("down_proj", (64, 128)),
    ):
        shapes["model.layers.0.mlp." + name] = shape
    for name, (outputs, width) in shapes.items():
        weights[name + ".weight"] = torch.from_numpy(
            random.integers(0, 2**32, (outputs, width // 8), dtype=np.uint32)
        )
        weights[name + ".scales"] = torch.full((outputs, width // 64), 0.002)
        weights[name + ".biases"] = torch.full((outputs, width // 64), -0.015)
    for name in (
        "model.norm",
        "model.layers.0.input_layernorm",
        "model.layers.0.post_attention_layernorm",
        "model.layers.0.self_attn.q_norm",
        "model.layers.0.self_attn.k_norm",
    ):
        weights[name + ".weight"] = torch.ones(64)
    save_file(weights, folder / "model.safetensors")
    tokenizer = Tokenizer(
        models.WordLevel(
            {"[UNK]": 0, **{chr(65 + n): n + 1 for n in range(26)}}, unk_token="[UNK]"
        )
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(tokenizer_object=tokenizer, unk_token="[UNK]")
    fast.chat_template = "{{ messages[0]['content'] }}"
    fast.save_pretrained(folder)


def test_tiny_export_preserves_dynamic_labels_and_distinct_identity(tmp_path):
    torch.set_num_threads(2)
    base, out = tmp_path / "source", tmp_path / "portable"
    tiny_source(base)
    item = {"question": "Choose one.", "options": {"A": "one", "B": "two"}}
    receipt = export(base, None, item, out)
    assert receipt["source_identity"] != receipt["model_identity"]
    assert receipt["native_calibration"] == "incompatible arithmetic identity"
    assert len(receipt["probes"][-1]["label_ids"]) == 26
    assert all(row["max_error"] < 0.002 for row in receipt["probes"])
    assert set(receipt["files"]) == {
        "model.onnx",
        "model.onnx.data",
        "tokenizer.json",
        "tokenizer_config.json",
    }
    assert json.loads((out / "manifest.json").read_text()) == receipt
    with pytest.raises(FileExistsError):
        export(base, None, item, out)


def test_integer_labels_and_unknown_architecture_fail_closed():
    with pytest.raises(ValueError, match="reorder"):
        probe_items({"question": "Choose.", "options": {"2": "two", "1": "one"}})
    with pytest.raises(ValueError, match="Qwen3"):
        validate_config({"architectures": ["LlamaForCausalLM"]})


def test_mismatched_adapter_identity_is_rejected_before_tensor_loading(tmp_path):
    base, adapter = tmp_path / "base", tmp_path / "adapter"
    base.mkdir()
    adapter.mkdir()
    (base / "config.json").write_text("{}")
    (adapter / "specialist.json").write_text(json.dumps({"base_identity": "0" * 64}))
    with pytest.raises(ValueError, match="another base"):
        source_identity(base, adapter)


def test_affine_adapter_export_matches_independent_dense_hf_oracle(tmp_path):
    from safetensors.torch import load_file, save_file
    from transformers import Qwen3Config
    from transformers.models.qwen3.modeling_qwen3 import Qwen3Model
    from common import digest, file_hash, write_json
    from decision_native import base_files

    torch.set_num_threads(2)
    base, adapter = tmp_path / "base", tmp_path / "adapter"
    tiny_source(base)
    adapter.mkdir()
    random = np.random.default_rng(217)
    tensors = {}
    for projection in ("q_proj", "v_proj"):
        key = f"model.layers.0.self_attn.{projection}"
        tensors[key + ".lora_a"] = torch.from_numpy(
            random.normal(0, 0.04, (64, 2)).astype("float32")
        )
        tensors[key + ".lora_b"] = torch.from_numpy(
            random.normal(0, 0.04, (2, 64)).astype("float32")
        )
    save_file(tensors, adapter / "adapters.safetensors")
    scale = 1.7
    write_json(
        adapter / "adapter_config.json",
        {
            "fine_tune_type": "lora",
            "num_layers": 1,
            "lora_parameters": {
                "rank": 2,
                "scale": scale,
                "keys": ["self_attn.q_proj", "self_attn.v_proj"],
            },
        },
    )
    write_json(
        adapter / "specialist.json",
        {
            "base_identity": digest({"backend": "mlx", "files": base_files(base)}),
            "adapter_sha256": file_hash(adapter / "adapters.safetensors"),
            "adapter_config_sha256": file_hash(adapter / "adapter_config.json"),
        },
    )
    receipt = export(
        base,
        adapter,
        {"question": "Choose.", "options": {"B": "two", "A": "one"}},
        tmp_path / "out",
    )
    config = Qwen3Config.from_pretrained(base, local_files_only=True)
    config._attn_implementation = "eager"
    dense = Qwen3Model(config).eval()
    packed = load_file(base / "model.safetensors")
    state = {}
    for name in dense.state_dict():
        key = "model." + name
        raw = packed[key]
        if raw.dtype == torch.uint32:
            # Independent uint32 decoding, rather than production byte splitting,
            # zero-point compensation, group sums or custom ONNX operators.
            words = raw.numpy().astype(np.uint64)
            q = np.stack([(words >> (4 * n)) & 15 for n in range(8)], -1).reshape(
                raw.shape[0], -1
            )
            prefix = key.removesuffix(".weight")
            weight = torch.from_numpy(q.astype("float32")) * packed[
                prefix + ".scales"
            ].repeat_interleave(64, -1) + packed[prefix + ".biases"].repeat_interleave(
                64, -1
            )
            if prefix + ".lora_a" in tensors:
                weight = (
                    weight
                    + scale
                    * (tensors[prefix + ".lora_a"] @ tensors[prefix + ".lora_b"]).T
                )
            state[name] = weight
        else:
            state[name] = raw
    dense.load_state_dict(state, strict=True)
    with torch.no_grad():
        for probe in receipt["probes"]:
            tokens, labels = (
                torch.tensor([probe["tokens"]]),
                torch.tensor(probe["label_ids"]),
            )
            expected = (
                dense(input_ids=tokens, use_cache=False).last_hidden_state[:, -1]
                @ dense.embed_tokens(labels).T
            )
            np.testing.assert_allclose(
                probe["logits"], expected.numpy()[0], atol=2e-5, rtol=2e-5
            )
    assert receipt["source_adapter"]["weights_sha256"] == file_hash(
        adapter / "adapters.safetensors"
    )
