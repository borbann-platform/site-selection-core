#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT_DIR/deploy/state"
STATE_FILE="$STATE_DIR/last_successful_image_tag"
PENDING_FILE="$STATE_DIR/pending_image_tag"
ENV_FILE="${APP_ENV_FILE:-$ROOT_DIR/.env.production}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8000/readyz}"
FRONTEND_HEALTH_URL="${FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/healthz}"

mkdir -p "$STATE_DIR"

wait_for_url() {
  local url="$1"
  local name="$2"

  for _ in $(seq 1 30); do
    if curl -fsS "$url" >/dev/null; then
      echo "$name is healthy: $url"
      return 0
    fi
    sleep 2
  done

  echo "$name failed health check: $url" >&2
  return 1
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "IMAGE_TAG must be set" >&2
  exit 1
fi

for required_dir in "$ROOT_DIR/runtime/gis-server/data" "$ROOT_DIR/runtime/gis-server/models"; do
  if [[ ! -d "$required_dir" ]]; then
    echo "Missing required runtime directory: $required_dir" >&2
    exit 1
  fi
done

if grep -q 'change-me' "$ENV_FILE"; then
  echo "Refusing to deploy with placeholder secrets still present in $ENV_FILE" >&2
  exit 1
fi

cd "$ROOT_DIR"

docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml config -q
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml pull
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml up -d --remove-orphans

wait_for_url "$BACKEND_HEALTH_URL" "backend"
wait_for_url "$FRONTEND_HEALTH_URL" "frontend"

printf '%s\n' "$IMAGE_TAG" > "$PENDING_FILE"
docker image prune -f

if [[ -f "$STATE_FILE" ]]; then
  echo "Current stable image tag: $(tr -d '\n' < "$STATE_FILE")"
else
  echo "No prior stable image tag recorded yet"
fi

echo "Deployed candidate image tag: $IMAGE_TAG"
docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml ps
