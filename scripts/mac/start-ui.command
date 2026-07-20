#!/bin/bash
# Double-click in Finder (macOS) or run from Terminal to start the learning UI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "No .venv found in $ROOT"
  echo "Create one first: python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements-ci.txt && pip install -e ."
  read -r -p "Press Enter to close…"
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f data/output/learning_units.json ]]; then
  echo "Missing data/output/learning_units.json"
  echo "Run: python -m constitution_memorizer.cli correct --force && python -m constitution_memorizer.cli generate-units --force"
  read -r -p "Press Enter to close…"
  exit 1
fi

echo "Starting Constitution Memorizer on http://127.0.0.1:8001/"
echo "Stop with Ctrl+C or scripts/mac/stop-ui.sh"
exec python -m constitution_memorizer.cli serve --host 127.0.0.1 --port 8001
