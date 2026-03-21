#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT_DIR/deploy/state"
STATE_FILE="$STATE_DIR/last_successful_image_tag"
PENDING_FILE="$STATE_DIR/pending_image_tag"
ENV_FILE="${APP_ENV_FILE:-$ROOT_DIR/.env.production}"

mkdir -p "$STATE_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "IMAGE_TAG must be set" >&2
  exit 1
fi

cd "$ROOT_DIR"

docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml pull
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml up -d --remove-orphans

printf '%s\n' "$IMAGE_TAG" > "$PENDING_FILE"
docker image prune -f

if [[ -f "$STATE_FILE" ]]; then
  echo "Current stable image tag: $(tr -d '\n' < "$STATE_FILE")"
else
  echo "No prior stable image tag recorded yet"
fi

echo "Deployed candidate image tag: $IMAGE_TAG"
