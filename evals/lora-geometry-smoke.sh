#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 - "$TMP_DIR/tiny.lora" <<'PY'
import json
import struct
import sys

import numpy as np

out = sys.argv[1]
header = {
    "rank": 2,
    "alpha": 4.0,
    "targetSuffixes": ["q_proj"],
    "entries": [
        {
            "name": "layers.0.attn.q_proj",
            "loraAShape": [3, 2],
            "loraBShape": [2, 4],
            "loraMShape": [4],
        }
    ],
}
header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
a = np.array([[1.0, 0.0], [0.5, 0.25], [0.0, 1.0]], dtype="<f4")
b = np.array([[1.0, 0.25, 0.0, 0.5], [0.0, 0.5, 1.0, 0.25]], dtype="<f4")
m = np.ones((4,), dtype="<f4")
with open(out, "wb") as f:
    f.write(b"TGLA")
    f.write(struct.pack("<I", 2))
    f.write(struct.pack("<I", len(header_bytes)))
    f.write(header_bytes)
    f.write(a.tobytes())
    f.write(b.tobytes())
    f.write(m.tobytes())
PY

python3 scripts/lora_geometry.py \
  "$TMP_DIR/tiny.lora" \
  --out "$TMP_DIR/lora-geometry.json" >/dev/null

grep -q "mean_stable_rank" "$TMP_DIR/lora-geometry.json"
grep -q "has_dora" "$TMP_DIR/lora-geometry.json"
echo "lora-geometry-smoke ok"
