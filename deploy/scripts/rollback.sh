#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_FILE="$ROOT_DIR/deploy/state/last_successful_image_tag"
ENV_FILE="${APP_ENV_FILE:-$ROOT_DIR/.env.production}"
ROLLBACK_PULL_POLICY="${ROLLBACK_PULL_POLICY:-missing}"

COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker-compose.prod.yml)

image_exists_locally() {
  docker image inspect "$1" >/dev/null 2>&1
}

if [[ ! -f "$STATE_FILE" ]]; then
  echo "No recorded successful image tag found at $STATE_FILE" >&2
  exit 1
fi

PREVIOUS_TAG="$(tr -d '\n' < "$STATE_FILE")"

if [[ -z "$PREVIOUS_TAG" ]]; then
  echo "Recorded image tag is empty" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${BACKEND_IMAGE:?BACKEND_IMAGE is required in $ENV_FILE}"
: "${FRONTEND_IMAGE:?FRONTEND_IMAGE is required in $ENV_FILE}"

cd "$ROOT_DIR"

case "$ROLLBACK_PULL_POLICY" in
  always)
    IMAGE_TAG="$PREVIOUS_TAG" ${COMPOSE[@]} pull backend frontend
    ;;
  missing)
    services_to_pull=()
    if ! image_exists_locally "${BACKEND_IMAGE}:${PREVIOUS_TAG}"; then
      services_to_pull+=(backend)
    fi
    if ! image_exists_locally "${FRONTEND_IMAGE}:${PREVIOUS_TAG}"; then
      services_to_pull+=(frontend)
    fi
    if [[ ${#services_to_pull[@]} -gt 0 ]]; then
      IMAGE_TAG="$PREVIOUS_TAG" ${COMPOSE[@]} pull "${services_to_pull[@]}"
    fi
    ;;
  never)
    ;;
  *)
    echo "Invalid ROLLBACK_PULL_POLICY: $ROLLBACK_PULL_POLICY" >&2
    exit 1
    ;;
esac

IMAGE_TAG="$PREVIOUS_TAG" ${COMPOSE[@]} up -d --remove-orphans --pull never backend frontend

echo "Rolled back to image tag: $PREVIOUS_TAG"
