#!/usr/bin/env bash
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"

ufw default deny incoming
ufw default allow outgoing
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "$SSH_PORT"/tcp
ufw --force enable
ufw status verbose

echo "Firewall enabled. Remove public SSH after Tailscale-only SSH is verified."
