#!/usr/bin/env bash
# E6 (V2) — install the official ScaleBench harness for public-leaderboard
# parity, mirroring the BFCL/tau-bench _external convention. NETWORK + pip;
# run manually. The self-contained `posttrainllm eval-scaledown` (V1) needs none of
# this.
#
#   bash scripts/install-scalebench.sh
set -euo pipefail
DEST="${SCALEBENCH_DIR:-$HOME/.cache/posttrainllm/datasets/_external/scalebench}"
# ⚠️ The repo URL from the E6 PRD (github.com/scaledown-ai/scaledown) returns
# 404 as of 2026-06-20 — the challenge repo appears moved/renamed/private.
# Override with REPO=<url> once the real location is known. Until then the
# self-contained `posttrainllm eval-scaledown` (E6 V1) is the working path.
REPO="${REPO:-https://github.com/scaledown-ai/scaledown}"

if [ -d "$DEST/.git" ]; then
  echo "updating $DEST"; git -C "$DEST" pull --ff-only
else
  if ! git ls-remote "$REPO" HEAD >/dev/null 2>&1; then
    echo "error: ScaleBench repo not reachable at $REPO (the PRD URL 404s)." >&2
    echo "       Pass REPO=<correct-url> once the challenge repo location is known;" >&2
    echo "       meanwhile use 'posttrainllm eval-scaledown' (E6 V1, self-contained)." >&2
    exit 1
  fi
  echo "cloning $REPO → $DEST"; mkdir -p "$(dirname "$DEST")"; git clone "$REPO" "$DEST"
fi

if [ -f "$DEST/requirements.txt" ]; then
  python3 -m pip install -r "$DEST/requirements.txt"
elif [ -f "$DEST/pyproject.toml" ]; then
  python3 -m pip install -e "$DEST"
else
  echo "warning: no requirements.txt/pyproject.toml in $DEST — install deps manually" >&2
fi
echo "ScaleBench at $DEST — point posttrainllm eval-scaledown's V2 wrapper here."
