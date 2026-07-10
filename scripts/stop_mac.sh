#!/usr/bin/env bash
# Stop and remove the FinAlly container (macOS/Linux).
# The db/ bind mount is untouched, so data persists.
set -euo pipefail

docker rm -f finally >/dev/null 2>&1 || true
echo "Stopped and removed container 'finally' (data in db/ preserved)."
