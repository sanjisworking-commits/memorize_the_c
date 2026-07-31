#!/usr/bin/env bash
# Install LaunchAgent for hourly study-reminder ticks.
# Default channel: macos (Notification Center via osascript).
# Override with REMINDER_CHANNEL=ntfy (requires NTFY_TOPIC).
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

CHANNEL="${REMINDER_CHANNEL:-macos}"
TOPIC="${NTFY_TOPIC:-}"
SERVER="${NTFY_SERVER:-https://ntfy.sh}"
TOKEN="${NTFY_TOKEN:-}"

if [[ "$CHANNEL" == "ntfy" && -z "$TOPIC" ]]; then
  echo "Set NTFY_TOPIC when using REMINDER_CHANNEL=ntfy, e.g.:"
  echo "  export NTFY_TOPIC=cm-$(whoami)-study"
  echo "  export REMINDER_CHANNEL=ntfy"
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

sed \
  -e "s|__REPO_ROOT__|${ROOT}|g" \
  -e "s|__VENV_PYTHON__|${VENV_PYTHON}|g" \
  -e "s|__HOME__|${HOME}|g" \
  -e "s|__REMINDER_CHANNEL__|${CHANNEL}|g" \
  -e "s|__NTFY_TOPIC__|${TOPIC}|g" \
  -e "s|__NTFY_SERVER__|${SERVER}|g" \
  -e "s|__NTFY_TOKEN__|${TOKEN}|g" \
  "$PLIST_SRC" > "$PLIST_DST"

if launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent: $LABEL (hourly ticks, channel=$CHANNEL)"
elif launchctl load "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent (legacy): $LABEL (channel=$CHANNEL)"
else
  echo "Wrote $PLIST_DST but could not load it."
  exit 1
fi

echo "Choose cadence in the UI: http://127.0.0.1:8001/settings (default: thrice)"
echo "Digest includes Constitution due/overdue units and Memory log reviews."
if [[ "$CHANNEL" == "macos" ]]; then
  echo "macOS banners use osascript → Notification Center."
  echo "If nothing appears, allow notifications for Script Editor / osascript in"
  echo "  System Settings → Notifications."
  echo "Test now: $VENV_PYTHON -m constitution_memorizer.cli send-reminders --channel macos --at \$(date +%Y-%m-%dT%H:%M)"
else
  echo "Subscribe in the ntfy app to topic: $TOPIC"
  echo "Test now: NTFY_TOPIC=$TOPIC $VENV_PYTHON -m constitution_memorizer.cli send-reminders --channel ntfy --at \$(date +%Y-%m-%dT%H:%M)"
fi
echo "Logs: ~/Library/Logs/constitution-memorizer-reminders.log"
