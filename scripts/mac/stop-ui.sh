#!/usr/bin/env bash
# Stop the learning UI serving on port 8001 (if any).
set -euo pipefail

PORT="${1:-8001}"

if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$PIDS" ]]; then
    echo "Nothing listening on port $PORT."
    exit 0
  fi
  echo "Stopping process(es) on port $PORT: $PIDS"
  # shellcheck disable=SC2086
  kill $PIDS 2>/dev/null || true
  sleep 0.5
  PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$PIDS" ]]; then
    # shellcheck disable=SC2086
    kill -9 $PIDS 2>/dev/null || true
  fi
  echo "Port $PORT is free."
else
  echo "lsof not found; cannot stop by port."
  exit 1
fi
