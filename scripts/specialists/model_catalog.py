"""Pinned public model choices and offline readiness; contract: specialist-labs.md."""

from __future__ import annotations

import importlib.util
import platform
from pathlib import Path
import json

MODELS = {
    "qwen-1.7b": {
        "mode": "decision",
        "label": "Qwen3 1.7B · MLX 4-bit",
        "repo": "mlx-community/Qwen3-1.7B-4bit",
        "revision": "3b1b1768f8f8cf8351c712464f906e86c2b8269e",
        "backend": "mlx",
    },
    "qwen-0.6b": {
        "mode": "decision",
        "label": "Qwen3 0.6B · MLX 4-bit",
        "repo": "mlx-community/Qwen3-0.6B-4bit",
        "revision": "73e3e38d981303bc594367cd910ea6eb48349da8",
        "backend": "mlx",
    },
    "timestral-5m": {
        "mode": "forecast",
        "label": "Timestral 5M · CPU",
        "repo": "mistralai/Timestral-5M",
        "revision": "bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f",
    },
    "timestral-28m": {
        "mode": "forecast",
        "label": "Timestral 28M · CPU",
        "repo": "mistralai/Timestral-28M",
        "revision": "49b26409ac87b5935539a5d8ffe7f397b720db47",
    },
    "timestral-123m": {
        "mode": "forecast",
        "label": "Timestral 123M · CPU",
        "repo": "mistralai/Timestral-123M",
        "revision": "5a147287addda85f6acd8da3fb8858fe9af7e8f7",
    },
    "timestral-209m": {
        "mode": "forecast",
        "label": "Timestral 209M · CPU",
        "repo": "mistralai/Timestral-209M",
        "revision": "9874d252ab0aae16f7f7c999f98f98d6ad7d8365",
    },
}


def get(key):
    if key not in MODELS:
        raise ValueError("choose a supported pinned model")
    return MODELS[key]


def readiness(key):
    spec = get(key)
    needed = [
        "huggingface_hub",
        "safetensors",
        "mlx_lm" if spec.get("backend") == "mlx" else "timestral",
    ]
    missing = [name for name in needed if importlib.util.find_spec(name) is None]
    compatible = spec.get("backend") != "mlx" or (
        platform.system() == "Darwin" and platform.machine() == "arm64"
    )
    cached = False
    if "huggingface_hub" not in missing:
        from huggingface_hub import snapshot_download

        try:
            path = Path(
                snapshot_download(
                    spec["repo"],
                    revision=spec["revision"],
                    local_files_only=True,
                    token=False,
                )
            )
            required = ["config.json"] + (
                ["tokenizer_config.json", "tokenizer.json"]
                if spec["mode"] == "decision"
                else []
            )
            cached = all(
                (path / name).is_file() for name in required
            ) and complete_weights(path)
        except (OSError, ValueError):
            pass
    return {
        "id": key,
        **spec,
        "cached": cached,
        "ready": cached and compatible and not missing,
        "missing_packages": missing,
        "compatible": compatible,
    }


def complete_weights(path):
    indexes = list(path.glob("*.safetensors.index.json"))
    if indexes:
        files = {
            name
            for index in indexes
            for name in json.loads(index.read_text())["weight_map"].values()
        }
        return bool(files) and all((path / name).is_file() for name in files)
    return any(path.glob("*.safetensors"))


def download(key):
    spec = get(key)
    from huggingface_hub import snapshot_download

    snapshot_download(
        spec["repo"],
        revision=spec["revision"],
        token=False,
        allow_patterns=["*.json", "*.safetensors", "*.model", "LICENSE*", "tokenizer*"],
    )
    result = readiness(key)
    if not result["ready"]:
        raise ValueError(
            "download finished, but this model still needs a compatible runtime"
        )
    return result
