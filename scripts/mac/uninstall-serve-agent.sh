#!/usr/bin/env bash
# Unload and remove the serve LaunchAgent.
set -euo pipefail

LABEL="com.constitution-memorizer.serve"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

if [[ -f "$PLIST_DST" ]]; then
  rm -f "$PLIST_DST"
  echo "Removed $PLIST_DST"
else
  echo "No plist at $PLIST_DST"
fi
