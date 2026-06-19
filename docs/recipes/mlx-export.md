# MLX Export

Use `tinygpt export-mlx` when a TinyGPT-trained artifact needs to leave the
TinyGPT binary and be loaded from Python MLX, MLX-Swift, or another Mac-local
tool.

Full distilled or trained checkpoints:

```bash
tinygpt export-mlx path/to/model.tinygpt --out exported-model
python exported-model/mlx_load.py exported-model
```

Fine-tuned adapters:

```bash
tinygpt export-mlx path/to/adapter.lora --out exported-adapter
python exported-adapter/mlx_load.py exported-adapter
```

The command writes standard safetensors containers plus sidecars:

- `model.safetensors` for full `.tinygpt` checkpoints.
- `adapters.safetensors` for `.lora` / DoRA adapters.
- `config.json`, `adapter_config.json`, tokenizer sidecars, and
  `tinygpt_mlx_export.json` metadata.
- `mlx_load.py`, a tiny Python MLX helper that loads the arrays and config.

TinyGPT-native byte-level checkpoints are not marked as `mlx-lm` compatible.
Their tensors are MLX-loadable, but a caller still needs a TinyGPT-aware module
class to run a forward pass. HF / MLX model directories copied through
`export-mlx` remain `mlx-lm` compatible when their original architecture is
supported by `mlx-lm`.

## Specialist packages

For trained modules that should be shared or routed in an app, pair the MLX
export with a specialist package under `specialists/<id>/`:

- `model_card.md` for the human-facing claim and limitations.
- `prompt.md` for the measured system/developer prompt.
- `eval_report.json` for machine-readable scores and regressions.
- `tinygpt.lock.json` for artifact files, sizes, checksums, base model, and
  compatibility.
- `mlx_load.py` for cheap metadata validation and optional MLX loading.

The first package is `specialists/qwen3-4b-file-ops-distilled`: a real fused
Qwen3-4B file-ops specialist stored at `~/.cache/tinygpt/models/mt4b_fused`.
