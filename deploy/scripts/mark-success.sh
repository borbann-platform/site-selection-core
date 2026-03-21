#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT_DIR/deploy/state"
STATE_FILE="$STATE_DIR/last_successful_image_tag"
PENDING_FILE="$STATE_DIR/pending_image_tag"

mkdir -p "$STATE_DIR"

if [[ ! -f "$PENDING_FILE" ]]; then
  echo "No pending image tag recorded at $PENDING_FILE" >&2
  exit 1
fi

mv "$PENDING_FILE" "$STATE_FILE"
echo "Marked stable image tag: $(tr -d '\n' < "$STATE_FILE")"
