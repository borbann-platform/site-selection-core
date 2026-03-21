#!/usr/bin/env bash
set -euo pipefail

TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"
TAILSCALE_TAG="${TAILSCALE_TAG:-tag:vps}"

curl -fsSL https://tailscale.com/install.sh | sh

if [[ -n "$TAILSCALE_AUTHKEY" ]]; then
  tailscale up --authkey "$TAILSCALE_AUTHKEY" --advertise-tags "$TAILSCALE_TAG"
else
  tailscale up --advertise-tags "$TAILSCALE_TAG"
fi

tailscale ip -4
tailscale status
