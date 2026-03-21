#!/usr/bin/env bash
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR="${APP_DIR:-/opt/app}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups}"

apt-get update
apt-get upgrade -y
apt-get install -y \
  acl \
  ca-certificates \
  curl \
  fail2ban \
  git \
  htop \
  jq \
  nginx \
  python3 \
  python3-venv \
  rsync \
  ufw \
  unattended-upgrades \
  unzip \
  vim \
  wget

if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi

usermod -aG sudo "$DEPLOY_USER"

install -d -m 0755 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$APP_DIR"
install -d -m 0755 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$BACKUP_DIR"
install -d -m 0755 /var/www/certbot

echo "Base system setup complete. Copy your SSH public key to /home/$DEPLOY_USER/.ssh/authorized_keys before disabling password auth."
