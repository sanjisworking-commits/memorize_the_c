#!/usr/bin/env bash
# Unload and remove the weekly backup LaunchAgent.
set -euo pipefail

LABEL="com.constitution-memorizer.backup"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

rm -f "$PLIST_DST"
echo "Uninstalled $LABEL"
