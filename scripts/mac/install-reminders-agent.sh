#!/usr/bin/env bash
# Install LaunchAgent for hourly ntfy study-reminder ticks.
# Cadence (twice / thrice / hourly) is chosen in the Settings UI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.constitution-memorizer.reminders"
PLIST_SRC="$ROOT/scripts/mac/${LABEL}.plist.example"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
VENV_PYTHON="${ROOT}/.venv/bin/python"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS (Darwin). Detected: $(uname -s)"
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing $VENV_PYTHON — create the venv first."
  exit 1
fi

TOPIC="${NTFY_TOPIC:-}"
if [[ -z "$TOPIC" ]]; then
  echo "Set NTFY_TOPIC to a private topic name, e.g.:"
  echo "  export NTFY_TOPIC=cm-$(whoami)-study"
  exit 1
fi
SERVER="${NTFY_SERVER:-https://ntfy.sh}"
TOKEN="${NTFY_TOKEN:-}"

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

sed \
  -e "s|__REPO_ROOT__|${ROOT}|g" \
  -e "s|__VENV_PYTHON__|${VENV_PYTHON}|g" \
  -e "s|__HOME__|${HOME}|g" \
  -e "s|__NTFY_TOPIC__|${TOPIC}|g" \
  -e "s|__NTFY_SERVER__|${SERVER}|g" \
  -e "s|__NTFY_TOKEN__|${TOKEN}|g" \
  "$PLIST_SRC" > "$PLIST_DST"

if launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent: $LABEL (hourly ticks)"
elif launchctl load "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent (legacy): $LABEL"
else
  echo "Wrote $PLIST_DST but could not load it."
  exit 1
fi

echo "Subscribe in the ntfy app to topic: $TOPIC"
echo "Choose cadence in the UI: http://127.0.0.1:8001/settings (default: thrice)"
echo "Test now: NTFY_TOPIC=$TOPIC $VENV_PYTHON -m constitution_memorizer.cli send-reminders --channel ntfy --at \$(date +%Y-%m-%dT%H:%M)"
echo "Logs: ~/Library/Logs/constitution-memorizer-reminders.log"
