#!/usr/bin/env bash
# Start the FinAlly container (macOS/Linux).
# Usage: ./scripts/start_mac.sh [--build]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="finally"
NAME="finally"

build=false
[ "${1:-}" = "--build" ] && build=true

if $build || [ -z "$(docker images -q "$IMAGE")" ]; then
    echo "Building image '$IMAGE'..."
    docker build -t "$IMAGE" "$ROOT"
fi

# Idempotent: remove any existing container first
docker rm -f "$NAME" >/dev/null 2>&1 || true

if [ ! -f "$ROOT/.env" ]; then
    echo "Warning: .env not found. Copy .env.example to .env and add your OPENROUTER_API_KEY." >&2
fi

echo "Starting container '$NAME'..."
docker run -d --name "$NAME" \
    -v "$ROOT/db:/app/db" \
    -p 8000:8000 \
    --env-file "$ROOT/.env" \
    "$IMAGE"

echo "Open http://localhost:8000 in your browser"
