#!/usr/bin/env bash
# E6 (V2) — install the official ScaleBench harness for public-leaderboard
# parity, mirroring the BFCL/tau-bench _external convention. NETWORK + pip;
# run manually. The self-contained `tinygpt eval-scaledown` (V1) needs none of
# this.
#
#   bash scripts/install-scalebench.sh
set -euo pipefail
DEST="${SCALEBENCH_DIR:-$HOME/.cache/tinygpt/datasets/_external/scalebench}"
REPO="https://github.com/scaledown-ai/scaledown"

if [ -d "$DEST/.git" ]; then
  echo "updating $DEST"; git -C "$DEST" pull --ff-only
else
  echo "cloning $REPO → $DEST"; mkdir -p "$(dirname "$DEST")"; git clone "$REPO" "$DEST"
fi

if [ -f "$DEST/requirements.txt" ]; then
  python3 -m pip install -r "$DEST/requirements.txt"
elif [ -f "$DEST/pyproject.toml" ]; then
  python3 -m pip install -e "$DEST"
else
  echo "warning: no requirements.txt/pyproject.toml in $DEST — install deps manually" >&2
fi
echo "ScaleBench at $DEST — point tinygpt eval-scaledown's V2 wrapper here."
