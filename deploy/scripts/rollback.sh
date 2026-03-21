#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_FILE="$ROOT_DIR/deploy/state/last_successful_image_tag"
ENV_FILE="${APP_ENV_FILE:-$ROOT_DIR/.env.production}"

if [[ ! -f "$STATE_FILE" ]]; then
  echo "No recorded successful image tag found at $STATE_FILE" >&2
  exit 1
fi

PREVIOUS_TAG="$(tr -d '\n' < "$STATE_FILE")"

if [[ -z "$PREVIOUS_TAG" ]]; then
  echo "Recorded image tag is empty" >&2
  exit 1
fi

cd "$ROOT_DIR"
IMAGE_TAG="$PREVIOUS_TAG" docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml pull
IMAGE_TAG="$PREVIOUS_TAG" docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml up -d --remove-orphans

echo "Rolled back to image tag: $PREVIOUS_TAG"
