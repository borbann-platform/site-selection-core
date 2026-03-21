#!/usr/bin/env bash
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"

curl -fsSL https://get.docker.com | sh
usermod -aG docker "$DEPLOY_USER"
systemctl enable docker

cat >/etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "5"
  }
}
EOF

systemctl restart docker
docker --version
docker compose version

echo "Docker setup complete. Log out and back in so $DEPLOY_USER picks up the docker group."
