#!/usr/bin/env bash
set -euo pipefail
LABEL="com.constitution-memorizer.reminders"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true
rm -f "$PLIST_DST"
echo "Removed reminders LaunchAgent (if present)."
