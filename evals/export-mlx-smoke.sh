#!/usr/bin/env bash
# Smoke test for `posttrainllm export-mlx`.
#
# No training, no GPU loop, no network. Uses a committed tiny checkpoint
# and a synthetic .lora adapter to verify the exported MLX directory shape.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NATIVE="$ROOT/native-mac"
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
BIN="$(resolve_posttrainllm)" || fail "could not resolve posttrainllm binary"
echo "binary: $BIN"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

MODEL="$ROOT/browser/public/demo.tinygpt"
[ -f "$MODEL" ] || MODEL="$ROOT/data/gallery/shakespeare.tinygpt"
[ -f "$MODEL" ] || fail "no committed .tinygpt fixture found"

echo "--- full model export ---"
"$BIN" export-mlx "$MODEL" --out "$WORK/model-mlx" >/tmp/export-mlx-model.out
test -f "$WORK/model-mlx/model.safetensors" || fail "model.safetensors missing"
test -f "$WORK/model-mlx/config.json" || fail "config.json missing"
test -f "$WORK/model-mlx/posttrainllm_mlx_export.json" || fail "metadata missing"
test -f "$WORK/model-mlx/mlx_load.py" || fail "mlx_load.py missing"

python3 - "$WORK/model-mlx" <<'PY' || exit 1
import json, struct, sys
from pathlib import Path
root = Path(sys.argv[1])
meta = json.loads((root / "posttrainllm_mlx_export.json").read_text())
cfg = json.loads((root / "config.json").read_text())
assert meta["artifact_type"] == "full_model"
assert cfg["model_type"] == "posttrainllm"
with open(root / "model.safetensors", "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    header = json.loads(f.read(n))
assert len(header) > 0
assert any(k.endswith(".weight") for k in header)
PY

if python3 - <<'PY' >/dev/null 2>&1
import mlx.core as mx
PY
then
  python3 "$WORK/model-mlx/mlx_load.py" "$WORK/model-mlx" >/tmp/export-mlx-loader.out
  python3 - <<'PY' || exit 1
import json
data = json.load(open("/tmp/export-mlx-loader.out"))
assert data["artifact_type"] == "full_model"
assert data["tensor_count"] > 0
PY
else
  echo "python mlx unavailable; skipped mlx_load.py execution"
fi

echo "--- adapter export ---"
python3 - "$WORK/fake.lora" <<'PY'
import json, struct, sys
from pathlib import Path
out = Path(sys.argv[1])
header = {
  "rank": 2,
  "alpha": 4.0,
  "targetSuffixes": ["q_proj"],
  "baseLayers": 1,
  "baseDModel": 4,
  "baseCtx": 8,
  "baseHeads": 1,
  "baseDMlp": 16,
  "entries": [{
    "name": "blocks.0.attn.q_proj",
    "loraAShape": [4, 2],
    "loraBShape": [2, 4]
  }]
}
blob = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
floats = [0.0] * (4 * 2 + 2 * 4)
out.write_bytes(b"TGLA" + struct.pack("<II", 2, len(blob)) + blob + struct.pack("<%sf" % len(floats), *floats))
PY
"$BIN" export-mlx "$WORK/fake.lora" --out "$WORK/adapter-mlx" >/tmp/export-mlx-adapter.out
test -f "$WORK/adapter-mlx/adapters.safetensors" || fail "adapters.safetensors missing"
test -f "$WORK/adapter-mlx/adapter_config.json" || fail "adapter_config.json missing"

python3 - "$WORK/adapter-mlx" <<'PY' || exit 1
import json, struct, sys
from pathlib import Path
root = Path(sys.argv[1])
meta = json.loads((root / "posttrainllm_mlx_export.json").read_text())
cfg = json.loads((root / "adapter_config.json").read_text())
assert meta["artifact_type"] == "adapter"
assert cfg["rank"] == 2
with open(root / "adapters.safetensors", "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    header = json.loads(f.read(n))
assert "blocks.0.attn.q_proj.loraA" in header
assert "blocks.0.attn.q_proj.loraB" in header
PY

echo "SMOKE PASS"
