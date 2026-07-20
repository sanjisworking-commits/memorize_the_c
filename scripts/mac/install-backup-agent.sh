#!/usr/bin/env bash
# Install optional weekly LaunchAgent for progress.db backup (Sunday 09:00).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.constitution-memorizer.backup"
PLIST_SRC="$ROOT/scripts/mac/${LABEL}.plist.example"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
BACKUP_SCRIPT="$ROOT/scripts/mac/backup-progress.sh"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS (Darwin). Detected: $(uname -s)"
  exit 1
fi

if [[ ! -f "$BACKUP_SCRIPT" ]]; then
  echo "Missing $BACKUP_SCRIPT"
  exit 1
fi

chmod +x "$BACKUP_SCRIPT"
mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/Library/Logs"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_DST" 2>/dev/null || true

sed \
  -e "s|__REPO_ROOT__|${ROOT}|g" \
  -e "s|__HOME__|${HOME}|g" \
  -e "s|__BACKUP_SCRIPT__|${BACKUP_SCRIPT}|g" \
  "$PLIST_SRC" > "$PLIST_DST"

if launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent: $LABEL (Sunday 09:00)"
elif launchctl load "$PLIST_DST" 2>/dev/null; then
  echo "Loaded LaunchAgent (legacy): $LABEL"
else
  echo "Wrote $PLIST_DST but could not load it."
  exit 1
fi

echo "Backups go to ~/Documents/ConstitutionMemorizerBackups/"
echo "Run once now: bash scripts/mac/backup-progress.sh"
echo "Unload: bash scripts/mac/uninstall-backup-agent.sh"
