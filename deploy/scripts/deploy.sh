#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT_DIR/deploy/state"
STATE_FILE="$STATE_DIR/last_successful_image_tag"
PENDING_FILE="$STATE_DIR/pending_image_tag"
ENV_FILE="${APP_ENV_FILE:-$ROOT_DIR/.env.production}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8000/readyz}"
FRONTEND_HEALTH_URL="${FRONTEND_HEALTH_URL:-http://127.0.0.1:3000/healthz}"
APP_IMAGE_PULL_POLICY="${APP_IMAGE_PULL_POLICY:-missing}"
RUN_APP_BOOTSTRAP="${RUN_APP_BOOTSTRAP:-1}"

mkdir -p "$STATE_DIR"

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)
INFRA_SERVICES=(db pgbouncer redis minio)
APP_SERVICES=(backend frontend)

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

wait_for_service_health() {
  local service="$1"
  local container_id

  for _ in $(seq 1 45); do
    container_id="$(${COMPOSE[@]} ps -q "$service")"
    if [[ -n "$container_id" ]]; then
      local status
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
      if [[ "$status" == "healthy" || "$status" == "running" ]]; then
        echo "$service is ready: $status"
        return 0
      fi
    fi
    sleep 2
  done

  echo "$service failed to become ready" >&2
  return 1
}

image_exists_locally() {
  docker image inspect "$1" >/dev/null 2>&1
}

pull_app_images_if_needed() {
  case "$APP_IMAGE_PULL_POLICY" in
    always)
      ${COMPOSE[@]} pull "${APP_SERVICES[@]}"
      ;;
    missing)
      local services_to_pull=()

      if ! image_exists_locally "${BACKEND_IMAGE}:${IMAGE_TAG}"; then
        services_to_pull+=(backend)
      fi
      if ! image_exists_locally "${FRONTEND_IMAGE}:${IMAGE_TAG}"; then
        services_to_pull+=(frontend)
      fi

      if [[ ${#services_to_pull[@]} -gt 0 ]]; then
        ${COMPOSE[@]} pull "${services_to_pull[@]}"
      else
        echo "App images already exist locally for tag $IMAGE_TAG; skipping app image pull"
      fi
      ;;
    never)
      echo "Skipping app image pull because APP_IMAGE_PULL_POLICY=never"
      ;;
    *)
      echo "Invalid APP_IMAGE_PULL_POLICY: $APP_IMAGE_PULL_POLICY" >&2
      exit 1
      ;;
  esac
}

run_app_bootstrap() {
  if [[ "$RUN_APP_BOOTSTRAP" != "1" ]]; then
    echo "Skipping app bootstrap because RUN_APP_BOOTSTRAP=$RUN_APP_BOOTSTRAP"
    return 0
  fi

  IMAGE_TAG="$IMAGE_TAG" ${COMPOSE[@]} run --rm \
    -e DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}" \
    -e DB_USE_PGBOUNCER=false \
    backend python -m scripts.bootstrap_production
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

set -a
source "$ENV_FILE"
set +a

: "${BACKEND_IMAGE:?BACKEND_IMAGE is required in $ENV_FILE}"
: "${FRONTEND_IMAGE:?FRONTEND_IMAGE is required in $ENV_FILE}"

cd "$ROOT_DIR"

${COMPOSE[@]} config -q
${COMPOSE[@]} pull "${INFRA_SERVICES[@]}"
pull_app_images_if_needed
${COMPOSE[@]} up -d "${INFRA_SERVICES[@]}"
wait_for_service_health db
run_app_bootstrap
${COMPOSE[@]} up -d --remove-orphans --pull never "${APP_SERVICES[@]}"

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
${COMPOSE[@]} ps
