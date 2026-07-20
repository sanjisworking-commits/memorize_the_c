#!/usr/bin/env bash
# Copy progress.db (mastery, schedule, article glosses) to Documents backups.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${ROOT}/data/progress/progress.db"
STAMP="$(date +%Y%m%d)"
DEST_DIR="${HOME}/Documents/ConstitutionMemorizerBackups"
DEST="${DEST_DIR}/progress-${STAMP}.db"

if [[ ! -f "$SRC" ]]; then
  echo "No progress database at $SRC"
  echo "It is created on first Learn / Progress / gloss save. Nothing to back up yet."
  exit 1
fi

mkdir -p "$DEST_DIR"
cp -p "$SRC" "$DEST"

SIZE="$(wc -c < "$SRC" | tr -d ' ')"
echo "Backed up progress.db (${SIZE} bytes)"
echo "  from: $SRC"
echo "  to:   $DEST"
echo
echo "Includes mastery schedule and article glosses (Explain it back)."
echo "Restore: cp \"$DEST\" \"$SRC\"  (stop the UI first)"
echo "Time Machine also covers this file if Documents (or the repo) is included."
