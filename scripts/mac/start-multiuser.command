#!/bin/bash
# Launch the multi-user hosted UI on port 8010 (does not modify start-ui.command).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export MULTIUSER_ENABLED="${MULTIUSER_ENABLED:-true}"
export PORT="${PORT:-8010}"
export APP_BASE_URL="${APP_BASE_URL:-http://127.0.0.1:${PORT}}"

required=(DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY SESSION_SECRET)
missing=()
for key in "${required[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done
if (( ${#missing[@]} > 0 )); then
  echo "Missing required environment variables: ${missing[*]}" >&2
  echo "Copy .env.example to .env and fill in values." >&2
  exit 1
fi

exec python -m constitution_memorizer.cli serve \
  --host 127.0.0.1 \
  --port "${PORT}"
