#!/usr/bin/env bash
# B9 — allow passwordless `powermetrics` for the energy/thermal benches.
#
# powermetrics needs root. Rather than typing a password per run, this
# installs a sudoers drop-in that lets the CURRENT user run *only*
# /usr/bin/powermetrics without a password. Review it before running.
#
#   sudo bash scripts/bench/setup_powermetrics_sudoers.sh
#
# Undo: sudo rm /etc/sudoers.d/posttrainllm-powermetrics
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo bash $0" >&2
  exit 1
fi

USER_NAME="${SUDO_USER:-$(whoami)}"
DROPIN=/etc/sudoers.d/posttrainllm-powermetrics
TMP="$(mktemp)"
printf '%s ALL=(root) NOPASSWD: /usr/bin/powermetrics\n' "$USER_NAME" > "$TMP"

# Validate syntax with visudo BEFORE installing — a malformed sudoers file
# can lock you out of sudo, so never write it unchecked.
if ! visudo -cf "$TMP"; then
  echo "refusing to install: visudo validation failed" >&2
  rm -f "$TMP"; exit 1
fi

install -m 0440 "$TMP" "$DROPIN"
rm -f "$TMP"
echo "installed $DROPIN — $USER_NAME may now run powermetrics without a password"
echo "undo with: sudo rm $DROPIN"
