#!/usr/bin/env bash
# Install LaunchAgent so the learning UI starts at login on macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.constitution-memorizer.serve"
PLIST_SRC="$ROOT/scripts/mac/${LABEL}.plist.example"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
VENV_PYTHON="${ROOT}/.venv/bin/python"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS (Darwin). Detected: $(uname -s)"
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing $VENV_PYTHON"
  echo "Create the venv and install first (see README: Run on your MacBook)."
  exit 1
fi

if [[ ! -f "$PLIST_SRC" ]]; then
  echo "Missing template: $PLIST_SRC"
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents"
mkdir -p "${HOME}/Library/Logs"

# Unload existing agent if present (ignore errors).
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

sed \
  -e "s|__REPO_ROOT__|${ROOT}|g" \
  -e "s|__VENV_PYTHON__|${VENV_PYTHON}|g" \
  -e "s|__HOME__|${HOME}|g" \
  "$PLIST_SRC" > "$PLIST_DST"

# Prefer modern bootstrap; fall back to load.
if launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent: $LABEL"
elif launchctl load "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent (legacy load): $LABEL"
else
  echo "Wrote $PLIST_DST but could not load it automatically."
  echo "Try: launchctl bootstrap gui/\$(id -u) $PLIST_DST"
  exit 1
fi

echo "UI should be at http://127.0.0.1:8001/"
echo "Logs: ~/Library/Logs/constitution-memorizer-serve.log"
echo "Unload: launchctl bootout gui/\$(id -u)/${LABEL}"
