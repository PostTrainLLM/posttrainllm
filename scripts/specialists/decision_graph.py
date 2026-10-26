"""Portable float32 Qwen3 using maintained Transformers and ONNX Runtime ops.

MLX affine q4 weights are retained as packed nibbles. MatMulNBits uses zero
point 8; a group-sum correction restores MLX's noninteger affine bias. This
is a distinct arithmetic identity, not native BF16/calibration equivalence.
Contract: docs/factory/specialist-labs.md.
"""

import json
from pathlib import Path

import onnxscript
import torch
from onnxscript import FLOAT, UINT8, opset18 as op
from onnxscript.values import Opset
from safetensors import safe_open
from transformers import Qwen3Config
from transformers.models.qwen3.modeling_qwen3 import Qwen3Model, Qwen3RotaryEmbedding

MICROSOFT = Opset(domain="com.microsoft", version=1)


@torch.library.custom_op("posttrain::packed_affine", mutates_args=())
def packed_affine(
    inputs: torch.Tensor,
    packed: torch.Tensor,
    scales: torch.Tensor,
    correction: torch.Tensor,
    width: int,
    outputs: int,
) -> torch.Tensor:
    values = torch.stack([packed & 15, packed >> 4], -1).reshape(outputs, width)
    weights = (values.float() - 8) * scales.repeat_interleave(64, -1)
    groups = inputs.reshape(*inputs.shape[:-1], width // 64, 64).sum(-1)
    return inputs @ weights.T + groups @ correction


@packed_affine.register_fake
def affine_shape(inputs, packed, scales, correction, width, outputs):
    return inputs.new_empty((*inputs.shape[:-1], outputs))


@onnxscript.script(MICROSOFT)
def translate_affine(
    inputs: FLOAT,
    packed: UINT8,
    scales: FLOAT,
    correction: FLOAT,
    width: int,
    outputs: int,
) -> FLOAT:
    # accuracy_level=4 permits approximate input quantization on CPU. Level 0
    # keeps the float32 input contract used by the Python/browser parity gate.
    base = MICROSOFT.MatMulNBits(
        inputs,
        packed,
        scales,
        K=width,
        N=outputs,
        bits=4,
        block_size=64,
        accuracy_level=0,
    )
    grouped = op.Reshape(inputs, op.Constant(value_ints=[0, 0, -1, 64]))
    sums = op.ReduceSum(grouped, op.Constant(value_ints=[-1]), keepdims=0)
    return base + op.MatMul(sums, correction)


class Weights:
    def __init__(self, base):
        self.base = Path(base)
        index = self.base / "model.safetensors.index.json"
        self.index = (
            json.loads(index.read_text())["weight_map"] if index.exists() else None
        )

    def read(self, name):
        filename = self.index[name] if self.index else "model.safetensors"
        if Path(filename).name != filename or not filename.endswith(".safetensors"):
            raise ValueError("weight index must reference local safetensors basenames")
        with safe_open(self.base / filename, framework="pt", device="cpu") as stream:
            return stream.get_tensor(name)

    def quantized(self, name):
        weight = self.read(name + ".weight")
        scales, biases = (
            self.read(name + suffix).float() for suffix in (".scales", ".biases")
        )
        if weight.ndim != 2 or weight.dtype != torch.uint32:
            raise ValueError("portable Qwen requires packed uint32 MLX q4 weights")
        count, width = weight.shape[0], weight.shape[1] * 8
        if (
            width % 64
            or scales.shape != (count, width // 64)
            or biases.shape != scales.shape
        ):
            raise ValueError("invalid MLX group64 affine weight shape")
        if not torch.isfinite(scales).all() or not torch.isfinite(biases).all():
            raise ValueError("nonfinite MLX affine parameters")
        return weight.view(torch.uint8).reshape(count, width // 2), scales, biases


class AffineLinear(torch.nn.Module):
    def __init__(self, weights, name, adapters, scale):
        super().__init__()
        packed, scales, biases = weights.quantized(name)
        self.width, self.outputs = packed.shape[1] * 2, packed.shape[0]
        self.register_buffer(
            "packed", packed.reshape(self.outputs, self.width // 64, 32)
        )
        self.register_buffer("scales", scales)
        self.register_buffer("correction", (biases + 8 * scales).T.contiguous())
        self.has_adapter = name + ".lora_a" in adapters
        self.scale = scale
        if self.has_adapter:
            self.register_buffer(
                "lora_a", torch.from_numpy(adapters[name + ".lora_a"]).float()
            )
            self.register_buffer(
                "lora_b", torch.from_numpy(adapters[name + ".lora_b"]).float()
            )

    def forward(self, inputs):
        output = packed_affine(
            inputs, self.packed, self.scales, self.correction, self.width, self.outputs
        )
        if self.has_adapter:
            output = output + self.scale * (inputs @ self.lora_a) @ self.lora_b
        return output


class AffineEmbedding(torch.nn.Module):
    def __init__(self, weights):
        super().__init__()
        packed, scales, biases = weights.quantized("model.embed_tokens")
        self.register_buffer("packed", packed)
        self.register_buffer("scales", scales)
        self.register_buffer("biases", biases)

    def forward(self, ids):
        # Decode only selected rows. Float32 exactly represents every byte;
        # remainder/floor avoid an exporter uint8 right-shift type mismatch.
        packed = self.packed[ids].float()
        values = torch.stack(
            [torch.remainder(packed, 16), torch.floor(packed / 16)], -1
        )
        values = values.reshape(*ids.shape, -1)
        return values * self.scales[ids].repeat_interleave(64, -1) + self.biases[
            ids
        ].repeat_interleave(64, -1)


def validate_config(config):
    if (
        config.get("architectures") != ["Qwen3ForCausalLM"]
        or config.get("quantization") != {"group_size": 64, "bits": 4}
        or not config.get("tie_word_embeddings")
        or config.get("attention_bias", False)
        or config.get("hidden_act", "silu") != "silu"
        or config.get("rope_scaling") is not None
    ):
        raise ValueError(
            "portable export supports tied-embedding Qwen3 MLX affine q4/group64 with standard RoPE"
        )
    for name, maximum in (
        ("hidden_size", 4096),
        ("num_hidden_layers", 64),
        ("vocab_size", 200000),
    ):
        value = config.get(name)
        if type(value) is not int or not 0 < value <= maximum:
            raise ValueError(f"unsupported Qwen dimension: {name}")


class DecisionGraph(torch.nn.Module):
    def __init__(self, base, adapters=None, scale=0):
        super().__init__()
        raw = json.loads((Path(base) / "config.json").read_text())
        validate_config(raw)
        config = Qwen3Config.from_pretrained(base, local_files_only=True)
        config._attn_implementation = "eager"
        weights = Weights(base)
        with torch.device("meta"):
            self.model = Qwen3Model(config)
        self.model.embed_tokens = AffineEmbedding(weights)
        for name, module in list(self.model.named_modules()):
            if isinstance(module, torch.nn.Linear):
                self.model.set_submodule(
                    name, AffineLinear(weights, "model." + name, adapters or {}, scale)
                )
        for name, _ in list(self.model.named_parameters()):
            parent, leaf = name.rsplit(".", 1)
            value = weights.read("model." + name).float()
            if not torch.isfinite(value).all():
                raise ValueError("nonfinite Qwen normalization weights")
            setattr(
                self.model.get_submodule(parent),
                leaf,
                torch.nn.Parameter(value, requires_grad=False),
            )
        self.model.rotary_emb = Qwen3RotaryEmbedding(config, device="cpu")

    def forward(self, tokens, labels):
        hidden = self.model(input_ids=tokens, use_cache=False).last_hidden_state[
            :, -1, :
        ]
        return hidden @ self.model.embed_tokens(labels).T


def export_graph(model, tokens, labels, path):
    program = torch.onnx.export(
        model,
        (tokens, labels),
        dynamo=True,
        dynamic_shapes={
            "tokens": {1: torch.export.Dim("sequence", min=1, max=4096)},
            "labels": {0: torch.export.Dim("labels", min=2, max=26)},
        },
        custom_translation_table={
            torch.ops.posttrain.packed_affine.default: translate_affine
        },
        input_names=["tokens", "labels"],
        output_names=["logits"],
        opset_version=18,
        optimize=False,
    )
    program.save(path, external_data=True)
